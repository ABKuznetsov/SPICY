#!/usr/bin/env python3
"""Build the current HTML-editor .spicy format using only Python's stdlib."""
import argparse
import hashlib
import io
import json
import math
from pathlib import Path, PurePosixPath
import re
import zipfile
import sys
from strict_contract import loads, validate_profile, PROFILE
from verify_contract import verify as verify_contract


def json_bytes(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def check(condition, message):
    if not condition:
        raise ValueError(message)


def validate_schema(value, schema, location):
    kinds = schema.get("type", [])
    kinds = [kinds] if isinstance(kinds, str) else kinds
    matches = {"object": isinstance(value, dict), "array": isinstance(value, list),
               "string": isinstance(value, str), "boolean": isinstance(value, bool), "null": value is None,
               "number": type(value) in (int, float) and math.isfinite(value),
               "integer": type(value) is int}
    check(not kinds or any(matches.get(kind, False) for kind in kinds), f"Invalid type at {location}")
    if "const" in schema:
        check(value == schema["const"], f"Invalid value at {location}")
    if "enum" in schema:
        check(value in schema["enum"], f"Unsupported value at {location}")
    if type(value) in (int, float):
        if "minimum" in schema:
            check(value >= schema["minimum"], f"Value too small at {location}")
        if "exclusiveMinimum" in schema:
            check(value > schema["exclusiveMinimum"], f"Value too small at {location}")
    if isinstance(value, dict):
        props = schema.get("properties", {})
        check(set(schema.get("required", [])) <= value.keys(), f"Missing fields at {location}")
        if schema.get("additionalProperties") is False:
            check(value.keys() <= props.keys(), f"Unknown fields at {location}")
        for key, child in value.items():
            if key in props:
                validate_schema(child, props[key], f"{location}/{key}")
    if isinstance(value, list) and "items" in schema:
        for index, child in enumerate(value):
            validate_schema(child, schema["items"], f"{location}/{index}")


def validate(document):
    verify_contract()
    schemas = json.loads((Path(__file__).parent.parent / "assets/schema.json").read_text())
    validate_schema(document, schemas["document"], "/document")
    validate_profile(document)
    for collection, kind in {"slides": "slide", "scenes": "scene", "nodes": "node", "interactions": "interaction",
                             "animations": "animation", "assets": "asset", "embeds": "embed", "pagePresets": "pagePreset",
                             "transitions": "transition"}.items():
        for key, record in document[collection].items():
            validate_schema(record, schemas[kind], f"/{collection}/{key}")
            check(record["id"] == key, f"Mismatched ID at {collection}/{key}")
    nodes, slides = document["nodes"], document["slides"]
    order = document["slideOrder"]
    check(order and len(order) == len(set(order)) and set(order) == set(slides), "Invalid slideOrder")
    check(document["defaultPagePresetId"] in document["pagePresets"], "Missing default page preset")
    roots = []
    for slide in slides.values():
        check(slide["sceneId"] in document["scenes"], "Missing slide scene")
        root = document["scenes"][slide["sceneId"]]["rootNodeId"]
        check(root in nodes and nodes[root]["parentId"] is None and nodes[root]["type"] == "frame", "Invalid slide root")
        roots.append(root)
    check(len(set(roots)) == len(roots), "Shared slide root")
    check(set(document['scenes']) == {s['sceneId'] for s in slides.values()}, 'Unused or missing scenes')
    seen = set()
    parts = []
    for slide_id, root in zip(order, [document["scenes"][slides[s]["sceneId"]]["rootNodeId"] for s in order]):
        ids, stack = [], [root]
        while stack:
            node_id = stack.pop()
            check(node_id not in seen, "Cycle or shared object ownership")
            check(node_id in nodes, f"Missing object: {node_id}")
            seen.add(node_id)
            ids.append(node_id)
            node = nodes[node_id]
            check(not node["children"] or node["type"] in ("frame", "group", "component"), "Leaf object has children")
            for child in node["children"]:
                check(child in nodes and nodes[child]["parentId"] == node_id, f"Invalid parent for {child}")
            if node["type"] == "html":
                content = node["content"]
                markup = content.get("markup", "")
                check(markup and not re.search(r"<\s*script\b|\son[a-z][\w:-]*\s*=|javascript\s*:|<!doctype\b|<\s*/?(?:html|head|body)\b", markup, re.I), f"Invalid ordinary HTML: {node_id}")
                check(all(asset in document["assets"] for asset in content.get("assetIds", [])), "Missing HTML asset")
                check(all(asset in document["assets"] for asset in re.findall(r"spicy-asset://([^\s\"'<>]+)", markup)), "Missing markup asset")
            if node["type"] == "embed":
                check(node["content"].get("bundleId") in document["embeds"], "Missing embed bundle")
            for interaction_id in node["interactionIds"]:
                record = document["interactions"].get(interaction_id)
                check(record and record["ownerNodeId"] == node_id, "Invalid interaction ownership")
            check(all(a in document["animations"] for a in node["animationIds"]), "Missing animation")
            stack.extend(reversed(node["children"]))
        selected = set(ids)
        records = {key: record for key, record in document["interactions"].items() if record["ownerNodeId"] in selected}
        animation_ids = {key for node_id in ids for key in nodes[node_id]["animationIds"]}
        parts.append((slide_id, {"slides": {slide_id: slides[slide_id]}, "scenes": {slides[slide_id]["sceneId"]: document["scenes"][slides[slide_id]["sceneId"]]},
                                 "nodes": {key: nodes[key] for key in ids}, "interactions": records,
                                 "animations": {key: document["animations"][key] for key in animation_ids}}))
    check(seen == set(nodes), "Unreachable objects")
    for key, record in document["interactions"].items():
        check(record["ownerNodeId"] in nodes and key in nodes[record["ownerNodeId"]]["interactionIds"], "Unlinked interaction")
        for action in record["actions"]:
            target = action.get("targetId") or action.get("targetNodeId") or action.get("slideId")
            check(target is None or target in nodes or target in slides, "Missing action target")
            if target in nodes:
                part = next(part for _, part in parts if record['ownerNodeId'] in part['nodes'])
                check(target in part['nodes'], 'Action target belongs to another slide')
    outline = document["settings"].get("presentationOutline", {})
    check(outline.get("version") == 1 and outline.get("rootIds"), "Missing presentation outline")
    outline_seen, outline_slides, stack = set(), [], [(key, True) for key in reversed(outline["rootIds"])]
    while stack:
        key, is_root = stack.pop()
        check(key not in outline_seen and key in outline.get("nodes", {}), "Invalid outline ownership")
        outline_seen.add(key)
        record = outline["nodes"][key]
        check(record["id"] == key and (record["type"] == "block" if is_root else record["type"] in ("group", "slide")), "Invalid outline node")
        if record["type"] == "slide":
            outline_slides.append(record["slideId"])
        else:
            stack.extend((child, False) for child in reversed(record["children"]))
    check(outline_slides == order and outline_seen == set(outline["nodes"]), "Outline and slideOrder disagree")
    return parts


def resource(root, relative):
    root = root.resolve()
    check(isinstance(relative, str) and relative and "\\" not in relative and not relative.startswith("/") and all(p not in ("", ".", "..") for p in relative.split("/")), "Unsafe resource path")
    target = (root / relative).resolve()
    check(target.is_relative_to(root), "Resource outside resource root")
    return target.read_bytes()


def build(document, resource_root):
    parts = validate(document)
    entries = {f"slides/{slide_id}.json": json_bytes(part) for slide_id, part in parts}
    for metadata in document["assets"].values():
        data = resource(resource_root, metadata["path"])
        check(len(data) == metadata["size"] and hashlib.sha256(data).hexdigest() == metadata["sha256"], "Image/resource checksum or size mismatch")
        check(metadata["path"].startswith("assets/") and metadata["path"] not in entries, "Conflicting asset path")
        entries[metadata["path"]] = data
    for bundle_id, metadata in document["embeds"].items():
        check(metadata["entryPoint"] in metadata["files"], "Missing embed entry point")
        for name in metadata["files"]:
            relative = f"embeds/{bundle_id}/{name}"
            check(relative not in entries, "Conflicting embed path")
            entries[relative] = resource(resource_root, relative)
    header = {key: value for key, value in document.items() if key not in ("slides", "slideOrder", "scenes", "nodes", "interactions", "animations")}
    manifest = {"formatVersion": document["formatVersion"], "mimeType": "application/vnd.spicy.presentation+zip", "documentId": document["documentId"],
                "createdAt": document["metadata"]["createdAt"], "modifiedAt": document["metadata"]["modifiedAt"], "packageLayout": "split-slides-v1",
                "slideOrder": document["slideOrder"], "document": header, "checksums": {key: hashlib.sha256(data).hexdigest() for key, data in entries.items()}}
    entries["manifest.json"] = json_bytes(manifest)
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, data in entries.items():
            archive.writestr(name, data)
    data = output.getvalue()
    verify_archive(data)
    return data


def verify_archive(data):
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        names = archive.namelist()
        check(len(names)==len(set(names)) and archive.testzip() is None, 'Duplicate or corrupt archive entries')
        entries = {name: archive.read(name) for name in names}
    check('manifest.json' in entries, 'Missing manifest')
    manifest = loads(entries['manifest.json'])
    check(set(manifest)=={'formatVersion','mimeType','documentId','createdAt','modifiedAt','packageLayout','slideOrder','document','checksums'}, 'Unknown manifest fields')
    check(manifest['formatVersion']=='1.0.0' and manifest['mimeType']=='application/vnd.spicy.presentation+zip' and manifest['packageLayout']=='split-slides-v1', 'Unsupported package contract')
    check(set(entries)-{'manifest.json'}==set(manifest['checksums']), 'Manifest checksums must cover every resource')
    for name, checksum in manifest['checksums'].items():
        check(hashlib.sha256(entries[name]).hexdigest()==checksum, 'Archive checksum mismatch: '+name)
    document = dict(manifest['document'])
    document['slideOrder'] = manifest['slideOrder']
    for table in ('slides','scenes','nodes','interactions','animations'):
        document[table] = {}
    for slide_id in document['slideOrder']:
        piece = loads(entries['slides/'+slide_id+'.json'])
        check(set(piece)=={'slides','scenes','nodes','interactions','animations'}, 'Unknown slide-file fields')
        check(set(piece['slides'])=={slide_id}, 'Slide file identity mismatch')
        for table, records in piece.items():
            check(not set(document[table]) & set(records), 'Shared IDs across slide files')
            document[table].update(records)
    validate(document)
    check(document['documentId']==manifest['documentId'], 'Document identity mismatch')
    expected={'manifest.json'}|{'slides/'+sid+'.json' for sid in document['slideOrder']}
    for meta in document['assets'].values():
        expected.add(meta['path']);check(len(entries[meta['path']])==meta['size'] and hashlib.sha256(entries[meta['path']]).hexdigest()==meta['sha256'], 'Asset bytes mismatch')
    for key, meta in document['embeds'].items():
        expected.update('embeds/'+key+'/'+file for file in meta['files'])
    check(set(entries)==expected, 'Unexpected or missing archive entries')
    return {'verified':True,'profile':PROFILE,'slides':len(document['slideOrder']),'entries':len(entries)}


def main():
    if len(sys.argv)==3 and sys.argv[1]=='--verify':
        print(json.dumps(verify_archive(Path(sys.argv[2]).read_bytes()),ensure_ascii=False));return
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("document", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--resource-root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    document = loads(args.document.read_text(encoding="utf-8"))
    data = build(document, args.resource_root.resolve())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("xb") as handle:
        handle.write(data)
    print(json.dumps({"output": str(args.output.resolve()), "slides": len(document["slideOrder"]), "bytes": len(data), **verify_archive(args.output.read_bytes())}, ensure_ascii=False))


if __name__ == "__main__":
    main()

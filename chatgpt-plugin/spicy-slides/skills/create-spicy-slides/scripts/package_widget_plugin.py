"""Package an independent installable SPICY plugin, without bundling the editor."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import re
import zipfile
from widget_contract import validate_widget

def main():
    from verify_contract import verify
    verify()
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('html',type=Path);p.add_argument('output',type=Path)
    p.add_argument('--id',required=True);p.add_argument('--name',required=True);p.add_argument('--version',required=True)
    p.add_argument('--description',required=True);p.add_argument('--author',required=True);p.add_argument('--license',required=True)
    args=p.parse_args()
    if not re.fullmatch(r'[a-z0-9][a-z0-9.-]{0,127}',args.id):raise ValueError('Invalid plugin ID')
    if not re.fullmatch(r'\d+\.\d+\.\d+',args.version):raise ValueError('Use major.minor.patch for plugin version')
    for value in (args.name,args.description,args.author,args.license):
        if not value.strip() or len(value)>1000:raise ValueError('Invalid plugin metadata')
    source=args.html.read_text(encoding='utf-8');validate_widget(source);data=source.encode('utf-8')
    manifest=dict(format='spicy-plugin',formatVersion=1,id=args.id,name=args.name,version=args.version,hostApi=1,description=args.description,author=args.author,license=args.license,entryPoint='index.html',sha256=hashlib.sha256(data).hexdigest())
    result=io.BytesIO()
    with zipfile.ZipFile(result,'w',compression=zipfile.ZIP_STORED) as archive:
        archive.writestr('manifest.json',json.dumps(manifest,ensure_ascii=False,allow_nan=False));archive.writestr('index.html',data)
    if len(result.getvalue())>12*1024*1024:raise ValueError('Plugin package exceeds 12 MB')
    with zipfile.ZipFile(io.BytesIO(result.getvalue())) as archive:
        if archive.testzip() or hashlib.sha256(archive.read('index.html')).hexdigest()!=manifest['sha256']:raise ValueError('Plugin archive verification failed')
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with args.output.open('xb') as output:output.write(result.getvalue())
    print(json.dumps({'output':str(args.output.resolve()),'verified':True,'pluginId':args.id,'version':args.version},ensure_ascii=False))
if __name__=='__main__':main()

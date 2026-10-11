"""Closed authoring profile for SPICY 1.0.0. Reject unknown fields; never repair silently."""
import json
import math
import re

PROFILE = 'spicy-gpt-authoring-v1'

def require(ok, message):
    if not ok:
        raise ValueError(message)

def keys(value, allowed, path, required=()):
    require(isinstance(value, dict), f'{path}: expected object')
    require(not set(value) - set(allowed), f'{path}: unknown fields {sorted(set(value)-set(allowed))}')
    require(set(required) <= set(value), f'{path}: missing required fields')

def identifier(value, path):
    require(isinstance(value, str) and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,127}', value), f'{path}: unsafe identifier')

def geometry(value, path, positive=False):
    keys(value, ('x','y','width','height','rotation'), path, ('x','y','width','height','rotation'))
    for key, item in value.items():
        require(type(item) in (int,float) and math.isfinite(item), f'{path}/{key}: finite number required')
    require(value['width'] >= 0 and value['height'] >= 0, f'{path}: negative size')
    if positive:
        require(value['width'] > 0 and value['height'] > 0, f'{path}: positive size required')

def loads(text):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, f'Duplicate JSON key: {key}')
            result[key] = value
        return result
    def constant(value):
        raise ValueError(f'Non-finite JSON value: {value}')
    return json.loads(text, object_pairs_hook=pairs, parse_constant=constant)

def validate_profile(document):
    keys(document['metadata'], ('title','description','language','createdAt','modifiedAt','author'), '/metadata', ('title','createdAt','modifiedAt'))
    require(all(isinstance(v,str) for v in document['metadata'].values()), '/metadata: string fields required')
    keys(document['settings'], ('presentationOutline',), '/settings', ('presentationOutline',))
    # Native tracks, themes and component definitions require separate confirmed contracts.
    # Dynamic animation and data live inside a widget, not invented native records.
    for table in ('sections','components','animations','transitions','variables','extensions'):
        require(document[table] == {}, f'/{table}: unsupported by {PROFILE}; use an isolated widget')
    for key, theme in document['themes'].items():
        keys(theme, ('id','name','tokens'), '/themes/'+key, ('id','name','tokens'))
        require(theme['id']==key and isinstance(theme['name'],str) and theme['tokens']=={}, '/themes/'+key+': only an empty base theme is supported')
    require(document['sectionOrder'] == [], '/sectionOrder: use presentationOutline blocks and folders')
    outline=document['settings']['presentationOutline']
    keys(outline, ('version','rootIds','nodes'), '/settings/presentationOutline', ('version','rootIds','nodes'))
    for key, item in outline['nodes'].items():
        identifier(key,'/settings/presentationOutline/nodes/'+key)
        allowed=('id','type','slideId') if item.get('type')=='slide' else ('id','type','name','color','children')
        keys(item,allowed,'/settings/presentationOutline/nodes/'+key)
    for table in ('slides','scenes','nodes','interactions','assets','embeds','pagePresets'):
        for key in document[table]:
            identifier(key, f'/{table}/{key}')
    nodes = document['nodes']
    for key, node in nodes.items():
        path = '/nodes/' + key
        geometry(node['geometry'], path+'/geometry')
        keys(node['style'], ('background','backgroundColor','backgroundOpacity','borderColor','borderRadius','borderStyle','borderWidth','opacity','overflow','color','fontFamily','fontSize','fontWeight','fontStyle','textAlign','textDecoration','lineHeight','padding','pointerEvents'), path+'/style')
        keys(node['layout'], ('aspectRatio','overflow','horizontal','vertical'), path+'/layout')
        keys(node['source'], ('format','sourceId','fileName','path','slideNumber'), path+'/source')
        keys(node['accessibility'], ('label','description','role'), path+'/accessibility')
        keys(node['pluginData'], ('portalGeometry','contentViewport','scaleMode','state'), path+'/pluginData')
        kind, content = node['type'], node['content']
        if kind == 'html':
            keys(content, ('markup','role','textEditable','assetIds'), path+'/content', ('markup','role','textEditable','assetIds'))
            require(type(content['textEditable']) is bool and isinstance(content['assetIds'],list), path+': invalid HTML metadata')
        elif kind == 'embed':
            keys(content, ('bundleId','entryPoint'), path+'/content', ('bundleId','entryPoint'))
            metadata = document['embeds'].get(content['bundleId'])
            require(metadata and content['entryPoint'] == metadata['entryPoint'], path+': embed entry point mismatch')
        elif kind == 'frame':
            keys(content, ('role','background'), path+'/content')
            if 'background' in content:
                keys(content['background'], ('assetId',), path+'/content/background', ('assetId',))
                require(content['background']['assetId'] in document['assets'], path+': missing background asset')
        elif kind == 'component':
            keys(content, ('role',), path+'/content', ('role',))
            require(content['role'] == 'card', path+': unsupported component role')
        else:
            keys(content, (), path+'/content')
        if kind == 'frame' and content.get('role') == 'card-panel':
            require(node['layout'].get('aspectRatio') == 'locked' and node['layout'].get('overflow') == 'hidden', path+': invalid panel layout')
            require(node['pluginData'].get('scaleMode') == 'uniform', path+': panel scaleMode must be uniform')
            geometry(node['pluginData'].get('portalGeometry'), path+'/pluginData/portalGeometry', True)
            viewport = node['pluginData'].get('contentViewport')
            keys(viewport, ('width','height'), path+'/pluginData/contentViewport', ('width','height'))
            require(all(type(v) in (int,float) and math.isfinite(v) and v>0 for v in viewport.values()), path+': invalid panel viewport')
    for key, slide in document['slides'].items():
        require((slide.get('pagePresetId') or document['defaultPagePresetId']) in document['pagePresets'], f'/slides/{key}: missing page preset')
        require(slide['transitionId'] is None and slide['sectionId'] is None, f'/slides/{key}: unsupported section/transition')
    for key, record in document['interactions'].items():
        path = '/interactions/' + key
        keys(record['trigger'], ('type',), path+'/trigger', ('type',))
        require(record['trigger']['type'] in ('click','hover'), path+': unsupported trigger')
        require(record['conditions'] == [], path+': unsupported native conditions')
        require(isinstance(record['actions'],list) and record['actions'], path+': action required')
        for action in record['actions']:
            kind = action.get('type')
            require(kind in ('show','hide','toggle','openPortal','closePortal','goto','next','previous','selectTab'), path+': unsupported action '+str(kind))
            if kind in ('next','previous'):
                keys(action, ('type',), path+'/actions')
            elif kind == 'goto':
                keys(action, ('type','slideId'), path+'/actions', ('type','slideId'))
                require(action['slideId'] in document['slides'], path+': missing target slide')
            elif kind == 'selectTab':
                keys(action, ('type','groupId','targetId','panels','tabs','index','colors'), path+'/actions', ('type','groupId','targetId','panels','tabs','index'))
                require(isinstance(action['panels'],list) and isinstance(action['tabs'],list) and len(action['panels'])==len(action['tabs'])>0, path+': invalid tab arrays')
                require(type(action['index']) is int and 0<=action['index']<len(action['tabs']), path+': invalid tab index')
                require(all(x in nodes for x in [action['groupId'],action['targetId']]+action['panels']+action['tabs']), path+': missing tab target')
            else:
                keys(action, ('type','targetId','kind','geometry'), path+'/actions', ('type',) if kind=='closePortal' else ('type','targetId'))
                if 'targetId' in action:
                    require(action['targetId'] in nodes, path+': missing target node')
                if 'geometry' in action:
                    geometry(action['geometry'], path+'/actions/geometry', True)
                if 'kind' in action:
                    require(action['kind'] in ('card','fullscreen'), path+': unsupported portal kind')
    for key, meta in document['embeds'].items():
        require(meta['sandboxProfile']=='spicy-html-v1' and meta['bridgeVersion']==1 and meta['permissions']==[], '/embeds/'+key+': unsupported bridge/sandbox/permissions')
        require(meta['files'] and len(meta['files'])==len(set(meta['files'])) and meta['entryPoint'] in meta['files'], '/embeds/'+key+': invalid file list')
        for file in meta['files']:
            require(isinstance(file,str) and '\\' not in file and all(p not in ('','.','..') for p in file.split('/')), '/embeds/'+key+': unsafe file path')

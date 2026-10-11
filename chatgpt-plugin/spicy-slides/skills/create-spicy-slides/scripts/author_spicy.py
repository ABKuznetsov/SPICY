"""Generate the fixed native format from a small design spec; never ask GPT to invent native records."""
import argparse
import copy
from datetime import datetime, timezone
import hashlib
import html
import json
from pathlib import Path
import uuid
from package_spicy import build, verify_archive, resource
from strict_contract import keys, loads, require, geometry
from widget_contract import validate_widget

BASE=Path(__file__).parent.parent
def uid(prefix):return prefix+'-'+uuid.uuid4().hex
def esc(value):return html.escape(str(value),quote=True)

def author(spec, resources):
    keys(spec,('title','language','slides'),'/design',('title','slides'))
    require(isinstance(spec['title'],str) and isinstance(spec['slides'],list) and spec['slides'],'Design needs a title and slides')
    doc=loads((BASE/'assets/starter.json').read_text())
    prototype=copy.deepcopy(doc['nodes']['caption'])
    for table in ('slides','scenes','nodes','interactions','animations','assets','embeds'):doc[table]={}
    doc['slideOrder']=[];doc['documentId']=uid('document')
    now=datetime.now(timezone.utc).isoformat().replace('+00:00','Z')
    doc['metadata']={'title':spec['title'],'description':'','language':spec.get('language','ru'),'createdAt':now,'modifiedAt':now}
    payload={};outline={'version':1,'rootIds':['block-main'],'nodes':{'block-main':{'id':'block-main','type':'block','name':spec['title'],'color':'#2f7d8c','children':[]}}};doc['settings']={'presentationOutline':outline}
    def node(kind,parent,box,content=None):
        value=copy.deepcopy(prototype);value.update(id=uid(kind),type=kind,name=kind,parentId=parent,children=[],geometry=box,style={},layout={},content=content or {},interactionIds=[],animationIds=[],pluginData={},source={},accessibility={})
        doc['nodes'][value['id']]=value
        if parent:doc['nodes'][parent]['children'].append(value['id'])
        return value
    def add(items,parent):
        require(isinstance(items,list),'objects must be an array')
        for item in items:
            keys(item,('kind','name','x','y','width','height','rotation','text','markup','fontSize','color','background','borderColor','borderWidth','radius','path','event','panel'),'/design/object',('kind','x','y','width','height'))
            kind=item['kind'];require(kind in ('text','box','image','widget','card'), 'Unsupported design kind: '+str(kind))
            common=('kind','name','x','y','width','height','rotation')
            specific={'text':('text','markup','fontSize','color'),'box':('background','borderColor','borderWidth','radius'),'image':('path',),'widget':('path',),'card':('text','event','panel')}
            keys(item,common+specific[kind],'/design/'+kind,('kind','x','y','width','height')+({'image':('path',),'widget':('path',),'card':('panel',)}.get(kind,())))
            box={key:item.get(key,0) for key in ('x','y','width','height','rotation')};geometry(box,'/design/geometry',True)
            if kind=='widget':
                data=resource(resources,item['path']);config=validate_widget(data.decode('utf-8'));require(bool(config['model']),'Configure the widget before inserting it in a presentation');bundle=uid('widget')
                doc['embeds'][bundle]={'id':bundle,'entryPoint':'index.html','files':['index.html'],'sandboxProfile':'spicy-html-v1','bridgeVersion':1,'permissions':[]}
                payload['embeds/'+bundle+'/index.html']=data
                value=node('embed',parent,box,{'bundleId':bundle,'entryPoint':'index.html'});value['name']=config['name'];continue
            if kind=='card':
                component=node('component',parent,box,{'role':'card'});trigger=node('html',component['id'],{**box,'x':0,'y':0},{'role':'card-trigger','textEditable':True,'assetIds':[],'markup':'<div style="width:100%;height:100%;box-sizing:border-box;background:#dcecf2;border:2px solid #2f7d8c;border-radius:16px;padding:20px;font:28px Arial">'+esc(item.get('text','Подробнее'))+'</div>'})
                panel=item['panel'];keys(panel,('x','y','width','height','objects'),'/design/panel',('x','y','width','height','objects'))
                portal={k:panel.get(k,0) for k in ('x','y','width','height','rotation')};geometry(portal,'/design/panel',True)
                frame=node('frame',component['id'],{**portal,'x':0,'y':0},{'role':'card-panel'});frame['visible']=False;frame['layout']={'aspectRatio':'locked','overflow':'hidden'};frame['style']={'backgroundColor':'#ffffff','borderColor':'#2f7d8c','borderRadius':16,'borderWidth':2,'borderStyle':'solid'};frame['pluginData']={'contentViewport':{'width':portal['width'],'height':portal['height']},'portalGeometry':portal,'scaleMode':'uniform'}
                event=item.get('event','click');require(event in ('click','hover'),'Card event must be click or hover');iid=uid('interaction');trigger['interactionIds']=[iid]
                doc['interactions'][iid]={'id':iid,'ownerNodeId':trigger['id'],'trigger':{'type':event},'conditions':[],'enabled':True,'actions':[{'type':'show' if event=='hover' else 'openPortal','targetId':frame['id'],'kind':'card','geometry':portal}]};add(panel['objects'],frame['id']);continue
            if kind=='image':
                data=resource(resources,item['path']);digest=hashlib.sha256(data).hexdigest();suffix=Path(item['path']).suffix.lower();mime={'.png':'image/png','.jpg':'image/jpeg','.jpeg':'image/jpeg','.svg':'image/svg+xml','.webp':'image/webp'}.get(suffix);require(mime is not None,'Unsupported image type')
                file='assets/'+digest+suffix;doc['assets'][digest]={'id':digest,'path':file,'mimeType':mime,'size':len(data),'sha256':digest,'name':Path(item['path']).name};payload[file]=data
                content={'role':'image','textEditable':False,'assetIds':[digest],'markup':f'<img src="spicy-asset://{digest}" alt="{esc(item.get("name",""))}" style="width:100%;height:100%;object-fit:contain;display:block">'}
            elif kind=='text':
                size=item.get('fontSize',32);require(type(size) in (int,float) and 1<=size<=300,'Invalid fontSize');color=item.get('color','#15324a');require(isinstance(color,str) and __import__('re').fullmatch(r'#[0-9a-fA-F]{3,8}',color),'Color must be hex')
                markup=item.get('markup',esc(item.get('text','')).replace('\n','<br>'))
                content={'role':'text','textEditable':True,'assetIds':[],'markup':f'<div style="width:100%;height:100%;box-sizing:border-box;font:{size}px/1.2 Arial,sans-serif;color:{color}">{markup}</div>'}
            else:
                background=item.get('background','#eef4f6');border=item.get('borderColor','#94afc6');width=item.get('borderWidth',2);radius=item.get('radius',16)
                require(all(isinstance(c,str) and __import__('re').fullmatch(r'#[0-9a-fA-F]{3,8}',c) for c in (background,border)),'Box colors must be hex')
                require(all(type(n) in (int,float) and 0<=n<=300 for n in (width,radius)),'Invalid box border/radius')
                content={'role':'shape','textEditable':False,'assetIds':[],'markup':f'<div style="width:100%;height:100%;box-sizing:border-box;background:{background};border:{width}px solid {border};border-radius:{radius}px"></div>'}
            value=node('html',parent,box,content);value['name']=item.get('name',item.get('text',kind))
    for slide in spec['slides']:
        keys(slide,('title','notes','objects'),'/design/slide',('title','objects'))
        root=node('frame',None,{'x':0,'y':0,'width':1600,'height':900,'rotation':0});root['style']={'background':'#ffffff','overflow':'hidden'}
        sid,cid=uid('slide'),uid('scene');doc['slides'][sid]={'id':sid,'name':slide['title'],'sceneId':cid,'hidden':False,'notes':slide.get('notes',''),'sectionId':None,'transitionId':None,'pagePresetId':doc['defaultPagePresetId']};doc['scenes'][cid]={'id':cid,'rootNodeId':root['id']};doc['slideOrder'].append(sid)
        oid=uid('outline');outline['nodes'][oid]={'id':oid,'type':'slide','slideId':sid};outline['nodes']['block-main']['children'].append(oid);add(slide['objects'],root['id'])
    return doc,payload

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('design',type=Path);parser.add_argument('output',type=Path);parser.add_argument('--resource-root',type=Path,default=Path.cwd());args=parser.parse_args()
    doc,resources=author(loads(args.design.read_text()),args.resource_root.resolve())
    import tempfile
    with tempfile.TemporaryDirectory() as temporary:
        root=Path(temporary)
        for path,data in resources.items():target=root/path;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
        data=build(doc,root)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with args.output.open('xb') as handle:handle.write(data)
    print(json.dumps({'output':str(args.output.resolve()),'bytes':len(data),**verify_archive(args.output.read_bytes())},ensure_ascii=False))
if __name__=='__main__':main()

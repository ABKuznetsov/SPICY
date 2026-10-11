"""Create a self-contained CIF authoring widget; optional Node parses a supplied CIF."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import uuid
import re
from widget_contract import config_json, validate_widget, validate_javascript

ASSETS=Path(__file__).parents[2]/'create-spicy-widget/assets'
def main():
    from verify_contract import verify
    verify()
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('output',type=Path);p.add_argument('--cif',type=Path);p.add_argument('--node',default=shutil.which('node'));p.add_argument('--config',type=Path);args=p.parse_args()
    config={'schemaVersion':1,'widgetId':'widget-'+uuid.uuid4().hex,'name':'Кристаллическая структура','model':{},'state':{},'source':{}}
    if args.config:
        from strict_contract import loads
        config=loads(args.config.read_text())
    if args.cif:
        if not args.node:raise ValueError('CIF preprocessing needs Node; alternatively generate the authoring HTML and open the CIF in it.')
        code='const fs=require("fs"),parser=require(process.argv[1]);process.stdout.write(JSON.stringify(parser.parse(fs.readFileSync(process.argv[2],"utf8"))));'
        result=subprocess.run([args.node,'-e',code,str(ASSETS/'cif-viewer.js'),str(args.cif.resolve())],capture_output=True,text=True,check=True)
        config.update(name=args.cif.name,model=json.loads(result.stdout),source={'format':'cif','name':args.cif.name})
    replacements={'CONFIG':config_json(config),'RUNTIME':(ASSETS/'cif-viewer.js').read_text().replace('</script','<\\/script')}
    source=re.sub(r'__SPICY_(CONFIG|RUNTIME)__',lambda match:replacements[match[1]],(ASSETS/'cif-widget.html').read_text())
    validate_widget(source)
    if args.node:validate_javascript(source,args.node)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with args.output.open('x') as file:file.write(source)
    print(json.dumps({'output':str(args.output.resolve()),'verified':True,'configured':bool(config['model']),'atoms':len(config['model'].get('atoms',[]))},ensure_ascii=False))
if __name__=='__main__':main()

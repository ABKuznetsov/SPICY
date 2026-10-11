"""A widget is one offline HTML document; its data never extends the .spicy schema."""
from html.parser import HTMLParser
import json
import re
from strict_contract import require, keys, loads, identifier

class WidgetHTML(HTMLParser):
    def __init__(self):
        super().__init__(); self.counts={}; self.scripts=[]; self.script=None; self.styles=[]; self.style=None
    def handle_starttag(self, tag, attrs):
        self.counts[tag]=self.counts.get(tag,0)+1; attrs=dict(attrs)
        if 'style' in attrs:self.styles.append(attrs['style'])
        if tag=='style':self.style=[]
        require(tag not in ('iframe','object','embed','base'), f'Widget: unsupported tag {tag}')
        for name in ('src','href','poster','srcset'):
            if name in attrs:
                require(attrs[name].startswith(('data:','#')), f'Widget: external or unresolved resource {attrs[name]}')
        if tag=='script':
            require('src' not in attrs and attrs.get('type')!='module', 'Widget: scripts must be inline classic JS')
            self.script={'attrs':attrs,'text':''}; self.scripts.append(self.script)
    def handle_data(self, text):
        if self.script is not None:self.script['text']+=text
        if self.style is not None:self.style.append(text)
    def handle_endtag(self, tag):
        if tag=='script':self.script=None
        if tag=='style' and self.style is not None:self.styles.append(''.join(self.style));self.style=None

def validate_widget(source):
    require(isinstance(source,str), 'Widget: UTF-8 HTML required')
    html=WidgetHTML(); html.feed(source); html.close()
    require(all(html.counts.get(tag)==1 for tag in ('html','head','body')), 'Widget: exactly one html/head/body required')
    require(len(re.findall(r'</body\s*>',source,re.I))==1, 'Widget: escape </body> strings inside JavaScript')
    for css in html.styles:
        require(not re.search(r'@import\b',css,re.I),'Widget: no CSS imports')
        for url in re.findall(r'url\(\s*([^)]*)\)',css,re.I):
            require(url.strip().strip('\"\x27').startswith(('data:','#')),'Widget: no external CSS resources')
    configs=[script for script in html.scripts if script['attrs'].get('id')=='spicy-widget-config']
    require(len(configs)==1 and configs[0]['attrs'].get('type')=='application/json','Widget: missing spicy-widget-config JSON')
    config=loads(configs[0]['text'])
    keys(config, ('schemaVersion','widgetId','name','model','state','source'), '/widget-config', ('schemaVersion','widgetId','name','model','state','source'))
    require(config['schemaVersion']==1, 'Widget: unsupported configuration version');identifier(config['widgetId'],'/widget-config/widgetId')
    require(isinstance(config['name'],str) and isinstance(config['model'],dict) and isinstance(config['state'],dict) and isinstance(config['source'],dict),'Widget: invalid configuration')
    for script in html.scripts:
        if script['attrs'].get('type')=='application/json':continue
        require(not re.search(r'\b(?:fetch\s*\(|import\s*\(|importScripts\s*\(|XMLHttpRequest\b|WebSocket\b|Worker\s*\()',script['text']), 'Widget: runtime network/module dependencies are not allowed')
    return config

def config_json(config):
    return json.dumps(config,ensure_ascii=False,allow_nan=False,separators=(',',':')).replace('<','\\u003c')

def validate_javascript(source, node):
    import subprocess
    parser=WidgetHTML();parser.feed(source);parser.close()
    scripts=[item['text'] for item in parser.scripts if item['attrs'].get('type')!='application/json']
    code='const fs=require("fs"),vm=require("vm");for(const source of JSON.parse(fs.readFileSync(0,"utf8")))new vm.Script(source);'
    subprocess.run([node,'-e',code],input=json.dumps(scripts),capture_output=True,text=True,check=True)
    return len(scripts)

if __name__=='__main__':
    import argparse
    from pathlib import Path
    p=argparse.ArgumentParser();p.add_argument('html',type=Path);args=p.parse_args()
    c=validate_widget(args.html.read_text(encoding='utf-8'))
    print(json.dumps({'verified':True,'widgetId':c['widgetId'],'name':c['name']},ensure_ascii=False))

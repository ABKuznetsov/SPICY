(function(root){
 'use strict';
 const fail=message=>{throw Error(message);};
 function tokens(source){
  if(source.length>8000000)fail('CIF слишком большой для этого виджета. Используйте файл без таблицы отражений.');
  const out=[];let i=0;
  while(i<source.length){
   if(/\s/.test(source[i])){i++;continue;}if(source[i]==='#'){while(i<source.length&&source[i]!=='\n')i++;continue;}
   if(source[i]===';'&&(i===0||source[i-1]==='\n')){const start=++i;let end=source.indexOf('\n;',i);if(end<0)fail('Незакрытый текстовый блок CIF');out.push({v:source.slice(start,end),q:true});i=end+2;continue;}
   if(source[i]==='"'||source[i]==="'"){const quote=source[i++],start=i;while(i<source.length&&!(source[i]===quote&&(i+1===source.length||/\s/.test(source[i+1]))))i++;if(i===source.length)fail('Незакрытая строка CIF');out.push({v:source.slice(start,i++),q:true});continue;}
   const start=i;while(i<source.length&&!/\s/.test(source[i]))i++;out.push({v:source.slice(start,i),q:false});
  }return out;
 }
 const num=value=>{const s=String(value??'').replace(/\(\d+\)$/,'');if(!/^[+-]?(?:\d+\.?\d*|\.\d+)(?:[Ee][+-]?\d+)?$/.test(s))fail('Недопустимое число CIF: '+value);const n=Number(s);if(!Number.isFinite(n))fail('Недопустимое число');return n;};
 function operation(expression,xyz){
  const s=expression.replace(/\s/g,'').toLowerCase(),parts=s.match(/[+-]?(?:[xyz]|\d+(?:\/\d+)?)/g)||[];
  if(parts.join('')!==s)fail('Неподдерживаемая операция симметрии: '+expression);
  return parts.reduce((sum,part)=>{const sign=part[0]==='-'?-1:1,v=part.replace(/^[+-]/,'');if(/^[xyz]$/.test(v))return sum+sign*xyz['xyz'.indexOf(v)];const [a,b='1']=v.split('/').map(Number);if(!b)fail('Деление на ноль в симметрии');return sum+sign*a/b;},0);
 }
 const cart=(f,basis)=>[0,1,2].map(k=>f.reduce((sum,x,i)=>sum+x*basis[i][k],0));
 function parse(source){
  const ts=tokens(source),scalar={},loops=[];let i=0,blocks=0;
  const control=t=>t&&!t.q&&(/^(?:loop_|stop_|save_|data_)/i.test(t.v)||t.v.startsWith('_'));
  while(i<ts.length){const t=ts[i++];if(!t.q&&/^data_/i.test(t.v)){if(++blocks>1)fail('В CIF несколько блоков данных. Выберите один блок.');continue;}
   if(!t.q&&t.v.toLowerCase()==='loop_'){const tags=[];while(i<ts.length&&!ts[i].q&&ts[i].v.startsWith('_'))tags.push(ts[i++].v.toLowerCase());if(!tags.length)fail('Пустой заголовок loop_');const values=[];while(i<ts.length&&!control(ts[i]))values.push(ts[i++].v);if(values.length%tags.length)fail('Неполная строка loop_');const rows=[];for(let j=0;j<values.length;j+=tags.length)rows.push(Object.fromEntries(tags.map((tag,k)=>[tag,values[j+k]])));loops.push(rows);continue;}
   if(!t.q&&t.v.startsWith('_')){if(!ts[i]||control(ts[i]))fail('Отсутствует значение '+t.v);scalar[t.v.toLowerCase()]=ts[i++].v;}
  }
  const cell=['_cell_length_a','_cell_length_b','_cell_length_c','_cell_angle_alpha','_cell_angle_beta','_cell_angle_gamma'].map(tag=>num(scalar[tag]));
  if(cell.slice(0,3).some(x=>x<=0)||cell.slice(3).some(x=>x<=0||x>=180))fail('Недопустимая ячейка');
  const [a,b,c,ad,bd,gd]=cell,rad=Math.PI/180,ca=Math.cos(ad*rad),cb=Math.cos(bd*rad),cg=Math.cos(gd*rad),sg=Math.sin(gd*rad),cy=(ca-cb*cg)/sg,cz2=1-cb*cb-cy*cy;
  if(cz2<=0||Math.abs(sg)<1e-10)fail('Вырожденная ячейка');const basis=[[a,0,0],[b*cg,b*sg,0],[c*cb,c*cy,c*Math.sqrt(cz2)]];
  const symmetry=loops.flat().map(row=>row._space_group_symop_operation_xyz||row._symmetry_equiv_pos_as_xyz).filter(Boolean);
  if(!symmetry.length){if(String(scalar._space_group_it_number||scalar._symmetry_int_tables_number)!=='1')fail('Нет явных операций симметрии; расширение по имени группы не выполняется.');symmetry.push('x,y,z');}
  const sites=loops.flat().filter(row=>row._atom_site_fract_x!==undefined);if(!sites.length)fail('Нет дробных координат атомов');const atoms=[],seen=new Set();
  for(const site of sites){const element=String(site._atom_site_type_symbol||site._atom_site_label||'').match(/^[A-Z][a-z]?/)?.[0];if(!element)fail('Нет типа атома');const occupancy=site._atom_site_occupancy===undefined?1:num(site._atom_site_occupancy);if(occupancy!==1)fail('Частичные заполнения и разупорядочение пока требуют отдельной модели.');const f=['x','y','z'].map(k=>num(site['_atom_site_fract_'+k]));
   for(const op of symmetry){const expressions=op.split(',');if(expressions.length!==3)fail('Неверная операция симметрии');const frac=expressions.map(e=>{const n=((operation(e,f)%1)+1)%1;return Math.abs(n-1)<1e-6||n<1e-6?0:n;});const key=element+':'+frac.map(x=>x.toFixed(5)).join(',');if(seen.has(key))continue;seen.add(key);atoms.push({element,label:site._atom_site_label||element,frac,position:cart(frac,basis)});}
  }
  if(atoms.length>512)fail('Более 512 атомов в ячейке: используйте специализированный виджет');
  return{cell,basis,atoms,symmetryCount:symmetry.length,spaceGroup:scalar['_space_group_name_h-m_alt']||scalar['_symmetry_space_group_name_h-m']||''};
 }
 const api={parse,operation,cart};if(typeof module!=='undefined'&&module.exports)module.exports=api;root.SpicyCif=api;
 if(!root.document)return;
 const $=id=>document.getElementById(id),config=JSON.parse($('spicy-widget-config').textContent),canvas=$('structure'),ctx=canvas.getContext('2d');
 const defaults={atoms:true,bonds:true,cell:true,cutoff:2.7,atomSize:5,rotationX:-.4,rotationY:.6,zoom:1,elements:{}};
 let state={...defaults,...config.state},model=config.model,drag=null,contacts=[];const initial=()=>({...defaults,...config.state,elements:{...(config.state.elements||{})}});
 const color=element=>'hsl('+([...element].reduce((sum,c)=>sum+c.charCodeAt(0)*41,0)%360)+' 60% 48%)';
 function rebuild(){contacts=[];for(let a=0;a<(model.atoms||[]).length;a++)for(let b=a+1;b<model.atoms.length;b++){const p=model.atoms[a].position,q=model.atoms[b].position,d=Math.hypot(...p.map((v,k)=>v-q[k]));if(d>.1&&d<=state.cutoff)contacts.push([a,b]);}}
 function update(){
  $('name').textContent=config.name;$('message').textContent=model.atoms?.length?`${model.atoms.length} атомов · ${model.symmetryCount} операций · ${model.spaceGroup} · связи по расстоянию ≤ ${state.cutoff} Å`:'Откройте CIF, настройте вид и сохраните виджет для вставки.';
  for(const key of ['atoms','bonds','cell'])$(key).classList.toggle('active',state[key]);$('cutoff').value=state.cutoff;$('atomSize').value=state.atomSize;
  $('elements').replaceChildren();for(const element of [...new Set((model.atoms||[]).map(a=>a.element))]){const b=document.createElement('button');b.textContent=element;b.style.color=color(element);b.classList.toggle('active',state.elements[element]!==false);b.onclick=()=>{state.elements[element]=state.elements[element]===false;update();};$('elements').append(b);}draw();
 }
 function draw(){
  const rect=canvas.getBoundingClientRect(),ratio=root.devicePixelRatio||1;canvas.width=Math.max(1,Math.round(rect.width*ratio));canvas.height=Math.max(1,Math.round(rect.height*ratio));ctx.setTransform(ratio,0,0,ratio,0,0);ctx.clearRect(0,0,rect.width,rect.height);if(!model.atoms?.length)return;
  const corners=[];for(let x=0;x<2;x++)for(let y=0;y<2;y++)for(let z=0;z<2;z++)corners.push(cart([x,y,z],model.basis));const center=cart([.5,.5,.5],model.basis),extent=Math.max(...corners.map(p=>Math.hypot(...p.map((x,i)=>x-center[i])))),scale=Math.min(rect.width,rect.height)*.35/Math.max(1,extent)*state.zoom;
  const project=pos=>{let[x,y,z]=pos.map((v,i)=>v-center[i]);const cx=Math.cos(state.rotationX),sx=Math.sin(state.rotationX),cy=Math.cos(state.rotationY),sy=Math.sin(state.rotationY);[y,z]=[y*cx-z*sx,y*sx+z*cx];[x,z]=[x*cy+z*sy,-x*sy+z*cy];return{x:rect.width/2+x*scale,y:rect.height/2-y*scale,z};};
  const line=(p,q,stroke,width)=>{const a=project(p),b=project(q);ctx.strokeStyle=stroke;ctx.lineWidth=width;ctx.beginPath();ctx.moveTo(a.x,a.y);ctx.lineTo(b.x,b.y);ctx.stroke();};
  if(state.cell)for(let i=0;i<8;i++)for(const step of [1,2,4])if(!(i&step))line(corners[i],corners[i|step],'#a3b8c5',1);
  const visible=a=>state.elements[a.element]!==false;
  if(state.bonds)for(const[a,b]of contacts)if(visible(model.atoms[a])&&visible(model.atoms[b]))line(model.atoms[a].position,model.atoms[b].position,'#8797a2',1.5);
  if(state.atoms)for(const item of model.atoms.filter(visible).map(atom=>({atom,...project(atom.position)})).sort((a,b)=>a.z-b.z)){ctx.fillStyle=color(item.atom.element);ctx.beginPath();ctx.arc(item.x,item.y,Number(state.atomSize),0,Math.PI*2);ctx.fill();ctx.strokeStyle='#ffffff';ctx.lineWidth=1;ctx.stroke();}
 }
 for(const key of ['atoms','bonds','cell'])$(key).onclick=()=>{state[key]=!state[key];update();};
 $('cutoff').oninput=event=>{state.cutoff=Number(event.target.value);rebuild();update();};$('atomSize').oninput=event=>{state.atomSize=Number(event.target.value);draw();};
 $('reset').onclick=()=>{state=initial();rebuild();update();};$('fullscreen').onclick=()=>{if(root.SpicyEmbedFullscreen){if(document.documentElement.dataset.spicyEmbedFullscreen==='true')root.SpicyEmbedFullscreen.close();else root.SpicyEmbedFullscreen.open();}else if(document.fullscreenElement)document.exitFullscreen?.();else document.documentElement.requestFullscreen?.();};
 canvas.onpointerdown=event=>{drag={x:event.clientX,y:event.clientY};canvas.setPointerCapture(event.pointerId);};canvas.onpointermove=event=>{if(!drag)return;state.rotationY+=(event.clientX-drag.x)*.01;state.rotationX+=(event.clientY-drag.y)*.01;drag={x:event.clientX,y:event.clientY};draw();};canvas.onpointerup=canvas.onpointercancel=()=>{drag=null;};canvas.onwheel=event=>{event.preventDefault();state.zoom=Math.max(.3,Math.min(4,state.zoom*Math.exp(-event.deltaY*.001)));draw();};
 $('cif').onchange=async event=>{try{const file=event.target.files[0];if(!file)return;model=parse(await file.text());config.name=file.name;config.source={format:'cif',name:file.name};state={...defaults,elements:{}};rebuild();update();}catch(error){$('message').textContent=error.message;}finally{event.target.value='';}};
 function exportHTML(){if(!model.atoms?.length)throw Error('Сначала откройте CIF.');const copy=document.documentElement.cloneNode(true),saved={...config,model,state:JSON.parse(JSON.stringify(state))};for(const host of copy.querySelectorAll('[data-spicy-plugin-host]'))host.remove();copy.querySelector('#spicy-widget-config').textContent=JSON.stringify(saved).replace(/</g,'\\u003c');copy.querySelector('#structure').removeAttribute('width');copy.querySelector('#structure').removeAttribute('height');return '<!doctype html>\n'+copy.outerHTML;}
 $('export').onclick=()=>{try{const blob=new Blob([exportHTML()],{type:'text/html'}),url=URL.createObjectURL(blob),link=document.createElement('a');link.href=url;link.download='structure-widget.html';link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}catch(error){$('message').textContent=error.message;}};
 if(root.SpicyPluginAuthor)root.SpicyPluginAuthor.exportHTML=exportHTML;
 if(root.parent!==root&&!root.SpicyPluginAuthor)$('author-controls').hidden=true;
 root.addEventListener('resize',draw);rebuild();update();
})(globalThis);

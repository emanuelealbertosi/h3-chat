/* Trusted, time-addressable SVG scenes. No generated code or wall-clock timers. */
(()=>{
 'use strict';
 const kinds=['group','rect','ellipse','line','path','text','bar','counter','image'],easings=['linear','easeIn','easeOut','easeInOut','step'];
 const ranges={x:[-32768,32768],y:[-32768,32768],scaleX:[0,8],scaleY:[0,8],rotation:[-7200,7200],opacity:[0,1],strokeWidth:[0,100],barValue:[-1e9,1e9],pathDraw:[0,1]};
 const defaults={x:0,y:0,scaleX:1,scaleY:1,rotation:0,opacity:1},fonts=['Manrope','Cormorant','BebasNeue','Baloo2','Caveat','Bangers'];
 const caches=new WeakMap(),ns='http://www.w3.org/2000/svg';
 function fail(path,message){throw Error('Motion Graphics · '+path+': '+message);}
 function fields(v,allowed,path){if(!v||typeof v!=='object'||Array.isArray(v)||Object.keys(v).some(k=>!allowed.includes(k)))fail(path,'oggetto o campi non validi');}
 function num(v,min,max,path){if(typeof v!=='number'||!Number.isFinite(v)||v<min||v>max)fail(path,'numero fuori intervallo');return v;}
 function color(v,path){if(typeof v!=='string'||!(v==='none'||/^#[0-9a-f]{6}$/i.test(v)))fail(path,'colore non valido');return v;}
 function id(v,path){if(typeof v!=='string'||!(/^[A-Za-z][A-Za-z0-9_-]{0,63}$/).test(v))fail(path,'identificativo non valido');}
 function svgPath(v,path){if(typeof v!=='string'||!v||v.length>12000)fail(path,'tracciato non valido');const re=/[MmLlHhVvCcSsQqTtAaZz]|[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?/g,tokens=v.match(re)||[],rest=v.replace(re,'').replace(/[\s,]/g,'');if(!tokens.length||!['M','m'].includes(tokens[0])||rest)fail(path,'tracciato non valido');const counts={M:2,L:2,H:1,V:1,C:6,S:4,Q:4,T:2,A:7,Z:0};let command=null,values=[];const check=()=>{const n=counts[command];if(!n&&values.length||n&&(!values.length||values.length%n))fail(path,'coordinate incomplete');if(command==='A')for(let i=0;i<values.length;i+=7)if(![0,1].includes(values[i+3])||![0,1].includes(values[i+4]))fail(path,'flag arco non valido');};for(const token of tokens)if(Object.hasOwn(counts,token.toUpperCase())){if(command!==null)check();command=token.toUpperCase();values=[];}else values.push(num(Number(token),-32768,32768,path));check();}
 function safeData(value){const stack=[[value,'scene',0,'']];let count=0;while(stack.length){const [item,path,depth,key]=stack.pop();if(++count>50000||depth>16)fail(path,'budget o profondità dei dati superati');if(item===null){if(key!=='parentId')fail(path,'valore nullo non consentito');}else if(Array.isArray(item)){item.forEach((v,i)=>stack.push([v,path+'['+i+']',depth+1,'']));}else if(typeof item==='object'){for(const [k,v] of Object.entries(item)){if(['__proto__','constructor','prototype'].includes(k))fail(path,'chiave non consentita');stack.push([v,path+'.'+k,depth+1,k]);}}else if(typeof item==='string'){if([...item].length>20000)fail(path,'stringa oltre il budget');if([...item].some(c=>c.codePointAt(0)>=0xD800&&c.codePointAt(0)<=0xDFFF))fail(path,'Unicode non valido');}else if(typeof item==='number'){if(!Number.isFinite(item))fail(path,'numero finito richiesto');}else if(typeof item!=='boolean')fail(path,'sono ammessi solo dati JSON');}}
 function validate(input){
  safeData(input);
  fields(input,['version','id','width','height','duration','background','objects','camera'],'scene');
  if(input.version!==2)fail('version','versione non supportata');id(input.id,'id');
  num(input.width,100,8192,'width');num(input.height,100,8192,'height');num(input.duration,.1,600,'duration');color(input.background,'background');
  if(!Array.isArray(input.objects)||input.objects.length<1||input.objects.length>256)fail('objects','da 1 a 256 oggetti, senza troncamento');
  const seen=new Map();
  for(const [i,o] of input.objects.entries()){
   const p='objects['+i+']';fields(o,['id','type','parentId','layer','width','height','anchor','transform','fill','stroke','strokeWidth','text','fontSize','fontFamily','path','value','maxValue','unit','tracks','visible','parallax','assetId','imageFit'],p);id(o.id,p+'.id');
   if(seen.has(o.id))fail(p+'.id','identificativo duplicato');seen.set(o.id,o);
   if(!kinds.includes(o.type))fail(p+'.type','primitiva non supportata');if(o.parentId!=null)id(o.parentId,p+'.parentId');
   if(o.type==='image'&&(!/^[0-9a-f]{32}$/.test(o.assetId||'')||!['contain','cover'].includes(o.imageFit??'contain')))fail(p+'.assetId','immagine autorizzata richiesta');
   num(o.layer??0,-1000,1000,p+'.layer');for(const a of ['width','height'])num(o[a],1,16384,p+'.'+a);
   num(o.parallax??1,0,2,p+'.parallax');if(o.parentId&&(o.parallax??1)!==1)fail(p+'.parallax','la parallasse si applica al gruppo principale');
   fields(o.anchor??{},['x','y'],p+'.anchor');for(const a of ['x','y'])num(o.anchor?.[a]??0,0,1,p+'.anchor.'+a);
   fields(o.transform??{},Object.keys(defaults),p+'.transform');for(const a of Object.keys(defaults))num(o.transform?.[a]??defaults[a],...ranges[a],p+'.transform.'+a);
   for(const a of ['fill','stroke'])color(o[a]??(a==='stroke'?'none':'#24C4D8'),p+'.'+a);num(o.strokeWidth??0,0,100,p+'.strokeWidth');
   if(typeof (o.visible??true)!=='boolean')fail(p+'.visible','booleano richiesto');if(!fonts.includes(o.fontFamily??'Manrope'))fail(p+'.fontFamily','font locale richiesto');num(o.fontSize??32,8,400,p+'.fontSize');
   for(const [a,n] of [['text',1200],['unit',30]])if(typeof (o[a]??'')!=='string'||[...(o[a]??'')].length>n)fail(p+'.'+a,'testo non valido');
   if(o.type==='path'||Object.hasOwn(o,'path'))svgPath(o.path,p+'.path');
   num(o.value??0,-1e9,1e9,p+'.value');num(o.maxValue??100,.000001,1e9,p+'.maxValue');
   if(!Array.isArray(o.tracks??[])||(o.tracks??[]).length>14)fail(p+'.tracks','tracce non valide');const props=new Set();
   for(const [j,tr] of (o.tracks??[]).entries()){
    const q=p+'.tracks['+j+']';fields(tr,['property','keyframes'],q);const prop=tr.property;
    if(![...Object.keys(ranges),'visible','fill','stroke','text'].includes(prop)||props.has(prop))fail(q+'.property','proprietà non valida o duplicata');props.add(prop);
    if(prop==='barValue'&&!['bar','counter'].includes(o.type)||prop==='pathDraw'&&o.type!=='path'||prop==='text'&&o.type!=='text')fail(q+'.property','proprietà incompatibile');
    if(!Array.isArray(tr.keyframes)||tr.keyframes.length<1||tr.keyframes.length>128)fail(q,'da 1 a 128 keyframe');let previous=-1;
    for(const [ki,k] of tr.keyframes.entries()){
     const kp=q+'.keyframes['+ki+']';fields(k,['t','value','ease'],kp);num(k.t,0,input.duration,kp+'.t');if(k.t<=previous)fail(kp+'.t','tempi strettamente crescenti');previous=k.t;
     if(!easings.includes(k.ease??'linear'))fail(kp+'.ease','easing non valido');
     if(prop in ranges)num(k.value,...ranges[prop],kp+'.value');else if(prop==='visible'){if(typeof k.value!=='boolean')fail(kp+'.value','booleano richiesto');}
     else if(['fill','stroke'].includes(prop))color(k.value,kp+'.value');else if(typeof k.value!=='string'||[...k.value].length>1200)fail(kp+'.value','testo non valido');
    }
   }
  }
  for(const o of input.objects){const chain=new Set([o.id]);let parent=o.parentId;while(parent!=null){if(!seen.has(parent)||seen.get(parent).type!=='group')fail(o.id+'.parentId','gruppo padre inesistente');if(chain.has(parent))fail(o.id+'.parentId','gerarchia ciclica');chain.add(parent);parent=seen.get(parent).parentId;}}
  if(new Set(input.objects.filter(o=>o.type==='image').map(o=>o.assetId)).size>12)fail('images','massimo dodici immagini distinte per scena');
  fields(input.camera??{},['keyframes'],'camera');const ck=input.camera?.keyframes??[];if(!Array.isArray(ck)||ck.length>128)fail('camera','keyframe non validi');let previous=-1;
  for(const [i,k] of ck.entries()){const p='camera.keyframes['+i+']';fields(k,['t','x','y','zoom','ease'],p);num(k.t,0,input.duration,p+'.t');if(k.t<=previous)fail(p+'.t','tempi strettamente crescenti');previous=k.t;num(k.x,-32768,32768,p+'.x');num(k.y,-32768,32768,p+'.y');num(k.zoom,.1,8,p+'.zoom');if(!easings.includes(k.ease??'linear'))fail(p+'.ease','easing non valido');}
  if(input.objects.reduce((n,o)=>n+(o.tracks??[]).reduce((m,t)=>m+t.keyframes.length,0),ck.length)>4096)fail('keyframes','massimo 4096 keyframe per scena');
  if(new TextEncoder().encode(JSON.stringify(input)).length>512000)fail('scene','budget scena superato');
  return JSON.parse(JSON.stringify(input));
 }
 function ease(p,name){return name==='step'?(p<1?0:1):name==='easeIn'?p*p:name==='easeOut'?1-(1-p)*(1-p):name==='easeInOut'?(p<.5?2*p*p:1-2*(1-p)*(1-p)):p;}
 function interpolate(a,b,p){
  if(typeof a==='number'&&typeof b==='number')return a+(b-a)*p;
  if(typeof a==='string'&&typeof b==='string'&&/^#[0-9a-f]{6}$/i.test(a)&&/^#[0-9a-f]{6}$/i.test(b))return '#'+[1,3,5].map(i=>Math.round(parseInt(a.slice(i,i+2),16)+(parseInt(b.slice(i,i+2),16)-parseInt(a.slice(i,i+2),16))*p).toString(16).padStart(2,'0')).join('');
  return p<1?a:b;
 }
 function at(keys,t,base){if(!keys.length)return base;if(t<keys[0].t)return keys[0].value;let left=keys[0];for(let i=1;i<keys.length;i++){const right=keys[i];if(t<right.t)return interpolate(left.value,right.value,ease((t-left.t)/(right.t-left.t),right.ease??'linear'));left=right;}return left.value;}
 function evaluateValidated(scene,seconds){
  const t=Math.min(scene.duration,Math.max(0,seconds));
  const objects=scene.objects.map(o=>{const state={...defaults,...o.transform,id:o.id,visible:o.visible??true,fill:o.fill??'#24C4D8',stroke:o.stroke??'none',strokeWidth:o.strokeWidth??0,text:o.text??'',barValue:o.value??0,pathDraw:1};for(const track of o.tracks??[])state[track.property]=at(track.keyframes,t,state[track.property]);return state;});
  const keys=scene.camera?.keyframes??[],camera={};for(const [prop,base] of [['x',scene.width/2],['y',scene.height/2],['zoom',1]])camera[prop]=at(keys.map(k=>({t:k.t,value:k[prop],ease:k.ease})),t,base);
  return {time:t,objects,camera};
 }
 function evaluateSceneAt(scene,seconds){if(typeof seconds!=='number'||!Number.isFinite(seconds))fail('time','tempo finito richiesto');return evaluateValidated(validate(scene),seconds);}
 function element(doc,tag,attrs={}){const e=doc.createElementNS(ns,tag);for(const [key,value] of Object.entries(attrs))e.setAttribute(key,String(value));return e;}
 function paintText(doc,node,content){
  const o=node.object,key=JSON.stringify([content,o.width,o.height,o.fontSize,o.fontFamily]);if(node.textKey===key)return;node.textKey=key;
  const context=doc.createElement('canvas').getContext('2d'),base=o.fontSize??32,family=o.fontFamily??'Manrope';let lines=[],size=base;
  const wrap=()=>{context.font=size+'px '+family;lines=[];for(const paragraph of String(content).split('\n')){let line='';for(const word of paragraph.split(/\s+/).filter(Boolean)){const candidate=line?line+' '+word:word;if(context.measureText(candidate).width<=o.width){line=candidate;continue;}if(line){lines.push(line);line='';}if(context.measureText(word).width<=o.width)line=word;else{for(const ch of [...word]){if(context.measureText(line+ch).width>o.width&&line){lines.push(line);line='';}line+=ch;}}}lines.push(line);}};
  wrap();while(lines.length*size*1.2>o.height&&size>Math.max(8,base*.7)){size=Math.max(8,base*.7,size-1);wrap();}
  if(lines.length*size*1.2>o.height+.1)fail(o.id,'testo oltre l’altezza dichiarata: aumenta lo spazio o riduci il contenuto');
  node.shape.replaceChildren(...lines.map((line,i)=>{const span=element(doc,'tspan',{x:0,y:size*(1+i*1.2)});span.textContent=line;return span;}));node.shape.setAttribute('font-size',size);
 }
 function mount(doc,input){
  const scene=validate(input),host=doc.querySelector('[data-h3-motion-root]')||doc.body;doc.documentElement.style.height='100%';doc.body.style.cssText+=';margin:0;height:100%;overflow:hidden';host.style.height='100%';host.replaceChildren();const svg=element(doc,'svg',{viewBox:'0 0 '+scene.width+' '+scene.height,width:'100%',height:'100%','aria-label':'Motion Graphics'});svg.style.display='block';
  svg.append(element(doc,'rect',{width:scene.width,height:scene.height,fill:scene.background}));const camera=element(doc,'g');svg.append(camera);const nodes=new Map();
  for(const o of scene.objects){const wrap=element(doc,'g',{'data-h3-motion-object':o.id});let shape;
   if(o.type==='image'){const assets=JSON.parse(doc.querySelector('[data-h3-motion-assets]')?.textContent||'{}'),url=assets[o.assetId];if(typeof url!=='string'||!/^data:image\/(png|jpeg|webp);base64,[A-Za-z0-9+/=]+$/.test(url))fail(o.id,'immagine incorporata non disponibile');shape=element(doc,'image',{width:o.width,height:o.height,href:url,preserveAspectRatio:o.imageFit==='cover'?'xMidYMid slice':'xMidYMid meet'});}
   else if(o.type==='rect'||o.type==='bar')shape=element(doc,'rect',{width:o.width,height:o.height});else if(o.type==='ellipse')shape=element(doc,'ellipse',{cx:o.width/2,cy:o.height/2,rx:o.width/2,ry:o.height/2});
   else if(o.type==='line')shape=element(doc,'line',{x1:0,y1:0,x2:o.width,y2:o.height});else if(o.type==='path')shape=element(doc,'path',{d:o.path});
   else if(o.type==='text'||o.type==='counter'){shape=element(doc,'text',{x:0,y:o.fontSize??32,'font-family':o.fontFamily??'Manrope','font-size':o.fontSize??32});shape.textContent=o.text??'';}
   if(shape)wrap.append(shape);nodes.set(o.id,{wrap,shape,object:o,pathLength:null});
  }
  for(const o of [...scene.objects].sort((a,b)=>(a.layer??0)-(b.layer??0)))(o.parentId?nodes.get(o.parentId).wrap:camera).append(nodes.get(o.id).wrap);
  host.append(svg);caches.set(doc,{scene,camera,nodes,svg});apply(doc,0);return svg;
 }
 function hasScene(doc){return caches.has(doc)||!!doc.querySelector?.('[data-h3-motion-scene]');}
 function ensure(doc){if(caches.has(doc))return caches.get(doc);const node=doc.querySelector('[data-h3-motion-scene]');if(!node)fail('scene','scena assente');mount(doc,JSON.parse(node.textContent));return caches.get(doc);}
 function apply(doc,seconds){
  if(typeof seconds!=='number'||!Number.isFinite(seconds))fail('time','tempo finito richiesto');const cache=ensure(doc),scene=cache.scene,state=evaluateValidated(scene,seconds);
  cache.camera.setAttribute('transform','translate('+scene.width/2+' '+scene.height/2+') scale('+state.camera.zoom+') translate('+(-state.camera.x)+' '+(-state.camera.y)+')');
  for(const s of state.objects){const n=cache.nodes.get(s.id),o=n.object,a=o.anchor??{x:0,y:0},factor=o.parentId?1:o.parallax??1,z=state.camera.zoom,k=Math.pow(z,factor-1),x=o.parentId?s.x:(s.x-scene.width/2-(state.camera.x-scene.width/2)*factor)*k+state.camera.x,y=o.parentId?s.y:(s.y-scene.height/2-(state.camera.y-scene.height/2)*factor)*k+state.camera.y;n.wrap.setAttribute('transform','translate('+x+' '+y+') rotate('+s.rotation+') scale('+(s.scaleX*k)+' '+(s.scaleY*k)+') translate('+(-(a.x??0)*o.width)+' '+(-(a.y??0)*o.height)+')');n.wrap.setAttribute('opacity',s.opacity);n.wrap.setAttribute('visibility',s.visible?'visible':'hidden');
   if(n.shape){n.shape.setAttribute('fill',s.fill);n.shape.setAttribute('stroke',s.stroke);n.shape.setAttribute('stroke-width',s.strokeWidth);
    if(o.type==='text')paintText(doc,n,s.text);else if(o.type==='counter'){const label=o.text??'',value=String(Math.round(s.barValue));paintText(doc,n,(/\{value\}/i.test(label)?label.replace(/\{value\}/gi,value):label+value)+(o.unit??''));}
    else if(o.type==='bar'){const p=Math.max(0,Math.min(1,s.barValue/(o.maxValue??100)));n.shape.setAttribute('y',o.height*(1-p));n.shape.setAttribute('height',o.height*p);}
    else if(o.type==='path'){if(n.pathLength===null)n.pathLength=n.shape.getTotalLength();n.shape.setAttribute('stroke-dasharray',n.pathLength);n.shape.setAttribute('stroke-dashoffset',n.pathLength*(1-s.pathDraw));}
   }
  }
  return state;
 }
 function checkTextBounds(doc,seconds){
  const state=apply(doc,seconds),cache=ensure(doc),byId=new Map(state.objects.map(o=>[o.id,o])),viewport=cache.svg.getBoundingClientRect(),errors=[],texts=[];
  for(const [id,node] of cache.nodes){if(!['text','counter'].includes(node.object.type))continue;let opacity=1,visible=true,current=node;
   while(current){const s=byId.get(current.object.id);opacity*=s.opacity;visible&&=s.visible;current=current.object.parentId?cache.nodes.get(current.object.parentId):null;}
   if(!visible||opacity<.95)continue;const rect=node.shape.getBoundingClientRect();if(rect.width<.1||rect.height<.1)continue;
   const x=(rect.left-viewport.left)*cache.scene.width/viewport.width,y=(rect.top-viewport.top)*cache.scene.height/viewport.height,w=rect.width*cache.scene.width/viewport.width,h=rect.height*cache.scene.height/viewport.height;
   if(x< -2||y< -2||x+w>cache.scene.width+2||y+h>cache.scene.height+2)errors.push(id+': testo fuori dal viewport a '+seconds.toFixed(2)+'s (x='+Math.round(x)+', y='+Math.round(y)+', larghezza='+Math.round(w)+', altezza='+Math.round(h)+'). Correggi coordinate locali e anchor del testo/gruppo o riserva spazio alla camera; non tagliare il testo.');
   for(const other of texts){const area=Math.max(0,Math.min(rect.right,other.rect.right)-Math.max(rect.left,other.rect.left))*Math.max(0,Math.min(rect.bottom,other.rect.bottom)-Math.max(rect.top,other.rect.top));if(area>Math.min(rect.width*rect.height,other.rect.width*other.rect.height)*.35)errors.push(id+' e '+other.id+': testi sovrapposti a '+seconds.toFixed(2)+'s. Sposta gli oggetti o unisci le tracce nello stesso oggetto, senza duplicare contatori o etichette.');}
   texts.push({id,rect});
  }
  if(errors.length)fail('layout',errors.slice(0,8).join(' '));return true;
 }
 async function prepare(doc,input){const scene=validate(input);if(doc.fonts?.load)await Promise.all([...new Set(scene.objects.filter(o=>['text','counter'].includes(o.type)).map(o=>o.fontFamily??'Manrope'))].map(name=>doc.fonts.load('32px '+name)));const images=scene.objects.filter(o=>o.type==='image');if(new Set(images.map(o=>o.assetId)).size>12)fail('images','massimo dodici immagini distinte per scena');const assets=JSON.parse(doc.querySelector('[data-h3-motion-assets]')?.textContent||'{}');await Promise.all([...new Set(images.map(o=>o.assetId))].map(async id=>{const url=assets[id];if(typeof url!=='string'||!/^data:image\/(png|jpeg|webp);base64,[A-Za-z0-9+/=]+$/.test(url))fail(id,'immagine incorporata non disponibile');const image=doc.createElement('img');image.src=url;await image.decode();}));const svg=mount(doc,scene);await Promise.all([...svg.querySelectorAll('image')].map(image=>new Promise((resolve,reject)=>{const timer=setTimeout(()=>reject(Error('Motion Graphics · caricamento immagine scaduto')),15000);image.onload=()=>{clearTimeout(timer);resolve();};image.onerror=()=>{clearTimeout(timer);reject(Error('Motion Graphics · immagine non decodificabile'));};})));return svg;}
 globalThis.H3SceneGraph={validate,evaluateSceneAt,mount,prepare,hasScene,apply,checkTextBounds,easings,kinds};
})();

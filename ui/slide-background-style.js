import {parseColor,colorHex} from './color-contrast.js';

export function validateBackgroundStyle(deck,media){
 if(deck.background_style==null)return null;
 if(typeof deck.background_style!=='object'||Array.isArray(deck.background_style)||Object.keys(deck.background_style).some(k=>!['base','decorations','set_id','asset_ids','opacity','veil'].includes(k)))throw Error('Sfondo della presentazione non valido.');
 const s={base:'plain',decorations:false,set_id:'',asset_ids:[],opacity:20,veil:'auto',...deck.background_style};
 if(!s||typeof s!=='object'||Array.isArray(s)||!['plain','gradient','collection'].includes(s.base)||typeof s.decorations!=='boolean'||!Number.isInteger(s.opacity)||s.opacity<5||s.opacity>45||!['auto','light','dark'].includes(s.veil)||!Array.isArray(s.asset_ids)||s.asset_ids.length>24||new Set(s.asset_ids).size!==s.asset_ids.length||s.asset_ids.some(id=>typeof id!=='string'||!/^[a-f0-9]{32}$/.test(id)))throw Error('Sfondo della presentazione non valido.');
 if(s.base==='collection'){
  if(typeof s.set_id!=='string'||!/^[a-f0-9]{32}$/.test(s.set_id)||!s.asset_ids.length||deck.pages.some(p=>!s.asset_ids.includes(p.background_asset_id)))throw Error('Assegnazione dello sfondo non valida.');
  if(media&&s.asset_ids.some(id=>!media.some(m=>m.id===id&&m.mime?.startsWith('image/'))))throw Error('Sfondo non disponibile negli allegati della presentazione.');
 }return s;
}

export function backgroundGeometry(deck,page,media,height){
 const s=validateBackgroundStyle(deck,media),asset=s?.base==='collection'?media.find(m=>m.id===page.background_asset_id):null;
 const box={x:0,y:0,width:1280,height};
 if(asset?.slide_background?.kind==='frame'){
  const [a,b]=String(asset.slide_background.format||deck.format).split(':').map(Number),fraction=Number(asset.slide_background.margin??12)/100;
  if(![a,b].every(n=>Number.isFinite(n)&&n>0)||!Number.isFinite(fraction)||fraction<.05||fraction>.25)throw Error('Margini della cornice non validi.');
  const fit=Math.min(1280/a,height/b),w=a*fit,h=b*fit;Object.assign(box,{x:(1280-w)/2+w*fraction,y:(height-h)/2+h*fraction,width:w*(1-2*fraction),height:h*(1-2*fraction)});
 }return {style:s,asset,box};
}
const images=new Map();
async function imageData(asset){
 if(typeof asset.offline_background_data==='string'&&/^data:image\/(png|jpeg|webp);base64,[A-Za-z0-9+/=]+$/.test(asset.offline_background_data))return asset.offline_background_data;
 if(!/^(uploads|outputs)\/[\w./-]+\.(png|jpg|jpeg|webp)$/i.test(asset.path)||asset.path.split('/').includes('..'))throw Error('Percorso sfondo non valido.');
 if(!images.has(asset.path)){
  const promise=fetch('/media/'+asset.path).then(r=>{if(!r.ok)throw Error('Sfondo non più disponibile.');return r.blob();}).then(blob=>new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(reader.result);reader.onerror=reject;reader.readAsDataURL(blob);}));
  images.set(asset.path,promise);promise.catch(()=>images.delete(asset.path));
 }return images.get(asset.path);
}
function important(element,values){for(const [key,value] of Object.entries(values))element.style.setProperty(key,String(value),'important');}
function tones(deck,style,asset,background){
 const parsed=parseColor(background),dark=style.veil==='dark'||style.veil==='auto'&&(asset?.slide_background?.tone==='dark'||deck.background==='dark'||deck.text_tone==='light'&&deck.background!=='light');
 const base=deck.background==='custom'&&/^#[a-f0-9]{6}$/i.test(deck.background_color||'')?deck.background_color:asset?(dark?'#17242b':'#fffefa'):parsed?.[3]>.95?colorHex(parsed):dark?'#17242b':'#fffefa';
 const accent=({natural:'#537c70',pastel:'#a7bad8',vivid:'#087f8c',neon:'#6850a1',monochrome:'#64748b'})[deck.palette]||({indigo:'#6850a1',sunset:'#b84944'})[deck.theme]||'#087f8c';
 return {base,accent,dark};
}
async function layer(doc,deck,page,media,height,background){
 const {style,asset,box}=backgroundGeometry(deck,page,media,height);if(!style)return null;
 const color=tones(deck,style,asset,background),node=doc.createElement('div');node.dataset.h3Trusted='';node.dataset.h3BackgroundLayer=style.base;node.setAttribute('aria-hidden','true');
 important(node,{all:'initial',display:'block',position:'absolute',left:'0',top:'0',width:'1280px',height:height+'px','z-index':'0',overflow:'hidden','pointer-events':'none','background-color':color.base});
 if(style.base==='gradient')important(node,{'background-image':`linear-gradient(135deg, ${color.base} 15%, ${color.accent}28 100%)`});
 if(asset){const img=doc.createElement('img');img.src=await imageData(asset);img.alt='';img.dataset.h3Trusted='';important(img,{position:'absolute',inset:'0',width:'100%',height:'100%','object-fit':'contain',opacity:style.opacity/100,margin:'0',padding:'0',border:'0','max-width':'none','max-height':'none'});node.append(img);}
 if(style.decorations){
  const ns='http://www.w3.org/2000/svg',svg=doc.createElementNS(ns,'svg');svg.setAttribute('viewBox',`0 0 1280 ${height}`);svg.setAttribute('aria-hidden','true');important(svg,{position:'absolute',inset:'0',width:'100%',height:'100%',opacity:'.35'});
  const border=doc.createElementNS(ns,'rect');for(const [key,value] of Object.entries({x:18,y:18,width:1244,height:height-36,rx:deck.design==='comic'?4:24,fill:'none',stroke:color.accent,'stroke-width':deck.design==='comic'?5:2}))border.setAttribute(key,String(value));svg.append(border);
  for(const [cx,cy,r] of [[22,22,42],[1258,height-22,52]]){const circle=doc.createElementNS(ns,'circle');for(const [key,value] of Object.entries({cx,cy,r,fill:color.accent,opacity:.2}))circle.setAttribute(key,String(value));svg.append(circle);}node.append(svg);
 }return {node,box,style,...color};
}

export async function applyHtmlBackground(doc,deck,page,media,height){
 if(!deck.background_style)return;
 const computed=doc.defaultView.getComputedStyle(doc.body),bodyLayout={};
 for(const property of ['display','padding','padding-left','padding-right','gap','align-items','justify-content','flex-direction','flex-wrap','grid-template-columns','grid-template-rows','align-content','font-family','font-size','line-height','color'])bodyLayout[property]=computed.getPropertyValue(property);
 const prepared=await layer(doc,deck,page,media,height,computed.backgroundColor);if(!prepared)return;
 const {node,box,style,base,dark}=prepared,content=doc.createElement('div');content.dataset.h3BackgroundContent='';
 important(content,{...bodyLayout,position:'absolute',left:box.x+'px',top:box.y+'px',width:box.width+'px',height:box.height+'px','min-width':'0','min-height':'0','max-width':box.width+'px','box-sizing':'border-box','z-index':'1',overflow:'visible'});
 if(style.base==='collection'){
  const [r,g,b]=parseColor(dark?'#17242b':'#fffefa');important(content,{'background-color':`rgba(${r},${g},${b},${1-style.opacity/100})`});
 }
 const roots=[...doc.body.children].filter(e=>!e.matches('style,[data-h3-trusted]'));
 for(const root of roots){
  const rect=root.getBoundingClientRect();
  const innerWidth=box.width-parseFloat(bodyLayout['padding-left']||0)-parseFloat(bodyLayout['padding-right']||0);
  if(rect.width>=1200||rect.width>innerWidth+1){important(root,{'width':'100%','max-width':'100%','min-width':'0','background':'transparent','box-shadow':'none'});}
  if(rect.height>=height*.85||rect.height>box.height)important(root,{'height':'100%','min-height':'0','max-height':'100%'});
  if(doc.defaultView.getComputedStyle(root).position==='fixed')important(root,{'position':'absolute'});
 }
 for(const child of [...doc.body.childNodes])if(child.nodeType!==1||child.tagName!=='STYLE')content.append(child);
 doc.body.append(node,content);
 important(doc.body,{display:'block',position:'relative',padding:'0',margin:'0',width:'1280px',height:height+'px','min-height':height+'px','background':base,overflow:'hidden'});
}

export async function applyDeclarativeBackground(frame,deck,page,media,height){
 if(!deck.background_style)return;
 const prepared=await layer(frame.ownerDocument,deck,page,media,height,getComputedStyle(frame).backgroundColor);if(!prepared)return;
 const {node,box,base,style,dark}=prepared;frame.style.background=base;frame.style.isolation='isolate';
 for(const child of frame.children){if(getComputedStyle(child).position==='static')child.style.position='relative';child.style.zIndex='1';}
 frame.prepend(node);
 if(style.base==='collection'){
  frame.style.paddingTop=box.y+28+'px';frame.style.paddingBottom=height-box.y-box.height+40+'px';frame.style.paddingLeft=box.x+28+'px';frame.style.paddingRight=1280-box.x-box.width+28+'px';
  const body=frame.querySelector('.h3-slide-body');body.style.background=dark?'#17242be6':'#fffefae6';
  for(const element of frame.querySelectorAll('.h3-slide-kicker,.h3-slide-footer')){element.style.left=box.x+28+'px';element.style.right=1280-box.x-box.width+28+'px';}
  frame.querySelector('.h3-slide-kicker').style.top=box.y+8+'px';frame.querySelector('.h3-slide-footer').style.bottom=height-box.y-box.height+8+'px';
 }
}

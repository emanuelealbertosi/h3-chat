import {parseColor,colorHex} from './color-contrast.js';
import {slideDecoration} from './slide-decoration.js';

export function validateBackgroundStyle(deck,media){
 if(deck.background_style==null)return null;
 if(typeof deck.background_style!=='object'||Array.isArray(deck.background_style)||Object.keys(deck.background_style).some(k=>!['base','decorations','set_id','asset_ids','opacity','veil'].includes(k)))throw Error('Sfondo della presentazione non valido.');
 const s={base:'plain',decorations:false,set_id:'',asset_ids:[],opacity:20,veil:'auto',...deck.background_style};
 if(!s||typeof s!=='object'||Array.isArray(s)||!['auto','plain','gradient','collection'].includes(s.base)||typeof s.decorations!=='boolean'||!Number.isInteger(s.opacity)||s.opacity<5||s.opacity>45||!['auto','light','dark'].includes(s.veil)||!Array.isArray(s.asset_ids)||s.asset_ids.length>24||new Set(s.asset_ids).size!==s.asset_ids.length||s.asset_ids.some(id=>typeof id!=='string'||!/^[a-f0-9]{32}$/.test(id)))throw Error('Sfondo della presentazione non valido.');
 if(s.base==='collection'){
  if(typeof s.set_id!=='string'||!/^[a-f0-9]{32}$/.test(s.set_id)||!s.asset_ids.length||deck.pages.some(p=>!s.asset_ids.includes(p.background_asset_id)))throw Error('Assegnazione dello sfondo non valida.');
  if(media&&s.asset_ids.some(id=>!media.some(m=>m.id===id&&m.mime?.startsWith('image/'))))throw Error('Sfondo non disponibile negli allegati della presentazione.');
 }return s.base==='auto'&&!s.decorations?null:s;
}

export function backgroundGeometry(deck,page,media,height){
 const s=validateBackgroundStyle(deck,media),asset=s?.base==='collection'?media.find(m=>m.id===page.background_asset_id):null;
 const box={x:0,y:0,width:1280,height};
 if(asset?.slide_background?.kind==='frame'){
  const [a,b]=String(asset.slide_background.format||deck.format).split(':').map(Number),fraction=Number(asset.slide_background.margin??12)/100;
  if(![a,b].every(n=>Number.isFinite(n)&&n>0)||!Number.isFinite(fraction)||fraction<.05||fraction>.25)throw Error('Margini della cornice non validi.');
  const fit=Math.min(1280/a,height/b),w=a*fit,h=b*fit;Object.assign(box,{x:(1280-w)/2+w*fraction,y:(height-h)/2+h*fraction,width:w*(1-2*fraction),height:h*(1-2*fraction)});
 }
 if(s?.decorations){const right=Math.min(1280-56,box.x+box.width),bottom=Math.min(height-56,box.y+box.height);box.x=Math.max(56,box.x);box.y=Math.max(56,box.y);box.width=right-box.x;box.height=bottom-box.y;}
 return {style:s,asset,box};
}
export function validateContentViewport(page,height){
 const value=page.content_viewport;if(value===undefined)return {width:1280,height};
 if(!value||typeof value!=='object'||Array.isArray(value)||Object.keys(value).some(k=>!['width','height'].includes(k))||!Number.isFinite(value.width)||!Number.isFinite(value.height)||value.width<=0||value.height<=0||value.width>1280||value.height>height)throw Error('Area interna della slide non valida.');
 return value;
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
 important(node,{all:'initial',display:'block',position:'absolute',left:'0',top:'0',width:'1280px',height:height+'px','z-index':'auto',overflow:'hidden','pointer-events':'none','background-color':style.base==='auto'?'transparent':color.base});
 if(style.base==='gradient')important(node,{'background-image':`linear-gradient(135deg, ${color.base} 15%, ${color.accent}28 100%)`});
 if(asset){const img=doc.createElement('img');img.src=await imageData(asset);img.alt='';img.dataset.h3Trusted='';important(img,{position:'absolute',inset:'0',width:'100%',height:'100%','object-fit':'contain',opacity:style.opacity/100,margin:'0',padding:'0',border:'0','max-width':'none','max-height':'none'});node.append(img);}
 if(style.decorations){
  const svg=slideDecoration(doc,deck,height,color.accent);important(svg,{position:'absolute',inset:'0',width:'100%',height:'100%','z-index':'2'});node.append(svg);
 }return {node,box,style,...color};
}

export async function applyHtmlBackground(doc,deck,page,media,height){
 if(!deck.background_style)return;
 const computed=doc.defaultView.getComputedStyle(doc.body),bodyLayout={};
 for(const property of ['display','padding','padding-left','padding-right','gap','align-items','justify-content','flex-direction','flex-wrap','grid-template-columns','grid-template-rows','align-content','font-family','font-size','line-height','color'])bodyLayout[property]=computed.getPropertyValue(property);
 const prepared=await layer(doc,deck,page,media,height,computed.backgroundColor);if(!prepared)return;
 const {node,box,style,base,dark}=prepared,content=doc.createElement('div'),canvas=doc.createElement('div');content.dataset.h3BackgroundContent='';canvas.dataset.h3ContentCanvas='';
 const viewport=validateContentViewport(page,height);canvas.dataset.h3ViewportWidth=String(viewport.width);canvas.dataset.h3ViewportHeight=String(viewport.height);
 important(content,{display:'block',position:'absolute',left:box.x+'px',top:box.y+'px',width:box.width+'px',height:box.height+'px','min-width':'0','min-height':'0','max-width':box.width+'px','box-sizing':'border-box','z-index':'1',overflow:'hidden',contain:'layout paint',padding:'0',margin:'0',border:'0'});
 important(canvas,{...bodyLayout,position:'absolute',left:'0',top:'0',width:viewport.width+'px',height:viewport.height+'px','box-sizing':'border-box',overflow:'visible',margin:'0',border:'0',background:'transparent',transform:'scale(1)','transform-origin':'0 0'});
 if(style.base==='collection'){
  const [r,g,b]=parseColor(dark?'#17242b':'#fffefa');important(content,{'background-color':`rgba(${r},${g},${b},${1-style.opacity/100})`});
 }
 const roots=[...doc.body.children].filter(e=>!e.matches('style,[data-h3-trusted]'));
 for(const root of roots){
  const rect=root.getBoundingClientRect();
  if(style.base!=='auto'&&rect.width>=viewport.width*.95&&rect.height>=viewport.height*.85)important(root,{background:'transparent','box-shadow':'none'});
 }
 // A full-page authored section can cover a transparent main. Clear only
 // page-sized surfaces when the app owns the base; local cards stay painted.
 if(style.base!=='auto')for(const element of roots.flatMap(root=>[root,...root.querySelectorAll('main,section,article,div')])){
  const rect=element.getBoundingClientRect();if(rect.width>=box.width*.95&&rect.height>=box.height*.95)important(element,{background:'transparent','box-shadow':'none'});
 }
 for(const child of [...doc.body.childNodes])if(child.nodeType!==1||child.tagName!=='STYLE')canvas.append(child);
 content.append(canvas);
 doc.body.append(node,content);
 important(doc.body,{display:'block',position:'relative',padding:'0',margin:'0',width:'1280px',height:height+'px','min-height':height+'px',...(style.base==='auto'?{}:{background:base}),overflow:'hidden'});
}

export async function applyDeclarativeBackground(frame,deck,page,media,height){
 if(!deck.background_style)return;
 const prepared=await layer(frame.ownerDocument,deck,page,media,height,getComputedStyle(frame).backgroundColor);if(!prepared)return;
 const {node,box,base,style,dark}=prepared;if(style.base!=='auto')frame.style.background=base;frame.style.isolation='isolate';
 for(const child of frame.children){if(getComputedStyle(child).position==='static')child.style.position='relative';child.style.zIndex='1';}
 frame.prepend(node);
 if(style.base==='collection'||style.decorations){
  frame.style.paddingTop=box.y+28+'px';frame.style.paddingBottom=height-box.y-box.height+40+'px';frame.style.paddingLeft=box.x+28+'px';frame.style.paddingRight=1280-box.x-box.width+28+'px';
  const body=frame.querySelector('.h3-slide-body');if(style.base==='collection')body.style.background=dark?'#17242be6':'#fffefae6';
  for(const element of frame.querySelectorAll('.h3-slide-kicker,.h3-slide-footer')){element.style.left=box.x+28+'px';element.style.right=1280-box.x-box.width+28+'px';}
  frame.querySelector('.h3-slide-kicker').style.top=box.y+8+'px';frame.querySelector('.h3-slide-footer').style.bottom=height-box.y-box.height+8+'px';
 }
}

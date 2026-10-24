import DOMPurify from 'dompurify';
import renderMath from 'katex/contrib/auto-render';
import {editHtmlSlide} from './slide-html-editing.js';
import {contentOverflows,fitMediaBounds} from './slide-html-bounds.js';
import {readableText} from './slide-html-contrast.js';
import {portraitLayout} from './infographic-layout.js';
import {initialExportStyles,applyExportStyles} from './export-style.js';
import '../static/infographic-motion.js';

const heights={'16:9':720,'9:16':1280*16/9,'4:3':960,'16:10':800,'1:1':1280};
const safePath=path=>/^(uploads|outputs)\/[\w./-]+\.(png|jpg|jpeg|webp)$/i.test(path);
const encode=deck=>'```h3-slides\n'+JSON.stringify(deck)+'\n```';
const sessions=new WeakMap();
const fontCache=new Map();
async function localFont(path){
  if(!fontCache.has(path))fontCache.set(path,fetch(path).then(r=>{if(!r.ok)throw Error('Font locale non disponibile.');return r.blob();}).then(blob=>new Promise(resolve=>{const reader=new FileReader();reader.onload=()=>resolve(reader.result);reader.readAsDataURL(blob);})));return fontCache.get(path);
}
let mathCSS;
async function localMathCSS(){
  mathCSS||=(async()=>{let css=await fetch('/static/vendor/katex.min.css').then(r=>r.text());const urls=[...new Set([...css.matchAll(/url\(([^)]+)\)/g)].map(m=>m[1].replace(/["']/g,'')).filter(x=>/^fonts\/KaTeX_[\w-]+\.woff2$/.test(x)))];const pairs=await Promise.all(urls.map(async x=>[x,await localFont('/static/vendor/'+x)]));const data=new Map(pairs);return css.replace(/url\(([^)]+)\)/g,(_,url)=>'url("'+(data.get(url.replace(/["']/g,''))||'data:font/woff;base64,')+'")');})();return mathCSS;
}

async function markup(page,media){
  const clean=DOMPurify.sanitize(page.html||'',{WHOLE_DOCUMENT:true,ADD_TAGS:['style'],FORBID_TAGS:['script','iframe','object','embed','link','meta','base','form','input','button','video','audio'],FORBID_ATTR:['srcset','action','formaction','autofocus','data-h3-editor','data-h3-trusted','data-h3-video']});
  const doc=new DOMParser().parseFromString(clean,'text/html');
  doc.querySelectorAll('a').forEach(a=>{a.removeAttribute('href');a.removeAttribute('target');});
  for(const image of doc.querySelectorAll('img')){
    const asset=media.find(m=>m.id===image.dataset.assetId&&m.mime.startsWith('image/')&&safePath(m.path));
    image.removeAttribute('src');
    if(!asset){image.remove();continue;}
    if(asset){const blob=await fetch('/media/'+asset.path).then(r=>{if(!r.ok)throw Error('Immagine slide non disponibile.');return r.blob();});image.src=await new Promise(resolve=>{const reader=new FileReader();reader.onload=()=>resolve(reader.result);reader.readAsDataURL(blob);});}
  }
  // CSS is authored by the model. The iframe's CSP blocks imports, URLs,
  // scripts and network even when a rule cannot be parsed during streaming.
  doc.querySelectorAll('svg image,use').forEach(n=>{for(const attr of ['href','xlink:href'])if(n.hasAttribute(attr)&&!n.getAttribute(attr).startsWith('#'))n.removeAttribute(attr);});
  return '<style>'+[...doc.querySelectorAll('style')].map(n=>n.textContent).join('\n')+'</style>'+doc.body.innerHTML.replace(/<style[\s\S]*?<\/style>/gi,'');
}

export async function htmlPage(deck,page,index,media,mount){
  const frame=document.createElement('article');frame.className='h3-slide-page h3-html-page';
  const height=heights[deck.format];frame.dataset.page=String(index+1);
  frame.style.cssText=`all:initial;display:block;position:relative;box-sizing:border-box;width:1280px;height:${height}px;overflow:hidden;transform-origin:top left;background:white;--slide-height:${height}px;`;
  const iframe=document.createElement('iframe');iframe.title=page.title;iframe.sandbox='allow-same-origin';iframe.style.cssText='display:block;border:0;width:1280px;height:100%;';
  const content=await markup(page,media);
  const loaded=new Promise((resolve,reject)=>{iframe.onload=resolve;iframe.onerror=()=>reject(Error('Anteprima HTML non disponibile.'));});
  const fontNames=['Manrope','Cormorant'].filter(name=>content.includes(name));
  const fonts=(await Promise.all(fontNames.map(async name=>`@font-face{font-family:${name};src:url("${await localFont('/static/'+name+'.ttf')}")}`))).join('');
  const background=deck.infographic?.video,clip=background&&media.find(m=>m.id===background.asset_id&&m.mime==='video/mp4'&&/^(uploads|outputs)\/[\w./-]+\.mp4$/i.test(m.path)&&!m.path.split('/').includes('..'));
  if(background&&!clip)throw Error('Video di sfondo non disponibile negli allegati.');
  const splitClips=(deck.infographic?.videos||[]).map(spec=>({spec,asset:media.find(m=>m.id===spec.asset_id&&m.mime==='video/mp4'&&/^(uploads|outputs)\/[\w./-]+\.mp4$/i.test(m.path)&&!m.path.split('/').includes('..'))}));if(splitClips.some(c=>!c.asset))throw Error('Video del riquadro non disponibile negli allegati.');
  iframe.srcdoc=`<!doctype html><html><head><meta charset="utf-8"><meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; img-src data:; font-src data:; script-src 'none'; connect-src 'none'; ${clip||splitClips.length?"media-src 'self';":''}"><style data-h3-trusted>html,body{margin:0;width:1280px;min-height:${height}px;box-sizing:border-box}*,*:before,*:after{box-sizing:border-box}${fonts}${deck.infographic?'*,*:before,*:after{animation:none!important;transition:none!important}':''}</style></head><body>${content}<style data-h3-trusted>html,body{overflow:hidden!important}</style></body></html>`;
  frame.append(iframe);mount.append(frame);await loaded;
  const doc=iframe.contentDocument;
  if(clip){
    const video=doc.createElement('video');video.dataset.h3Video=background.asset_id;video.dataset.h3Trusted='';video.muted=true;video.playsInline=true;video.preload='auto';video.loop=background.end==='loop';video.src='/media/'+clip.path;
    const poster=media.find(m=>m.id===background.poster_id&&m.mime==='image/jpeg'&&safePath(m.path));
    if(poster){const preview=new DOMParser().parseFromString(await markup({html:'<img data-asset-id="'+poster.id+'">'},[poster]),'text/html');video.poster=preview.querySelector('img')?.src||'';}
    const style=doc.createElement('style');style.dataset.h3Trusted='';style.textContent=`html{background:#101820}body{position:relative!important;isolation:isolate;background:transparent!important;overflow:hidden!important;height:${height}px}video[data-h3-video]{position:absolute!important;inset:0!important;z-index:-1!important;width:100%!important;height:100%!important;object-fit:${background.fit==='cover'?'cover':'contain'}!important;pointer-events:none!important}`;
    doc.head.append(style);doc.body.append(video);
  }
  for(const {spec,asset} of splitClips){
    for(const slot of [...doc.querySelectorAll('div[data-video-asset-id]')].filter(e=>e.dataset.videoAssetId===spec.asset_id)){
      const video=doc.createElement('video');video.dataset.h3Video=spec.asset_id;video.dataset.h3Trusted='';video.muted=true;video.playsInline=true;video.preload='auto';video.loop=spec.end==='loop';video.src='/media/'+asset.path;video.style.cssText='display:block;width:100%;height:100%;object-fit:'+(spec.fit==='cover'?'cover':'contain');
      const poster=media.find(m=>m.id===spec.poster_id&&m.mime==='image/jpeg'&&safePath(m.path));
      if(poster){const preview=new DOMParser().parseFromString(await markup({html:'<img data-asset-id="'+poster.id+'">'},[poster]),'text/html');video.poster=preview.querySelector('img')?.src||'';}
      slot.prepend(video);
    }
  }
  if(deck.infographic){H3Motion.screen(doc,deck.infographic.options,deck.infographic.durations[index]);H3Motion.freeze(doc);}
  await doc.fonts.ready;await Promise.all([...doc.images].map(img=>img.decode().catch(()=>{})));
  renderMath(doc.body,{delimiters:[{left:'$$',right:'$$',display:true},{left:'$',right:'$',display:false}],throwOnError:false});
  // Local bundled math CSS is trusted and does not enable generated scripts.
  if(doc.querySelector('.katex')){const style=document.createElement('style');style.dataset.h3Trusted='';style.textContent=await localMathCSS();doc.head.append(style);await doc.fonts.ready;}
  doc.documentElement.dataset.h3TextTone=page.text_tone||deck.text_tone||'auto';
  readableText(doc);
  if(deck.infographic)H3Motion.configure(doc,deck.infographic.options||{});
  const generated=new Set((deck.image_generation?.plan||[]).map(item=>item.asset_id));
  for(const img of doc.images)if(generated.has(img.dataset.assetId)&&!img.dataset.imageFit&&doc.defaultView.getComputedStyle(img).objectFit==='cover')img.dataset.imageFit='cover';
  if(fitMediaBounds(doc,height,!deck.infographic))frame.dataset.layoutAdjusted='true';
  if(deck.infographic&&page.status==='ready'&&portraitLayout(doc,height,deck.infographic.options).issue)frame.dataset.portraitSparse='true';
  sessions.set(frame,{iframe,doc});return frame;
}

// Prepare the next streamed draft without clearing the visible document. Keep
// the iframe itself attached: replacing/reparenting it reloads its browsing
// context and briefly exposes the unscaled 1280px page.
export async function refreshHtmlPage(frame,deck,page,index,media,current=()=>true){
  const session=sessions.get(frame);
  if(!session||deck.infographic)return false;
  const staging=document.createElement('div');
  staging.style.cssText='position:fixed;left:-20000px;top:0;width:1280px;visibility:hidden;pointer-events:none;contain:layout paint;';
  staging.setAttribute('aria-hidden','true');document.body.append(staging);
  try{
    const next=await htmlPage(deck,page,index,media,staging),prepared=sessions.get(next);
    if(!current()||!frame.isConnected||session.iframe.contentDocument!==session.doc)return false;
    const {doc,iframe}=session;
    const head=doc.importNode(prepared.doc.head,true),body=doc.importNode(prepared.doc.body,true);
    // Both replacements are synchronous, so the browser paints only the fully
    // prepared draft; generated scripts remain blocked by the existing sandbox.
    doc.head.replaceWith(head);doc.body.replaceWith(body);
    doc.documentElement.dataset.h3TextTone=prepared.doc.documentElement.dataset.h3TextTone;
    iframe.title=page.title;
    if(next.dataset.layoutAdjusted)frame.dataset.layoutAdjusted='true';else delete frame.dataset.layoutAdjusted;
    return true;
  }finally{staging.remove();}
}

export function htmlOverflow(frame){
  const doc=sessions.get(frame)?.doc;if(!doc)return false;
  return contentOverflows(doc,frame.offsetHeight);
}

export function flattenHtml(frame){
  const {doc}=sessions.get(frame),body=doc.body,initial=initialExportStyles(doc),clone=body.cloneNode(true);
  const sources=[body,...body.querySelectorAll('*')],targets=[clone,...clone.querySelectorAll('*')];
  for(let i=0;i<sources.length;i++){
    const css=doc.defaultView.getComputedStyle(sources[i]);targets[i].removeAttribute('class');
    applyExportStyles(targets[i],css,initial);
    if(css.position==='fixed')targets[i].setAttribute('style',targets[i].getAttribute('style')+';position:absolute');
    for(const pseudo of ['::before','::after']){
      const decoration=doc.defaultView.getComputedStyle(sources[i],pseudo);
      if(!decoration.content||['none','normal'].includes(decoration.content))continue;
      const span=document.createElement('span');
      try{span.textContent=JSON.parse(decoration.content);}catch{span.textContent='';}
      applyExportStyles(span,decoration,initial,{pseudo:true});
      if(pseudo==='::before')targets[i].prepend(span);else targets[i].append(span);
    }
  }
  clone.querySelectorAll('[data-h3-video]').forEach(n=>{if(n.poster){const image=document.createElement('img');image.src=n.poster;image.style.cssText=n.style.cssText;n.replaceWith(image);}else n.remove();});
  clone.querySelectorAll('style,script').forEach(n=>n.remove());
  const content=document.createElement('div');content.setAttribute('style',clone.getAttribute('style'));content.innerHTML=clone.innerHTML;
  frame.replaceChildren(content);sessions.delete(frame);
}

export function mountHtmlEditor(target,deck,index,frame,onChange,options,media){
  return editHtmlSlide(target,deck,index,frame,onChange,{...options,repairContrast:readableText},media,{...sessions.get(frame),overflow:htmlOverflow,encode});
}

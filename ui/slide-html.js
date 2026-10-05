import DOMPurify from 'dompurify';
import renderMath from 'katex/contrib/auto-render';
import {imagePicker} from './slide-image-picker.js';
import {parseColor,composite,contrastRatio,readableColor,colorHex} from './color-contrast.js';

const heights={'16:9':720,'4:3':960,'16:10':800,'1:1':1280};
const safePath=path=>/^(uploads|outputs)\/[\w./-]+\.(png|jpg|jpeg|webp)$/i.test(path);
const encode=deck=>'```h3-slides\n'+JSON.stringify(deck)+'\n```';
const sessions=new WeakMap();
function readableText(doc){
  for(const element of doc.body.querySelectorAll('*')){
    if(element.closest('svg,style,math,.katex-mathml')||![...element.childNodes].some(n=>n.nodeType===3&&n.textContent.trim()))continue;
    const layers=[];let opacity=1,complex=false;
    for(let parent=element;parent;parent=parent.parentElement){const css=doc.defaultView.getComputedStyle(parent);if(css.backgroundImage!=='none'){complex=true;break;}layers.push(parseColor(css.backgroundColor)||[0,0,0,0]);opacity*=Number(css.opacity);}
    if(complex)continue;
    const background=layers.reverse().reduce((bg,layer)=>composite(layer,bg),[255,255,255,1]),foreground=parseColor(doc.defaultView.getComputedStyle(element).color);
    if(foreground&&contrastRatio(foreground,background,opacity)<4.5){element.style.setProperty('color',colorHex(readableColor(foreground,background,opacity)),'important');element.dataset.contrastAdjusted='true';}
  }
}
const fontCache=new Map();
async function localFont(path){
  if(!fontCache.has(path))fontCache.set(path,fetch(path).then(r=>{if(!r.ok)throw Error('Font locale non disponibile.');return r.blob();}).then(blob=>new Promise(resolve=>{const reader=new FileReader();reader.onload=()=>resolve(reader.result);reader.readAsDataURL(blob);})));return fontCache.get(path);
}
let mathCSS;
async function localMathCSS(){
  mathCSS||=(async()=>{let css=await fetch('/static/vendor/katex.min.css').then(r=>r.text());const urls=[...new Set([...css.matchAll(/url\(([^)]+)\)/g)].map(m=>m[1].replace(/["']/g,'')).filter(x=>/^fonts\/KaTeX_[\w-]+\.woff2$/.test(x)))];const pairs=await Promise.all(urls.map(async x=>[x,await localFont('/static/vendor/'+x)]));const data=new Map(pairs);return css.replace(/url\(([^)]+)\)/g,(_,url)=>'url("'+(data.get(url.replace(/["']/g,''))||'data:font/woff;base64,')+'")');})();return mathCSS;
}

async function markup(page,media){
  const clean=DOMPurify.sanitize(page.html||'',{WHOLE_DOCUMENT:true,ADD_TAGS:['style'],FORBID_TAGS:['script','iframe','object','embed','link','meta','base','form','input','button','video','audio'],FORBID_ATTR:['srcset','action','formaction','autofocus']});
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
  iframe.srcdoc=`<!doctype html><html><head><meta charset="utf-8"><meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; img-src data:; font-src data:; script-src 'none'; connect-src 'none';"><style data-h3-trusted>html,body{margin:0;width:1280px;min-height:${height}px;box-sizing:border-box}*,*:before,*:after{box-sizing:border-box}${fonts}</style></head><body>${content}</body></html>`;
  frame.append(iframe);mount.append(frame);await loaded;
  const doc=iframe.contentDocument;
  await doc.fonts.ready;await Promise.all([...doc.images].map(img=>img.decode().catch(()=>{})));
  renderMath(doc.body,{delimiters:[{left:'$$',right:'$$',display:true},{left:'$',right:'$',display:false}],throwOnError:false});
  // Local bundled math CSS is trusted and does not enable generated scripts.
  if(doc.querySelector('.katex')){const style=document.createElement('style');style.dataset.h3Trusted='';style.textContent=await localMathCSS();doc.head.append(style);await doc.fonts.ready;}
  readableText(doc);
  sessions.set(frame,{iframe,doc});return frame;
}

export function htmlOverflow(frame){
  const doc=sessions.get(frame)?.doc;if(!doc)return false;
  return [...doc.body.querySelectorAll('*')].some(e=>{if(e.closest('svg,style'))return false;const b=e.getBoundingClientRect();return b.right>1282||b.bottom>frame.offsetHeight+2||b.left< -2||b.top< -2;});
}

export function flattenHtml(frame){
  const {doc}=sessions.get(frame),body=doc.body,clone=body.cloneNode(true);
  const sources=[body,...body.querySelectorAll('*')],targets=[clone,...clone.querySelectorAll('*')];
  for(let i=0;i<sources.length;i++){
    const css=doc.defaultView.getComputedStyle(sources[i]);targets[i].removeAttribute('class');
    for(const property of css){const value=css.getPropertyValue(property);if(!/url\(/i.test(value))targets[i].style.setProperty(property,value);}
    if(css.position==='fixed')targets[i].style.position='absolute';
    targets[i].style.setProperty('animation','none');targets[i].style.setProperty('transition','none');
    for(const pseudo of ['::before','::after']){
      const decoration=doc.defaultView.getComputedStyle(sources[i],pseudo);
      if(!decoration.content||['none','normal'].includes(decoration.content))continue;
      const span=document.createElement('span');
      try{span.textContent=JSON.parse(decoration.content);}catch{span.textContent='';}
      for(const property of decoration){const value=decoration.getPropertyValue(property);if(!/url\(/i.test(value)&&property!=='content')span.style.setProperty(property,value);}
      if(pseudo==='::before')targets[i].prepend(span);else targets[i].append(span);
    }
  }
  clone.querySelectorAll('style,script').forEach(n=>n.remove());
  const content=document.createElement('div');content.style.cssText=clone.style.cssText;content.innerHTML=clone.innerHTML;
  frame.replaceChildren(content);sessions.delete(frame);
}

export function mountHtmlEditor(target,deck,index,frame,onChange,options,media){
  const {doc,iframe}=sessions.get(frame);let selected=null,dirty=false,saving=false;
  const page=deck.pages[index],toolbar=document.createElement('div');toolbar.className='slide-editor no-export';
  toolbar.innerHTML='<p>Seleziona un elemento nella slide. Trascina per spostarlo.</p><label>Testo <textarea id="slide-html-text" rows="3"></textarea></label> <label>Dimensione <input id="slide-html-size" type="number" min="8" max="160"></label> <label>Colore <input id="slide-html-color" type="color"></label> <label>Sfondo <input id="slide-html-bg" type="color"></label> <label>Larghezza <input id="slide-html-width" type="number" min="10" max="1280"></label> <button id="slide-html-save">Applica e salva</button> <button id="slide-html-undo">Annulla modifiche</button><span id="slide-html-status"></span>';
  target.append(toolbar);const q=s=>toolbar.querySelector(s),status=q('#slide-html-status');
  const extra=document.createElement('div');extra.innerHTML='<button id="slide-html-add">+ Testo</button> <button id="slide-html-copy">Duplica</button> <button id="slide-html-delete">Elimina</button> <label>Altezza <input id="slide-html-height" type="number" min="10" max="1280"></label> <label>Carattere <select id="slide-html-font"><option>Segoe UI</option><option>Arial</option><option>Georgia</option><option>Manrope</option><option>Cormorant</option><option>Consolas</option><option>Comic Sans MS</option></select></label>';toolbar.prepend(extra);
  if(options.api)imagePicker(target,{api:options.api,chatId:options.chatId,media,onSelect:async asset=>{
    if(!media.some(m=>m.id===asset.id)){if(media.length>=64)throw Error('Massimo 64 immagini per presentazione.');media.push(asset);}
    const replacing=selected?.tagName==='IMG';const image=replacing?selected:doc.createElement('img');
    image.dataset.assetId=asset.id;
    const blob=await fetch('/media/'+asset.path).then(r=>r.blob());image.src=await new Promise(resolve=>{const reader=new FileReader();reader.onload=()=>resolve(reader.result);reader.readAsDataURL(blob);});
    image.alt=asset.name;
    if(!replacing){image.style.cssText='position:absolute;left:80px;top:140px;width:400px;height:280px;object-fit:contain;';doc.body.append(image);}
    if(asset.provenance){const id='I'+asset.id.slice(0,8),label=[asset.name,asset.provenance.credit,asset.provenance.license].filter(Boolean).join(' · ');deck.references||=[];if(!deck.references.some(r=>r.id===id))deck.references.push({id,label:label.slice(0,1000),...(asset.provenance.url?{url:asset.provenance.url}:{})});page.sources||=[];if(!page.sources.includes(id))page.sources.push(id);}
    select(image);dirty=true;status.textContent='Immagine inserita · premi Applica e salva';
  }});
  const rgbHex=value=>{const m=value.match(/\d+/g);return m?'#'+m.slice(0,3).map(x=>Number(x).toString(16).padStart(2,'0')).join(''):'#ffffff';};
  const select=element=>{
    selected?.style.removeProperty('outline');selected=element;
    const css=doc.defaultView.getComputedStyle(element);element.style.outline='2px dashed #138a92';
    q('#slide-html-text').value=element.textContent;q('#slide-html-text').disabled=!!element.querySelector('img,svg,div,section,article,h1,h2,p,ul,ol');
    q('#slide-html-size').value=parseFloat(css.fontSize);q('#slide-html-color').value=rgbHex(css.color);q('#slide-html-bg').value=rgbHex(css.backgroundColor);q('#slide-html-width').value=Math.round(element.getBoundingClientRect().width);q('#slide-html-height').value=Math.round(element.getBoundingClientRect().height);q('#slide-html-font').value=[...q('#slide-html-font').options].map(x=>x.value).find(x=>css.fontFamily.includes(x))||'Arial';
  };
  doc.addEventListener('click',e=>{e.preventDefault();const element=e.target.closest('h1,h2,h3,h4,p,span,pre,li,img,svg,div,section,article');if(element&&element!==doc.body)select(element);});
  let drag=null;
  doc.addEventListener('pointerdown',e=>{if(e.button!==0||!selected||!selected.contains(e.target))return;const css=doc.defaultView.getComputedStyle(selected);drag={x:e.clientX,y:e.clientY,dx:parseFloat(css.getPropertyValue('--h3-dx'))||0,dy:parseFloat(css.getPropertyValue('--h3-dy'))||0};selected.setPointerCapture?.(e.pointerId);});
  doc.addEventListener('pointermove',e=>{if(!drag)return;selected.style.setProperty('--h3-dx',drag.dx+e.clientX-drag.x+'px');selected.style.setProperty('--h3-dy',drag.dy+e.clientY-drag.y+'px');selected.style.translate='var(--h3-dx) var(--h3-dy)';dirty=true;status.textContent='Modifiche da salvare';});
  doc.addEventListener('pointerup',()=>{drag=null;});
  q('#slide-html-text').oninput=()=>{if(selected&&!q('#slide-html-text').disabled){selected.textContent=q('#slide-html-text').value;dirty=true;}};
  for(const [id,property,unit] of [['size','font-size','px'],['color','color',''],['bg','background-color',''],['width','width','px'],['height','height','px'],['font','font-family','']])q('#slide-html-'+id).oninput=()=>{if(selected){const input=q('#slide-html-'+id);if(unit&&!input.checkValidity())return;selected.style.setProperty(property,input.value+unit);dirty=true;status.textContent='Modifiche da salvare';}};
  q('#slide-html-add').onclick=()=>{const text=doc.createElement('p');text.textContent='Nuovo testo';text.style.cssText='position:absolute;left:80px;top:100px;width:600px;font:32px Segoe UI;color:inherit';doc.body.append(text);select(text);dirty=true;};
  q('#slide-html-copy').onclick=()=>{if(!selected)return;const copy=selected.cloneNode(true);copy.removeAttribute('id');copy.querySelectorAll('[id]').forEach(n=>n.removeAttribute('id'));copy.style.outline='';copy.style.translate='20px 20px';selected.after(copy);select(copy);dirty=true;};
  q('#slide-html-delete').onclick=()=>{if(!selected)return;selected.remove();selected=null;dirty=true;status.textContent='Elemento eliminato · premi Applica e salva';};
  const original=page.html;
  q('#slide-html-undo').onclick=()=>{page.html=original;onChange(encode(deck)).catch(e=>{status.textContent=e.message;});};
  q('#slide-html-save').onclick=async()=>{
    if(saving)return;saving=true;selected?.style.removeProperty('outline');
    const old=page.html;
    try{
      if(htmlOverflow(frame))throw Error('Un elemento supera i bordi: spostalo o ridimensionalo prima di salvare.');
      const editable=doc.body.cloneNode(true);
      for(const formula of editable.querySelectorAll('.katex-display,.katex:not(.katex-display .katex)')){const tex=formula.querySelector('annotation')?.textContent;if(tex){const delimiter=formula.classList.contains('katex-display')?'$$':'$';formula.replaceWith(delimiter+tex+delimiter);}}
      page.html='<style>'+[...doc.querySelectorAll('style:not([data-h3-trusted])')].map(x=>x.textContent).join('\n')+'</style>'+editable.innerHTML;
      // Images are stored by asset ID; never persist the decoded data twice.
      const saved=new DOMParser().parseFromString(page.html,'text/html');saved.querySelectorAll('img').forEach(img=>img.removeAttribute('src'));
      page.html='<style>'+[...saved.querySelectorAll('style')].map(x=>x.textContent).join('\n')+'</style>'+saved.body.innerHTML.replace(/<style[\s\S]*?<\/style>/gi,'');
      await onChange(encode(deck),media);dirty=false;status.textContent='Salvato';
    }catch(e){page.html=old;status.textContent=e.message;}finally{saving=false;}
  };
}

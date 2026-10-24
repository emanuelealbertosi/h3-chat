import {saveBlob} from './render.js';

const escapeHtml=text=>String(text).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const navigation=`const data=JSON.parse(document.getElementById('slides-data').textContent),frame=document.getElementById('slide'),stage=document.getElementById('stage'),select=document.getElementById('pages');let current=0;
data.pages.forEach((page,i)=>{const option=document.createElement('option');option.value=i;option.textContent=(i+1)+'. '+page.title;select.append(option);});
function fit(){const scale=Math.min(stage.clientWidth/data.width,stage.clientHeight/data.height);frame.style.width=data.width+'px';frame.style.height=data.height+'px';frame.style.transform='translate(-50%,-50%) scale('+scale+')';}
function show(index){current=Math.max(0,Math.min(data.pages.length-1,index));const page=data.pages[current];frame.title=page.title;frame.srcdoc=page.html.replace(/<style[^>]*data-h3-shared-style="(\\d+)"[^>]*><\\/style>/g,(_,id)=>'<style>'+data.styles[Number(id)]+'</style>');select.value=current;document.getElementById('counter').textContent=(current+1)+' / '+data.pages.length;document.getElementById('previous').disabled=current===0;document.getElementById('next').disabled=current===data.pages.length-1;fit();}
document.getElementById('previous').onclick=()=>show(current-1);document.getElementById('next').onclick=()=>show(current+1);document.getElementById('replay').onclick=()=>show(current);select.onchange=()=>show(Number(select.value));document.getElementById('fullscreen').onclick=()=>document.fullscreenElement?document.exitFullscreen():document.documentElement.requestFullscreen().catch(()=>{});
document.addEventListener('keydown',e=>{if(e.target===select)return;if(['ArrowRight','PageDown',' '].includes(e.key)){e.preventDefault();show(current+1);}if(['ArrowLeft','PageUp'].includes(e.key)){e.preventDefault();show(current-1);}if(e.key==='Home')show(0);if(e.key==='End')show(data.pages.length-1);});new ResizeObserver(fit).observe(stage);show(0);`;

export function presentationHtml(data,title){
 const nonce=btoa(String.fromCharCode(...crypto.getRandomValues(new Uint8Array(18))));
 // Page markup is data, never part of the parent document. Each page runs in
 // an opaque sandbox without scripts; only this fixed navigation script runs.
 const json=JSON.stringify(data).replace(/</g,'\\u003c').replace(/>/g,'\\u003e').replace(/&/g,'\\u0026');
 const result=`<!doctype html><html lang="it"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta http-equiv="Content-Security-Policy" content="default-src 'none'; frame-src 'self' about:; style-src 'unsafe-inline'; script-src 'nonce-${nonce}'; base-uri 'none'; form-action 'none'"><title>${escapeHtml(title)}</title><style>html,body{margin:0;height:100%;background:#17242b;color:#eef5f7;font:16px system-ui}body{display:grid;grid-template-rows:auto minmax(0,1fr) auto}header,footer{padding:12px 16px;display:flex;align-items:center;gap:10px;flex-wrap:wrap}header strong{flex:1}button,select{font:inherit;border:1px solid #63828b;border-radius:7px;padding:8px;background:#263d46;color:inherit;max-width:100%}button:disabled{opacity:.4}select{flex:1;min-width:120px}#stage{position:relative;overflow:hidden;min-height:0}iframe{position:absolute;left:50%;top:50%;border:0;background:white;transform-origin:center}footer small{width:100%;color:#bfd0d5}@media(max-width:600px){header,footer{padding:8px;gap:6px}header strong{font-size:14px}button,select{font-size:14px;padding:7px}}</style></head><body><header><strong>${escapeHtml(title)}</strong><button id="fullscreen">Schermo intero</button></header><main id="stage"><iframe id="slide" sandbox="" title="Slide"></iframe></main><footer><button id="previous" aria-label="Slide precedente">←</button><select id="pages" aria-label="Scegli slide"></select><span id="counter" aria-live="polite"></span><button id="next" aria-label="Slide successiva">→</button><button id="replay">Ripeti animazioni</button><small>Frecce ← → per sfogliare. Le animazioni CSS disponibili ripartono a ogni apertura della slide.</small></footer><script type="application/json" id="slides-data">${json}</script><script nonce="${nonce}">${navigation}</script></body></html>`;
 if(new TextEncoder().encode(result).length>64*1024*1024)throw Error('Presentazione HTML oltre 64 MB: riduci le dimensioni delle immagini.');
 return result;
}

export async function exportPresentation(root,deck,title,token){
 const styles=[],pages=[],height={'16:9':720,'9:16':1280*16/9,'4:3':960,'16:10':800,'1:1':1280}[deck.format];
 const share=style=>{let index=styles.indexOf(style);if(index<0){index=styles.length;styles.push(style);}return index;};
 if(deck.engine==='llm'){
  for(const [index,frame] of [...root.children].entries()){
   const original=frame.querySelector('iframe').contentDocument,clone=original.documentElement.cloneNode(true);
   clone.querySelectorAll('[data-h3-editor],script').forEach(n=>n.remove());
   clone.querySelectorAll('[data-h3-shared-style]').forEach(n=>n.removeAttribute('data-h3-shared-style'));
   for(const style of clone.querySelectorAll('style[data-h3-trusted]')){style.dataset.h3SharedStyle=share(style.textContent);style.textContent='';}
   pages.push({title:deck.pages[index].title,html:'<!doctype html>'+clone.outerHTML});
  }
 }else{
  // Legacy declarative pages have no authored CSS animations. Reuse the
  // existing sanitized vector export and embed its shared fonts only once.
  const html=await (await import('./exports.js')).printableHtml(root);
  const response=await fetch('/api/export/html',{method:'POST',headers:{'Content-Type':'application/json','X-H3-Token':token},body:JSON.stringify({title,html,slide_format:deck.format})});
  const result=await response.json();if(!response.ok)throw Error(result.error);
  const doc=new DOMParser().parseFromString(await fetch(result.url).then(r=>r.text()),'text/html');
  const style=share([...doc.querySelectorAll('style')].map(n=>n.textContent).join('\n'));
  for(const [index,page] of [...doc.querySelectorAll('.h3-slide-page')].entries())pages.push({title:deck.pages[index].title,html:'<!doctype html><html><head><meta http-equiv="Content-Security-Policy" content="default-src \'none\'; style-src \'unsafe-inline\'; img-src data:; font-src data:; script-src \'none\'"><style data-h3-shared-style="'+style+'"></style><style>html,body{margin:0;width:1280px;height:'+height+'px;overflow:hidden;background:white}.slides-document{margin:0}.h3-slide-page{margin:0!important;box-shadow:none!important}</style></head><body>'+page.outerHTML+'</body></html>'});
 }
 const html=presentationHtml({width:1280,height,styles,pages},title);
 saveBlob(new Blob([html],{type:'text/html;charset=utf-8'}),(title||'Presentazione').replace(/[^\p{L}\p{N}\s_-]/gu,'').slice(0,80)+'.html');
}

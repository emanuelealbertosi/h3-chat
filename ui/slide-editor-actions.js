import DOMPurify from 'dompurify';
import {uploadFile} from './file-upload.js';
const mime='application/x-h3-canvas-element';
const fields='input,textarea,select,[contenteditable=""],[contenteditable="true"]';
const safeAsset=a=>a&&typeof a.id==='string'&&/^image\//.test(a.mime)&&/^(uploads|outputs)\/[\w./-]+\.(png|jpg|jpeg|webp)$/i.test(a.path)&&!a.path.split('/').includes('..');

export function initSlideEditorActions({toolbar,target,doc,getSelected,select,insertionParent,change,media,imageSources,status,insertAsset,options}){
 const parent=target.ownerDocument;
 const controls=parent.createElement('div');controls.className='slide-editor-top slide-layer-controls';
 for(const [key,label] of [['copy','Copia'],['paste','Incolla'],['back','Porta indietro'],['front','Porta avanti'],['bottom','Porta sullo sfondo'],['top','Porta in primo piano']]){const b=parent.createElement('button');b.type='button';b.dataset.editorAction=key;b.textContent=label;controls.append(b);}
 const note=parent.createElement('p');note.className='slide-editor-help';note.textContent='Ctrl+Z annulla · Ctrl+Y / Ctrl+Shift+Z ripristina · Ctrl+C / Ctrl+V copia e incolla. I livelli si ordinano nel gruppo corrente; usa Seleziona gruppo per spostare un gruppo intero.';toolbar.querySelector('#slide-html-parent').closest('.slide-editor-top').after(controls,note);
 let copied=null,copyingByButton=false;
 const sync=()=>{for(const b of controls.children)b.disabled=b.dataset.editorAction==='paste'?!copied:!getSelected()?.isConnected;};
 const writing=e=>e.target?.isContentEditable||e.target?.closest?.(fields);
 const scoped=e=>e.currentTarget===doc||toolbar.contains(e.target)||target.contains(e.target);
 function copy(){
  const selected=getSelected();if(!selected?.isConnected)return null;
  const clone=selected.cloneNode(true);for(const element of [clone,...clone.querySelectorAll('*')]){element.removeAttribute('id');element.removeAttribute('src');element.querySelectorAll('[data-h3-editor],[data-h3-trusted]').forEach(n=>n.remove());}
  const ids=new Set([clone,...clone.querySelectorAll('img')].map(e=>e.dataset.assetId).filter(Boolean));
  return copied={version:1,html:clone.outerHTML,media:media.filter(m=>ids.has(m.id)&&safeAsset(m)).map(m=>({...m}))};
 }
 async function paste(value){
  if(value?.version!==1||typeof value.html!=='string'||value.html.length>80000||!Array.isArray(value.media)||value.media.length>128)throw Error('Elemento copiato non valido.');
  const clean=DOMPurify.sanitize(value.html,{RETURN_DOM_FRAGMENT:true,FORBID_TAGS:['script','style','iframe','object','embed','link','meta','base','form','input','button','video','audio'],FORBID_ATTR:['src','srcset','href','xlink:href','data-h3-editor','data-h3-trusted']});
  if(clean.children.length!==1)throw Error('Copia un singolo elemento o un gruppo.');
  const clone=doc.importNode(clean.firstElementChild,true);for(const n of [clone,...clone.querySelectorAll('[id]')])n.removeAttribute('id');
  const assets=value.media.filter(safeAsset),fresh=assets.filter(a=>!media.some(m=>m.id===a.id));if(media.length+fresh.length>128)throw Error('Massimo 128 risorse per presentazione.');
  for(const image of [clone,...clone.querySelectorAll('img')].filter(e=>e.tagName==='IMG')){
   const asset=media.find(m=>m.id===image.dataset.assetId)||assets.find(m=>m.id===image.dataset.assetId);if(!safeAsset(asset))throw Error('Immagine copiata non disponibile.');
   if(!imageSources.has(asset.id)){
    const response=await fetch('/media/'+asset.path);if(!response.ok)throw Error('Immagine copiata non disponibile.');
    const blob=await response.blob(),src=await new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(reader.result);reader.onerror=reject;reader.readAsDataURL(blob);});imageSources.set(asset.id,src);
   }
   image.src=imageSources.get(asset.id);
  }
  const selected=getSelected(),holder=insertionParent();
  if(change(()=>{clone.style.translate='20px 20px';if(selected?.parentElement===holder)selected.after(clone);else holder.append(clone);select(clone);}))media.push(...fresh);
 }
 function layer(action){
  const selected=getSelected();if(!selected?.isConnected)return;
  change(()=>{
   const siblings=[...selected.parentElement.children].filter(e=>!e.matches('style,script,[data-h3-editor],[data-h3-trusted]')).sort((a,b)=>(parseInt(doc.defaultView.getComputedStyle(a).zIndex)||0)-(parseInt(doc.defaultView.getComputedStyle(b).zIndex)||0));
   const index=siblings.indexOf(selected),next=action==='top'?siblings.length-1:action==='bottom'?0:Math.max(0,Math.min(siblings.length-1,index+(action==='front'?1:-1)));
   siblings.splice(index,1);siblings.splice(next,0,selected);
   for(const [i,e] of siblings.entries()){if(doc.defaultView.getComputedStyle(e).position==='static')e.style.position='relative';e.style.zIndex=String(i+1);}
   select(selected);
  });
 }
 const report=fn=>async()=>{try{await fn();}catch(e){status.textContent=e.message;}};
 for(const b of controls.children)b.onclick=report(async()=>{const action=b.dataset.editorAction;if(action==='copy'){copy();sync();copyingByButton=true;try{parent.execCommand('copy');}finally{copyingByButton=false;}status.textContent='Elemento copiato · seleziona dove incollarlo';}else if(action==='paste'){if(copied)await paste(copied);else status.textContent='Copia un elemento oppure usa Ctrl+V per incollare un’immagine dagli appunti.';}else layer(action);});
 function keydown(e){
  if(!scoped(e)||writing(e)||!(e.ctrlKey||e.metaKey)||e.altKey)return;
  const key=e.key.toLowerCase();
  if(key==='z'||key==='y'){e.preventDefault();toolbar.querySelector(key==='y'||e.shiftKey?'#slide-html-redo':'#slide-html-undo').click();}
  else if(key==='s'){e.preventDefault();toolbar.querySelector('#slide-html-save').click();}
 }
 function onCopy(e){
  if(!scoped(e)||writing(e)||!copyingByButton&&!doc.getSelection()?.isCollapsed)return;
  const value=copy();sync();if(!value||!e.clipboardData)return;e.preventDefault();e.clipboardData.setData(mime,JSON.stringify(value));e.clipboardData.setData('text/plain',getSelected().getAttribute('alt')||getSelected().textContent||'Elemento H3');status.textContent='Elemento copiato';
 }
 async function onPaste(e){
  if(!scoped(e)||writing(e)||!e.clipboardData)return;
  const value=e.clipboardData.getData(mime),images=[...e.clipboardData.items].filter(i=>i.kind==='file'&&i.type.startsWith('image/'));
  if(!value&&!images.length)return;e.preventDefault();
  try{if(value)await paste(JSON.parse(value));else{if(!options.api)throw Error('Caricamento immagini non disponibile.');for(const item of images){if(!['image/png','image/jpeg','image/webp'].includes(item.type))throw Error('Incolla un’immagine PNG, JPEG o WebP.');const file=item.getAsFile();if(file)await insertAsset(await uploadFile(file,{api:options.api}),{replace:false});}}}
  catch(error){status.textContent=error.message;}
 }
 for(const d of [doc,parent]){d.addEventListener('keydown',keydown);d.addEventListener('copy',onCopy);d.addEventListener('paste',onPaste);}
 const observer=new MutationObserver(()=>{if(toolbar.isConnected)return;for(const d of [doc,parent]){d.removeEventListener('keydown',keydown);d.removeEventListener('copy',onCopy);d.removeEventListener('paste',onPaste);}observer.disconnect();});observer.observe(parent.body,{childList:true,subtree:true});
 sync();return {sync};
}

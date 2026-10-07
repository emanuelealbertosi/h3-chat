import {readDeck,exportSlides} from './slides.js';
export const presentationAttachment=m=>['application/pdf','application/vnd.openxmlformats-officedocument.presentationml.presentation','image/png','image/jpeg','image/webp'].includes(m.mime);
export function readyPresentation(value){try{const deck=readDeck(value?.content||'');return !!deck&&deck.pages.every(p=>p.status==='ready');}catch{return false;}}
export function initManimPresentation({getAttachments,getCanvas,getState,getChatId,api,notify}){
 const drafts=new Map(),panel=document.createElement('div');panel.id='manim-presentation-options';panel.className='prompt-slide-options';panel.hidden=true;
 panel.innerHTML='<div class="prompt-field"><span class="prompt-field-label">Presentazione → animazione</span><div class="prompt-choices"><button type="button" id="manim-presentation-enable" class="prompt-choice" aria-pressed="false">Anima presentazione</button></div></div><div id="manim-presentation-details" hidden><div class="prompt-field"><span class="prompt-field-label">Sorgente</span><div class="prompt-choices"><button type="button" class="prompt-choice" data-manim-source="attachments">Allegati</button><button type="button" class="prompt-choice" data-manim-source="canvas">Slide nel canvas</button></div></div><div class="prompt-field"><span class="prompt-field-label">Animazione</span><div class="prompt-choices"><button type="button" class="prompt-choice" data-manim-mode="preserve">Mantieni layout</button><button type="button" class="prompt-choice" data-manim-mode="reconstruct">Ricostruisci con Manim</button></div></div><p class="small-note">Una scena per slide, nell’ordine originale, con le stesse immagini. Mantieni layout anima sopra la pagina originale; Ricostruisci ricrea gli elementi. Con Voice aggiunge la spiegazione sincronizzata. Fino a 30 slide; senza durata nel prompt usa la durata Manim per ciascuna slide.</p></div><p id="manim-presentation-empty" class="small-note">Allega PDF, PPTX o immagini, oppure apri una presentazione completata nel canvas.</p>';
 document.querySelector('#prompt-context').append(panel);
 const draft=()=>{const key=getChatId()||'new';if(!drafts.has(key))drafts.set(key,{enabled:false,mode:'preserve',source:'attachments'});return drafts.get(key);};
 const availability=()=>({attachments:getAttachments().some(presentationAttachment),canvas:readyPresentation(getCanvas())});
 panel.querySelector('#manim-presentation-enable').onclick=()=>{draft().enabled=!draft().enabled;render();};
 for(const button of panel.querySelectorAll('[data-manim-source],[data-manim-mode]'))button.onclick=()=>{const d=draft();if(button.dataset.manimSource)d.source=button.dataset.manimSource;else d.mode=button.dataset.manimMode;render();};
 function render(){
  const manim=document.querySelector('#lab-tool').value==='manim';panel.hidden=!manim;
  const available=availability(),d=draft(),any=available.attachments||available.canvas;
  if(!any)d.enabled=false;
  if(!available[d.source])d.source=available.attachments?'attachments':'canvas';
  const toggle=panel.querySelector('#manim-presentation-enable');toggle.disabled=!any;toggle.setAttribute('aria-pressed',String(d.enabled));
  panel.querySelector('#manim-presentation-details').hidden=!d.enabled;panel.querySelector('#manim-presentation-empty').hidden=any;
  for(const b of panel.querySelectorAll('[data-manim-source]')){b.disabled=!available[b.dataset.manimSource];b.setAttribute('aria-pressed',String(d.source===b.dataset.manimSource));}
  for(const b of panel.querySelectorAll('[data-manim-mode]'))b.setAttribute('aria-pressed',String(d.mode===b.dataset.manimMode));
 }
 return {render,migrateNew(id){if(drafts.has('new')){drafts.set(id,{...drafts.get('new')});drafts.delete('new');}},set(value){Object.assign(draft(),value||{enabled:false});render();},async prepare(){
  const d={...draft()};if(document.querySelector('#lab-tool').value!=='manim'||!d.enabled)return {};
  if(!availability()[d.source])throw Error('La sorgente della presentazione non è più disponibile.');
  let media=[...getAttachments()];
  if(d.source==='canvas'){
   const value={...getCanvas(),media:[...getCanvas().media]};notify('Preparo le slide del canvas per Manim…');
   const blob=await exportSlides(value,'source-pdf',getState().token);
   if(blob.size>25*1024*1024)throw Error('La presentazione del canvas supera 25 MB: riduci le immagini o dividila.');
   const data=await new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(reader.result.split(',')[1]);reader.onerror=reject;reader.readAsDataURL(blob);});
   const source=await api('/uploads',{name:(value.title||'Presentazione')+'.pdf',data});media=[...media.filter(m=>m.mime.startsWith('audio/')),source];
  }
  return {media,manim_presentation:{mode:d.mode,source:d.source}};
 }};
}

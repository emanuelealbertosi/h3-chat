import {escape as esc} from './render.js';

export function initSlideImages(){
 const holder=document.querySelector('#slides-options');
 holder.insertAdjacentHTML('beforeend',' <label><input type="checkbox" id="slides-generate-images"> Immagini AI · tutte insieme</label> <label id="slides-image-model-label" hidden>Modello immagini <select id="slides-image-model" aria-label="Modello immagini della presentazione"></select></label>');
 const enabled=document.querySelector('#slides-generate-images'),select=document.querySelector('#slides-image-model');
 enabled.title='Opzionale: prepara il piano, genera tutte le illustrazioni con un solo modello, poi compone le slide. Se disattivato, il flusso attuale resta invariato.';
 enabled.onchange=()=>document.querySelector('#slides-image-model-label').hidden=!enabled.checked;
 let signature='';
 return {read:()=>({generate_images:enabled.checked,image_model:enabled.checked?select.value:''}),render(state){
  const models=state.models.filter(m=>m.ready&&m.capabilities.includes('create'));
  const next=JSON.stringify(models.map(m=>[m.id,m.name]));if(next===signature)return;signature=next;
  const chosen=select.value;select.innerHTML='<option value="">Predefinito immagini</option>'+models.map(m=>`<option value="${esc(m.id)}">${esc(m.name)}</option>`).join('');
  if(models.some(m=>m.id===chosen))select.value=chosen;
 }};
}

export function mountSlideRevision(target,selected,page,options){
 if(!options.onRegenerate)return;
 const details=document.createElement('details');details.className='slide-ai-revision no-export';details.open=!!selected.aiOpen;
 const summary=document.createElement('summary');summary.textContent=options.animatedInfographic?'Ricrea questa scena animata con AI':'Ricrea questa slide con AI';details.append(summary);
 details.ontoggle=()=>selected.aiOpen=details.open;
 const form=document.createElement('form'),label=document.createElement('label'),input=document.createElement('textarea'),button=document.createElement('button'),error=document.createElement('p');
 label.textContent='Modifiche per la slide '+(selected.index+1);input.placeholder='Es. usa due colonne, una palette più vivace e amplia la spiegazione…';input.ariaLabel='Istruzioni AI per questa slide';input.rows=3;input.maxLength=8000;input.required=true;input.value=selected.aiPrompt||'';input.oninput=()=>selected.aiPrompt=input.value;
 button.type='submit';button.textContent=options.animatedInfographic?'Ricrea solo questa scena':'Ricrea solo questa slide';button.disabled=!options.editable||page.status==='writing';input.disabled=!options.editable;
 if(options.animatedInfographic){const note=document.createElement('p');note.className='small-note';note.textContent='Ricrea contenuti, tempi ed effetti di questa scena. Per aggiornare il filmato premi separatamente «Esporta / aggiorna MP4».';form.append(note);}
 error.className='message-error';error.hidden=true;label.append(input);form.append(label,button,error);details.append(form);target.append(details);
 form.onsubmit=async event=>{event.preventDefault();button.disabled=true;error.hidden=true;try{await options.onRegenerate(selected.index,input.value);selected.aiPrompt='';selected.aiOpen=false;selected.follow=true;}catch(e){error.textContent=e.message;error.hidden=false;button.disabled=!options.editable;}};
}

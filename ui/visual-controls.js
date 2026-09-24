import {escape as esc} from './render.js';

// These are conversation preferences, captured with each queued request.
export function initVisualControls({getState,getChatId}){
 const model=document.querySelector('#image-model'),assistant=document.querySelector('#image-assistant');
 const key=id=>'h3.visual-options.'+(id||'new');
 const read=()=>{try{return {image_model:'',assistant:true,music:false,music_fields:{},...JSON.parse(localStorage.getItem(key(getChatId()))||'{}')};}catch{return {image_model:'',assistant:true,music:false,music_fields:{}};}};
 function save(value){localStorage.setItem(key(getChatId()),JSON.stringify(value));render();}
 function render(){
  const state=getState();if(!state)return;
  const value=read(),items=state.models.filter(m=>m.capabilities.includes('create'));
  const signature=JSON.stringify(items.map(m=>[m.id,m.name,m.ready]));
  if(model.dataset.signature!==signature){model.innerHTML='<option value="">Automatico · dal prompt</option>'+items.map(m=>`<option value="${esc(m.id)}" ${m.ready?'':'disabled'}>${esc(m.name)}${m.ready?'':' · non disponibile'}</option>`).join('');model.dataset.signature=signature;}
  if(value.image_model&&!items.some(m=>m.id===value.image_model&&m.ready)){
   const option=document.createElement('option');option.value=value.image_model;option.textContent='Modello selezionato non disponibile';option.disabled=true;
   if(![...model.options].some(o=>o.value===value.image_model))model.append(option);
  }
  model.value=value.image_model;assistant.checked=value.assistant;
  document.querySelector('#music-toggle').setAttribute('aria-pressed',!!value.music);
  document.querySelector('#music-inputs').hidden=!value.music;
  for(const input of document.querySelectorAll('[data-music-field]'))if(document.activeElement!==input){const field=value.music_fields?.[input.dataset.musicField];if(input.type==='checkbox')input.checked=!!field;else input.value=field||'';}
  document.querySelector('#image-assistant-label').textContent='Assistant '+(value.assistant?'On':'Off');
 }
 model.onchange=()=>save({...read(),image_model:model.value,music:false});
 document.querySelector('#music-toggle').onclick=()=>save({...read(),music:!read().music,image_model:''});
 for(const input of document.querySelectorAll('[data-music-field]'))input.oninput=()=>save({...read(),music_fields:{...read().music_fields,[input.dataset.musicField]:input.type==='checkbox'?input.checked:input.value}});
 assistant.onchange=()=>save({...read(),assistant:assistant.checked});
 return {render,read,set:save,migrateNew(id){const value=read();localStorage.setItem(key(id),JSON.stringify(value));localStorage.removeItem(key(null));}};
}

export function renderVisualSetup(container,{state,draft,link,edit,preferences,changed,install}){
 const models=state.models.filter(m=>m.engine==='vision');
 const ming=models.filter(m=>m.architecture==='ming'),qwen=models.filter(m=>m.architecture==='qwen21');
 const select=(list,value)=>'<option value="">Scegli un modello collegato…</option>'+list.map(m=>`<option value="${esc(m.id)}" ${m.id===value?'selected':''}>${esc(m.name)}</option>`).join('');
 const card=(kind,title,list,selected,note)=>`<section class="card"><h3>${title}</h3><p>${note}</p><label class="field"><span>Modello e componenti locali</span><select id="visual-${kind}" ${kind==='ming'?'data-setting="diagram_model"':''}>${select(list,selected)}</select></label><div class="visual-model-actions"><button type="button" class="btn small" data-visual-link="${kind}">Sfoglia e collega</button><button type="button" class="text-button" data-visual-edit="${kind}">Percorsi</button><button type="button" class="text-button" data-visual-preferences="${kind}">Parametri di generazione</button></div><div class="visual-model-actions"><button type="button" class="btn small" data-visual-default="${kind}:create_model">Predefinito crea</button><button type="button" class="btn small" data-visual-default="${kind}:edit_model">Predefinito modifica</button></div>${kind==='ming'?`<label class="mtp-toggle"><input type="checkbox" data-setting="diagram_auto" ${draft.diagram_auto?'checked':''}> Usa Ming automaticamente per grafici, grafi e diagrammi</label><p class="small-note">Per grafici calcolati da dati e diagrammi strutturati puoi richiedere esplicitamente Chart, Mermaid o SVG.</p>`:''}</section>`;
 container.innerHTML=`<h3>Ming e Qwen Image 2.1</h3><p>I tre componenti restano nelle cartelle scelte. Fino a quattro riferimenti nella stessa chat; nessun servizio esterno da avviare.</p><div class="runtime-actions"><button type="button" id="install-vision" class="btn">Installa motore Ming / Qwen 2.1</button><span id="vision-runtime-status" class="small-note"></span></div><p class="small-note">Questo motore usa NVIDIA CUDA o CPU; Vulkan resta disponibile per gli altri modelli. Download aggiuntivo del motore solo al primo utilizzo.</p><div class="settings-grid">${card('ming','Ming · grafici e diagrammi',ming,draft.diagram_model,'Preset: 1024 × 1024, 12 step, CFG 1, Euler / Simple. Creazione e modifica con riferimenti.')}${card('qwen21','Qwen Image 2.1',qwen,qwen.find(m=>m.id===draft.create_model||m.id===draft.edit_model)?.id||qwen[0]?.id,'Preset: 1024 × 1024, 25 step, CFG 1, Euler / Simple. Puoi sceglierlo anche direttamente in chat.')}</div><section class="card"><h3>Assistant · lo stesso LLM della chat</h3><p>Assistant On prepara istruzioni precise con l’LLM già selezionato per la chat. Se è caricato viene riutilizzato. Assistant Off passa il prompt direttamente al modello immagini. L’interruttore è in chat e la scelta viene salvata con il messaggio.</p><p class="small-note">Contesto e limiti di output Assistant si impostano per ciascun LLM in Preferenze → Parametri dei modelli chat.</p><p class="small-note">Le immagini generate possono contenere errori nei testi o nei grafici: Assistant migliora le istruzioni, ma non certifica l’esattezza del risultato. Per precisione numerica usa il grafico strutturato.</p></section>`;
 const chosen=kind=>state.models.find(m=>m.id===container.querySelector('#visual-'+kind).value);
 container.querySelector('#install-vision').onclick=install;
 for(const b of container.querySelectorAll('[data-visual-link]'))b.onclick=()=>link(b.dataset.visualLink);
 for(const b of container.querySelectorAll('[data-visual-edit]'))b.onclick=()=>{const model=chosen(b.dataset.visualEdit);model?edit(model):link(b.dataset.visualEdit);};
 for(const b of container.querySelectorAll('[data-visual-preferences]'))b.onclick=()=>{const model=chosen(b.dataset.visualPreferences);model?preferences(model.id):link(b.dataset.visualPreferences);};
 for(const b of container.querySelectorAll('[data-visual-default]'))b.onclick=()=>{const [kind,key]=b.dataset.visualDefault.split(':'),model=chosen(kind);if(model){draft[key]=model.id;changed();}else link(kind);};
}

import {escape as esc} from './render.js';
let selected=null;
export const selectLlmPreferencesModel=id=>{selected=id;};
export function llmOptions(state){
 const options=state?.llm_options;
 if(!Array.isArray(options?.keys)||!options.defaults||!options.max_context)throw Error('È ancora attivo un motore precedente all’aggiornamento. Esegui Ferma-H3-Chat.bat e poi Avvia-H3-Chat.bat; le impostazioni salvate restano disponibili.');
 return options;
}
const pick=(draft,state)=>Object.fromEntries(llmOptions(state).keys.map(k=>[k,draft[k]]));
export function syncLlmDraft(draft,state,next=draft.chat_model){
 draft.llm_overrides??={};const previous=draft.chat_model;
 if(previous)draft.llm_overrides[previous]=pick(draft,state);
 if(next!==previous){draft.chat_model=next;Object.assign(draft,llmOptions(state).defaults[draft.profile],draft.llm_overrides[next]||{});}
}
export function renderLlmPreferences(container,draft,state,onChange){
 const models=state.models.filter(m=>m.capabilities.includes('chat'));
 if(!selected||!models.some(m=>m.id===selected))selected=draft.chat_model||models[0]?.id;
 const model=models.find(m=>m.id===selected);
 if(!model){container.innerHTML='<h3>Parametri dei modelli chat</h3><p>Collega o scarica un LLM dal Catalogo modelli.</p>';return;}
 const values=selected===draft.chat_model?pick(draft,state):{...llmOptions(state).defaults[draft.profile],...draft.llm_overrides?.[selected]};
 const num=(key,label,min,max,step=1)=>`<label class="field"><span>${label}</span><input data-setting="${key}" data-llm-setting="${key}" type="number" min="${min}" max="${max}" step="${step}" value="${values[key]}"></label>`;
 container.innerHTML=`<h3>Parametri dei modelli chat</h3><label class="field"><span>Modello da configurare</span><select id="llm-settings-model">${models.map(m=>`<option value="${esc(m.id)}" ${m.id===selected?'selected':''}>${esc(m.name)}</option>`).join('')}</select><small>${selected===draft.chat_model?'È il modello chat predefinito.':'Stai modificando il suo preset; il modello chat predefinito resta invariato.'} Salva le impostazioni per conservare il preset.</small></label><div class="settings-grid">${num('context','Contesto LLM · token totali',1024,llmOptions(state).max_context)}${num('max_tokens','Max token di risposta',64,8192)}${num('temperature','Temperatura',0,2,.1)}${num('gpu_layers','Layer su GPU',0,999)}<label class="field"><span>Thinking del modello</span><select data-setting="think_level" data-llm-setting="think_level">${['off','low','med','high','xhigh'].map(v=>`<option value="${v}" ${v===values.think_level?'selected':''}>${v}</option>`).join('')}</select></label></div><p id="context-model-note" class="small-note" aria-live="polite"></p><p>Il contesto comprende istruzioni, cronologia, immagini e risposta. Max token di risposta comprende testo e thinking: da 64 a 8192, al massimo metà del contesto.</p><div class="mtp-settings"><label class="mtp-toggle"><input type="checkbox" data-setting="mtp_enabled" data-llm-setting="mtp_enabled" ${values.mtp_enabled?'checked':''}> MTP per questo modello</label>${num('mtp_draft_tokens','Token da anticipare',1,8)}<p id="mtp-model-note" class="small-note"></p></div><h3>Assistant con questo LLM</h3><div class="settings-grid">${num('prompt_max_tokens','Max token istruzioni immagini',256,8192)}${num('music_prompt_max_tokens','Max token stile e testo musica',256,8192)}</div><p class="small-note">Sono limiti di output per Assistant; il contesto totale è quello sopra. Le impostazioni vengono recuperate automaticamente quando selezioni questo LLM.</p><button type="button" id="llm-reset" class="text-button">Ripristina preset iniziale</button>`;
 const context=container.querySelector('[data-llm-setting="context"]'),list=document.createElement('datalist');list.id='context-presets';
 for(const v of [4096,8192,16384,32768,65536,131072,262144,524288,1048576]){const option=document.createElement('option');option.value=v;option.label=(v/1024)+'k';list.append(option);}context.after(list);context.setAttribute('list',list.id);context.setAttribute('aria-describedby','context-model-note');
 const details=()=>{
  const note=container.querySelector('#context-model-note'),declared=model.parameters?.context_length,exceeds=declared&&values.context>declared;
  note.textContent=declared?model.name+' dichiara '+Number(declared).toLocaleString('it-IT')+' token nel GGUF. '+(exceeds?'Il valore scelto supera il contesto dichiarato: compatibilità ed efficacia dell’estensione non sono garantite.':'64k corrispondono a 65.536 token.'):'Contesto massimo non rilevato: verifica le specifiche del modello. Puoi inserire il valore manualmente; 64k corrispondono a 65.536 token.';
  note.classList.toggle('vision-warning',!!exceeds);
  const mtp=model.mtp;container.querySelector('[data-llm-setting="mtp_enabled"]').disabled=!mtp?.supported;
  container.querySelector('[data-llm-setting="mtp_draft_tokens"]').disabled=!mtp?.supported||!values.mtp_enabled;
  container.querySelector('#mtp-model-note').textContent=mtp?.note||'MTP non supportato o non ancora rilevato.';
  container.querySelector('[data-llm-setting="think_level"]').disabled=!model.thinking?.supported;
 };
 const persist=()=>{draft.llm_overrides??={};draft.llm_overrides[selected]={...values};if(selected===draft.chat_model)Object.assign(draft,values);details();onChange?.();};
 for(const input of container.querySelectorAll('[data-llm-setting]'))input.oninput=()=>{values[input.dataset.llmSetting]=input.type==='checkbox'?input.checked:input.type==='number'?Number(input.value):input.value;persist();};
 container.querySelector('#llm-settings-model').onchange=e=>{selected=e.target.value;renderLlmPreferences(container,draft,state,onChange);};
 container.querySelector('#llm-reset').onclick=()=>{Object.assign(values,llmOptions(state).defaults[draft.profile]);persist();renderLlmPreferences(container,draft,state,onChange);};
 details();
}

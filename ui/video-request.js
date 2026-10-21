import {escape as esc} from './render.js';
import {attentionChoices,attentionSelection,attentionParameters,needsAttentionUpdate} from './video-attention.js';

export function effectiveVideoResolution(value,state){
 const model=state?.models.find(m=>m.id===(value.video_model||state.settings.video_model));
 const p={...state?.video_options?.defaults,...state?.settings.video_overrides?.[model?.id],...value.video_parameters};
 const mp=value.video_quality==='medium'?Math.min(p.megapixels??.7,.5):p.megapixels??.7;
 return !model?.remote_media&&!p.experimental_resolution?Math.min(mp,.98):mp;
}

export function videoRequestSummary(value,state){
 const model=state?.models.find(m=>m.id===(value.video_model||state.settings.video_model));
 const p={...state?.video_options?.defaults,...state?.settings.video_overrides?.[model?.id],...value.video_parameters};
 return [model?.name,(model?.remote_media&&value.video_quality!=='medium'&&value.video_parameters?.megapixels==null)?'Risoluzione dal server':effectiveVideoResolution(value,state).toLocaleString('it-IT')+' MP',value.video_parameters?.aspect?'Formato '+value.video_parameters.aspect:'Formato automatico',!model?.remote_media?'Segmenti max '+(value.video_segment_seconds||15)+' s':'',!model?.remote_media?((p.seed??-1)===-1?'Seed casuale':'Seed '+p.seed):'',model?.remote_media?'Server esterno':(attentionChoices.find(([id])=>id===attentionSelection(p))?.[1]||'Automatico · Sage'),p.longtake_enabled?'LongTakeNoCuts · +5 passi/clip':'',model?.remote_media?'':p.pdd_enabled?'PDD On · 8 passi':'PDD Off'].filter(Boolean).join(' · ');
}

export function initVideoRequest({holder,read,save,getState,pickFile}){
 const host=document.createElement('section');host.className='video-chat-request';
 host.innerHTML='<button type="button" class="prompt-choice" id="video-request-toggle" aria-expanded="false" aria-controls="video-request-fields">Impostazioni avanzate</button><div id="video-request-fields" hidden><p class="small-note">Scelte della richiesta: i preset nelle Preferenze restano invariati.</p><div class="video-request-grid"><label class="field"><span>Modello video</span><select id="video-request-model" aria-label="Modello video della richiesta"></select></label><label class="field"><span>Accelerazione attenzione</span><select id="video-request-attention" aria-label="Accelerazione della richiesta"><option value="">Preset del modello</option><option value="veda">VEDA</option><option value="sage">SageAttention</option><option value="pytorch">PyTorch</option><option value="auto">Automatico · Sage</option></select></label><label class="field"><span>PDD</span><select id="video-request-pdd" aria-label="PDD della richiesta"><option value="">Preset del modello</option><option value="off">Spento · passi standard</option><option value="on">Attivo · turbo 8 passi</option></select></label></div><div data-pdd-adapter hidden><label class="field"><span>Adattatore PDD</span><select id="video-request-adapter" aria-label="Adattatore PDD della richiesta"></select></label><button type="button" class="btn small" data-pdd-browse>Scegli file</button><p class="small-note">PDD usa 8 passi, Euler e CFG 1. L’adattatore deve essere compatibile con il modello; sugli Hybrid è sperimentale.</p></div><label class="check"><input type="checkbox" id="video-request-longtake"> LongTakeNoCuts · sperimentale · continuità lunga</label><p class="small-note">5 passi aggiuntivi per clip; può cambiare dettagli e sfondo. Conserva audio, clip modificabili e stacchi voluti della regia.</p><p class="small-note" data-video-request-ready></p><button type="button" class="text-button" data-video-request-reset>Ripristina preset del modello</button></div>';
 holder.append(host);const q=s=>host.querySelector(s),model=q('#video-request-model'),attention=q('#video-request-attention'),pdd=q('#video-request-pdd'),adapter=q('#video-request-adapter');
 const update=changes=>save({...read(),video_parameters:{...read().video_parameters,...changes}});
 q('#video-request-toggle').onclick=()=>save({...read(),video_request_advanced:!read().video_request_advanced});
 model.onchange=()=>{const value=read(),parameters={};for(const key of ['aspect','megapixels','seed'])if(value.video_parameters?.[key]!=null)parameters[key]=value.video_parameters[key];save({...value,video_model:model.value,video_parameters:parameters,video_steps:null});};
 attention.onchange=()=>{const parameters={...read().video_parameters};for(const key of ['attention','attention_chunks','attention_chunks_mode'])delete parameters[key];if(attention.value)Object.assign(parameters,attentionParameters(attention.value,!!getState()?.video_options?.attention_choices));save({...read(),video_parameters:parameters});};
 pdd.onchange=()=>{
  const value=read(),parameters={...value.video_parameters},state=getState();
  const preset=state.settings.video_overrides?.[value.video_model||state.settings.video_model]||{};
  if(pdd.value==='')delete parameters.pdd_enabled;else parameters.pdd_enabled=pdd.value==='on';
  const enabled=parameters.pdd_enabled??preset.pdd_enabled??false;
  if(enabled&&state.video_options?.longtake_experimental)parameters.longtake_enabled=false;
  if(enabled&&!parameters.pdd_lora&&preset.pdd_lora)parameters.pdd_lora=preset.pdd_lora;
  save({...value,video_parameters:parameters,video_steps:enabled?8:null});
 };
 q('#video-request-longtake').onchange=()=>{const on=q('#video-request-longtake').checked;update({longtake_enabled:on,...(on?{pdd_enabled:false}:{})});};
 adapter.onchange=()=>update({pdd_lora:adapter.value});
 q('[data-pdd-browse]').onclick=()=>pickFile?.(adapter.value,path=>{if(path)update({pdd_lora:path});});
 q('[data-video-request-reset]').onclick=()=>save({...read(),video_model:'',video_parameters:{},video_steps:null,video_segment_seconds:null,video_quality:'high'});
 return {render(){
  const state=getState();if(!state)return;
  const value=read(),models=state.models.filter(m=>m.capabilities.includes('video')),id=value.video_model||state.settings.video_model;
  const selected=models.find(m=>m.id===id),preset=state.settings.video_overrides?.[id]||{},parameters=value.video_parameters||{};
  const ready=!!state.video_options?.request_controls,remote=!!selected?.remote_media;
  const signature=JSON.stringify([state.settings.video_model,models.map(m=>[m.id,m.name,m.ready])]);
  if(model.dataset.signature!==signature){model.innerHTML='<option value="">Preset · modello predefinito</option>'+models.map(m=>`<option value="${esc(m.id)}" ${m.ready?'':'disabled'}>${esc(m.name)}${m.ready?'':' · non disponibile'}</option>`).join('');model.dataset.signature=signature;}
  if(value.video_model&&!models.some(m=>m.id===value.video_model)&&![...model.options].some(o=>o.value===value.video_model))model.insertAdjacentHTML('beforeend',`<option value="${esc(value.video_model)}" disabled>Modello selezionato non disponibile</option>`);
  model.value=value.video_model||'';model.disabled=!ready;
  const explicit=!!state.video_options?.attention_choices;
  if(attention.dataset.explicit!==String(explicit)){attention.innerHTML='<option value="">Preset del modello</option>'+attentionChoices.map(([id,label])=>`<option value="${id}" ${!explicit&&needsAttentionUpdate(id)?'disabled':''}>${label}</option>`).join('');attention.dataset.explicit=String(explicit);}
  attention.value=parameters.attention?attentionSelection(parameters):'';attention.disabled=!ready||remote;
  attention.title=explicit?'VEDA 8/56 mantengono il numero scelto. Nel prompt: VEDA 8, VEDA 56 oppure una riga Accelerazione: ComfyKitchen / Sage / nessuna. La scelta nel menu prevale.':'VEDA 8/56 e ComfyKitchen disponibili dopo l’aggiornamento a coda libera; il video attuale continua.';
  pdd.value=typeof parameters.pdd_enabled==='boolean'?(parameters.pdd_enabled?'on':'off'):'';pdd.disabled=!ready||remote;
  const longtake=q('#video-request-longtake');longtake.checked=!!parameters.longtake_enabled;longtake.disabled=remote||!state.video_options?.longtake_experimental;
  const enabled=parameters.pdd_enabled??preset.pdd_enabled??false,path=parameters.pdd_lora||preset.pdd_lora||'';
  const paths=[...new Set([path,...Object.values(state.settings.video_overrides||{}).map(p=>p.pdd_lora)].filter(Boolean))];
  const pathSignature=JSON.stringify(paths);if(adapter.dataset.signature!==pathSignature){adapter.innerHTML='<option value="">Seleziona un adattatore…</option>'+paths.map(path=>`<option value="${esc(path)}">${esc(path.split(/[\\/]/).at(-1))}</option>`).join('');adapter.dataset.signature=pathSignature;}
  adapter.value=path;adapter.disabled=!ready||remote;q('[data-pdd-adapter]').hidden=!enabled||remote;
  q('[data-pdd-browse]').hidden=!pickFile||state.access?.role==='guest';q('[data-pdd-browse]').disabled=!ready;
  q('[data-video-request-reset]').disabled=!ready;
  q('[data-video-request-ready]').textContent=!ready?'I nuovi controlli saranno disponibili dopo il prossimo riavvio del motore. La generazione in corso continua.':remote?'PDD e accelerazione locale si configurano sul server esterno.':enabled&&!path?'Seleziona l’adattatore prima di inviare.':'Valori effettivi: '+videoRequestSummary(value,state);
  q('#video-request-fields').hidden=!value.video_request_advanced;q('#video-request-toggle').setAttribute('aria-expanded',String(!!value.video_request_advanced));
 }};
}

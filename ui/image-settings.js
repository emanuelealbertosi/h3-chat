import {escape as esc} from './render.js';
let selectedModel=null;
export function selectImagePreferencesModel(id){selectedModel=id;}
const globals={sampler:'image_sampler',scheduler:'image_scheduler',cfg:'image_cfg'};

export function renderImagePreferences(container,draft,state,onChange){
 const models=state.models.filter(m=>m.capabilities.some(c=>['create','edit'].includes(c)));
 if(selectedModel===null||(selectedModel&&!models.some(m=>m.id===selectedModel)))selectedModel=draft.create_model||draft.edit_model||'';
 const model=models.find(m=>m.id===selectedModel);
 const preset={width:model?.width??draft.width,height:model?.height??draft.height,steps:model?.steps??draft.steps,cfg:model?.cfg??draft.image_cfg,
  sampler:model?.sampler&&model.sampler!=='auto'?model.sampler:draft.image_sampler,
  scheduler:model?.scheduler&&model.scheduler!=='auto'?model.scheduler:draft.image_scheduler,
  seed:draft.seed,negative_prompt:draft.negative_prompt,strength:model?.strength??draft.strength};
 const override=selectedModel?draft.image_overrides?.[selectedModel]:null,values={...preset,...override};
 const num=(key,label,min,max,step=1)=>`<label class="field"><span>${label}</span><input data-image-setting="${key}" type="number" min="${min}" max="${max}" step="${step}" value="${values[key]}"></label>`;
 const choice=(key,label,choices)=>`<label class="field"><span>${label}</span><select data-image-setting="${key}">${choices.map(value=>`<option value="${value}" ${values[key]===value?'selected':''}>${value==='auto'?'Automatico · modello':value}</option>`).join('')}</select></label>`;
 const label=value=>value==='auto'?'automatico':value;
 container.innerHTML=`<h3>Impostazioni immagini</h3><label class="field"><span>Configurazione del modello</span><select id="image-settings-model"><option value="">Impostazioni generali</option>${models.map(m=>`<option value="${esc(m.id)}" ${m.id===selectedModel?'selected':''}>${esc(m.name)}</option>`).join('')}</select></label><div class="image-preset-summary"><span class="badge">${override?'Personalizzate':'Predefinite'}</span><p>${values.width} × ${values.height} · ${values.steps} step · CFG ${values.cfg}<br>Sampler ${esc(label(values.sampler))} · Scheduler ${esc(label(values.scheduler))}<br>Seed ${values.seed===-1?'casuale':values.seed}</p></div><label class="mtp-toggle"><input type="checkbox" id="image-advanced" data-setting="image_advanced" ${draft.image_advanced?'checked':''}> Avanzate · modifica i parametri</label><div id="image-advanced-fields" ${draft.image_advanced?'':'hidden'}><div class="settings-grid">${num('width','Larghezza (px)',256,1536,64)}${num('height','Altezza (px)',256,1536,64)}${num('steps','Step',1,100)}${num('cfg','CFG',0,30,.1)}${choice('sampler','Sampler',model?.engine==='vision'?state.image_options.vision_samplers:state.image_options.samplers)}${choice('scheduler','Scheduler',model?.engine==='vision'?state.image_options.vision_schedulers:state.image_options.schedulers)}${num('seed','Seed (-1 = casuale)',-1,2147483647)}${model?.engine==='vision'?'<p class="small-note">Editing nativo con riferimenti: denoise 1, dimensioni adattate al primo riferimento.</p>':num('strength','Intensità img2img',.05,1,.05)}</div><label class="field"><span>Negative prompt</span><textarea data-image-setting="negative_prompt" maxlength="8000" rows="3">${esc(values.negative_prompt)}</textarea></label><button type="button" id="image-reset-defaults" class="text-button">Ripristina predefiniti ${model?'del modello':'generali'}</button><p class="small-note">Le personalizzazioni di questo modello hanno precedenza sui valori generali. Nascondere Avanzate conserva i valori salvati.</p></div><p class="small-note">${model?.architecture==='anima'?'Anima usa diffusore, Qwen3-0.6B Base e VAE Qwen Image. Base/Aesthetic: preset 30 step, CFG 4; Turbo: 8 step, CFG 1.':'I preset seguono il modello. Con Automatico, sampler e scheduler vengono risolti dal motore.'} I parametri effettivi sono consultabili attivando Avanzate in chat.</p>`;
 container.querySelector('#image-settings-model').value=selectedModel;
 container.querySelector('#image-settings-model').onchange=e=>{selectedModel=e.target.value;renderImagePreferences(container,draft,state,onChange);onChange?.();};
 container.querySelector('#image-advanced').onchange=e=>{draft.image_advanced=e.target.checked;renderImagePreferences(container,draft,state,onChange);};
 for(const input of container.querySelectorAll('[data-image-setting]'))input.oninput=()=>{
  const key=input.dataset.imageSetting,value=input.type==='number'?Number(input.value):input.value;
  if(selectedModel){draft.image_overrides??={};draft.image_overrides[selectedModel]={...(draft.image_overrides[selectedModel]||{}),[key]:value};}
  else draft[globals[key]||key]=value;
  onChange?.();
 };
 container.querySelector('#image-reset-defaults').onclick=()=>{
  if(selectedModel){delete draft.image_overrides[selectedModel];}
  else{Object.assign(draft,state.image_options.defaults);Object.assign(draft,{width:state.profiles[draft.profile].width,height:state.profiles[draft.profile].height});}
  renderImagePreferences(container,draft,state,onChange);onChange?.();
 };
}

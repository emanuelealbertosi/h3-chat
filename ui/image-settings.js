import {escape as esc} from './render.js';
import {mossNegativeDefault} from './image-negative-defaults.js';
import {IMAGE_FORMATS,imageFormatLabel} from './image-formats.js';
import {imageModelOptions} from './image-model-options.js';
import {mountMossTurbo,mossTurboValues,MOSS_TURBO_RECIPE} from './moss-turbo.js';
let selectedModel=null;
export function selectImagePreferencesModel(id){selectedModel=id;}
const globals={sampler:'image_sampler',scheduler:'image_scheduler',cfg:'image_cfg',aspect:'image_aspect'};

export function renderImagePreferences(container,draft,state,onChange,options={}){
 const models=state.models.filter(m=>m.capabilities.some(c=>['create','edit'].includes(c)));
 if(selectedModel===null||(selectedModel&&!models.some(m=>m.id===selectedModel)))selectedModel=draft.create_model||draft.edit_model||models[0]?.id||'';
 const model=models.find(m=>m.id===selectedModel);
 const preset={width:model?.width??draft.width,height:model?.height??draft.height,steps:model?.steps??draft.steps,cfg:model?.cfg??draft.image_cfg,
  sampler:model?.sampler&&model.sampler!=='auto'?model.sampler:draft.image_sampler,
  scheduler:model?.scheduler&&model.scheduler!=='auto'?model.scheduler:draft.image_scheduler,
  aspect:draft.image_aspect||'auto',seed:draft.seed,negative_prompt:draft.negative_prompt||(model?.architecture==='moss'?mossNegativeDefault(state):'')||'',strength:model?.strength??draft.strength};
 const override=selectedModel?draft.image_overrides?.[selectedModel]:null,values=mossTurboValues({...preset,...override});
 const controls=imageModelOptions(model,state.image_options);
 const num=(key,label,min,max,step=1)=>`<label class="field"><span>${label}</span><input data-image-setting="${key}" type="number" min="${min}" max="${max}" step="${step}" value="${values[key]}"></label>`;
 const label=value=>value==='sequential'?'Prudente · meno VRAM':value==='resident'?'Più GPU · pesi stabili':value==='full'?'Tutto su GPU · sperimentale':value==='group'?'Gruppi di 16 · sperimentale':value==='qwen21_turbo'?'Qwen 2.1 Turbo · 8 passi ufficiali':value==='auto'?'Automatico · modello':value;
 const choice=(key,title,choices)=>`<label class="field"><span>${title}</span><select data-image-setting="${key}">${choices.map(value=>`<option value="${value}" ${values[key]===value?'selected':''}>${key==='aspect'?imageFormatLabel(value):label(value)}</option>`).join('')}</select></label>`;
 const assistantFormat=['anima','sd','sdxl','sd15','sd2'].includes(model?.architecture)?'tag in inglese separati da virgole':'istruzioni descrittive in inglese';
 container.innerHTML=`<h3>Impostazioni immagini</h3><label class="field"><span>Configurazione del modello</span><select id="image-settings-model">${models.map(m=>`<option value="${esc(m.id)}" ${m.id===selectedModel?'selected':''}>${esc(m.name)}</option>`).join('')}</select></label><h4>Formato immagine</h4>${choice('aspect','Proporzioni dell’immagine',IMAGE_FORMATS.map(([value])=>value))}<p class="small-note">Formato o dimensioni richiesti nel prompt (es. 16:9, verticale o 1024x576) prevalgono sulle impostazioni, anche nelle modifiche con immagini.</p><div class="image-preset-summary"><span class="badge">${override?'Personalizzate':'Predefinite'}</span><p>${values.width} × ${values.height} · ${values.steps} step · CFG ${values.cfg}<br>Sampler ${esc(label(values.sampler))} · Scheduler ${esc(label(values.scheduler))}<br>Seed ${values.seed===-1?'casuale':values.seed}</p></div><label class="mtp-toggle"><input type="checkbox" id="image-advanced" data-setting="image_advanced" ${draft.image_advanced?'checked':''}> Avanzate · modifica i parametri</label><div id="image-advanced-fields" ${draft.image_advanced?'':'hidden'}><div class="settings-grid">${num('width','Larghezza (px)',256,controls.max,controls.grid)}${num('height','Altezza (px)',256,controls.max,controls.grid)}${num('steps','Step',1,100)}${num('cfg','CFG',0,30,.1)}${choice('sampler','Sampler',controls.samplers)}${choice('scheduler','Scheduler',controls.schedulers)}${num('seed','Seed (-1 = casuale)',-1,2147483647)}${model?.architecture==='moss'?num('strength','Intensità MOSS img2img',.05,1,.05)+'<p class="small-note">MOSS accetta una sola immagine di partenza con img2img sperimentale. Intensità bassa conserva di più; 1 ridisegna tutto. Non è un modello Edit addestrato. Senza allegati genera da testo; prompt normali anche con Assistant Off. Preset ufficiale: 50 passi, CFG 3, Euler / sgm_uniform.</p>':model?.architecture==='krea2'?'<p class="small-note">Krea 2 genera immagini da testo. I LoRA compatibili si scelgono in chat; non vengono attivati automaticamente.</p>':model?.engine==='vision'?'<p class="small-note">Editing nativo: denoise 1. Con formato Automatico conserva le proporzioni del primo riferimento; con un formato scelto usa la nuova tela.</p>':num('strength','Intensità img2img',.05,1,.05)}</div><label class="field"><span>Negative prompt</span><textarea data-image-setting="negative_prompt" maxlength="8000" rows="3">${esc(values.negative_prompt)}</textarea></label><button type="button" id="image-reset-defaults" class="text-button">Ripristina predefiniti ${model?'del modello':'generali'}</button><p class="small-note">Questo preset appartiene solo al modello selezionato e viene usato anche quando lo scegli in chat. Nascondere Avanzate conserva i valori salvati.</p></div><p class="small-note">${model?.architecture==='anima'?'Anima usa diffusore, Qwen3-0.6B Base e VAE Qwen Image. Base/Aesthetic: preset 30 step, CFG 4; Turbo: 8 step, CFG 1.':'I preset seguono il modello. Con Automatico, sampler e scheduler vengono risolti dal motore.'} I parametri effettivi sono consultabili attivando Avanzate in chat.</p><p class="small-note" id="image-assistant-format">Assistant On: ${assistantFormat}. Assistant Off: viene usato il prompt originale.</p>`;
 const seedControl=document.createElement('section');seedControl.className='image-seed-controls';
 if(model?.architecture==='moss'&&state.image_options.moss_dmd2){
  const turboHost=document.createElement('div');container.querySelector('#image-advanced').closest('label').before(turboHost);
  mountMossTurbo(turboHost,values,state.image_options.moss_dmd2,parameters=>{
   draft.image_overrides??={};draft.image_overrides[selectedModel]=parameters;
   renderImagePreferences(container,draft,state,onChange,options);onChange?.();
  });
  for(const key of Object.keys(MOSS_TURBO_RECIPE))container.querySelector(`[data-image-setting="${key}"]`).disabled=!!values.moss_turbo;
 }
 seedControl.innerHTML='<h4>Seed</h4><label><input type="checkbox" data-image-seed-fixed> Usa un seed fisso</label><button type="button" class="text-button" data-image-preferences-last-seed>Recupera ultimo seed di questo modello</button><p class="small-note" data-image-preferences-seed-note></p>';
 const seedField=container.querySelector('[data-image-setting="seed"]').closest('label');
 container.querySelector('#image-advanced').closest('label').before(seedControl);seedControl.querySelector('label').after(seedField);
 const fixed=seedControl.querySelector('[data-image-seed-fixed]'),last=seedControl.querySelector('button'),seedModel=selectedModel;
 fixed.checked=Number.isInteger(values.seed)&&values.seed>=0;last.disabled=!model||!options.getLastSeed;
 function applySeed(seed,note){
  if(selectedModel!==seedModel)return;
  if(seedModel){draft.image_overrides??={};draft.image_overrides[seedModel]={...draft.image_overrides[seedModel],seed};}else draft.seed=seed;
  renderImagePreferences(container,draft,state,onChange,options);container.querySelector('[data-image-preferences-seed-note]').textContent=note;onChange?.();
 }
 last.onclick=async()=>{last.disabled=true;try{const result=await options.getLastSeed(seedModel);if(!last.isConnected||selectedModel!==seedModel)return;if(!Number.isInteger(result.seed)||result.seed<0)throw Error('Nessun seed effettivo disponibile per questo modello.');applySeed(result.seed,'Seed '+result.seed+' fissato. Premi Salva per usarlo come predefinito; il prompt ha priorità.');}catch(e){if(last.isConnected){seedControl.querySelector('[data-image-preferences-seed-note]').textContent=e.message;fixed.checked=Number.isInteger(values.seed)&&values.seed>=0;}}finally{last.disabled=false;}};
 fixed.oninput=event=>{event.stopPropagation();if(!fixed.checked)applySeed(-1,'Seed casuale per ogni generazione. Premi Salva per confermare.');else if(!Number.isInteger(values.seed)||values.seed<0)last.click();};
 container.querySelector('#image-settings-model').value=selectedModel;
 container.querySelector('#image-settings-model').onchange=e=>{selectedModel=e.target.value;renderImagePreferences(container,draft,state,onChange,options);onChange?.();};
 container.querySelector('#image-advanced').onchange=e=>{draft.image_advanced=e.target.checked;renderImagePreferences(container,draft,state,onChange,options);};
 for(const input of container.querySelectorAll('[data-image-setting]'))input.oninput=()=>{
  const key=input.dataset.imageSetting,value=input.type==='number'?Number(input.value):input.value;
  if(selectedModel){draft.image_overrides??={};draft.image_overrides[selectedModel]={...values,...(draft.image_overrides[selectedModel]||{}),[key]:value};}
  else draft[globals[key]||key]=value;
  if(key==='seed')fixed.checked=Number.isInteger(value)&&value>=0;
  onChange?.();
 };
 container.querySelector('#image-reset-defaults').onclick=()=>{
  if(selectedModel){delete draft.image_overrides[selectedModel];}
  else{Object.assign(draft,state.image_options.defaults);Object.assign(draft,{width:state.profiles[draft.profile].width,height:state.profiles[draft.profile].height});}
  renderImagePreferences(container,draft,state,onChange,options);onChange?.();
 };
}

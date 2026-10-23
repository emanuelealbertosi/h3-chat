import {escape as esc} from './render.js';

export const minimaxDefaults={seed:0,max_duration:120,cfg_scale:1.5,top_k:50,num_inference_steps:30,diffusion_cfg:1,sampler:'euler',scheduler:'simple'};
export function chosenMusicModel(state,value){return state?.models.find(m=>m.id===(value.music_model||state.settings.music_quality_profiles?.[value.music_quality||state.settings.music_quality]?.model||state.settings.music_model));}
export function musicParameters(state,value){
 const model=chosenMusicModel(state,value);if(!model)return null;
 const quality=!value.music_model&&state.settings.music_quality_profiles?.[value.music_quality||state.settings.music_quality];
 return {...(model.architecture==='minimax-music'?minimaxDefaults:state.music_options?.defaults),...state.settings.music_overrides?.[model.id],...(quality?.model?{num_inference_steps:quality.steps}:{}),...value.music_presets?.[model.id],...(value.music_resing?{cot:'full'}:{})};
}
export function initMusicRequest({read,save,getState}){
 const panel=document.querySelector('#music-inputs'),section=document.createElement('section');section.className='music-request prompt-field';panel.prepend(section);let signature='';
 const update=(model,key,value)=>save({...read(),music_presets:{...read().music_presets,[model.id]:{...read().music_presets?.[model.id],[key]:value}}});
 function render(){
  const state=getState();if(!state)return;const value=read(),model=chosenMusicModel(state,value),mini=model?.architecture==='minimax-music';
  const models=state.models.filter(m=>m.capabilities.includes('music')),next=JSON.stringify([models.map(m=>[m.id,m.name,m.ready]),model?.id]);
  if(signature!==next){
   signature=next;section.innerHTML='<label class="field"><span>Motore musicale per questa chat</span><select data-music-request-model><option value="">Predefinito / qualità scelta</option>'+models.map(m=>`<option value="${esc(m.id)}" ${m.ready?'':'disabled'}>${esc(m.name)}${m.ready?'':' · non disponibile'}</option>`).join('')+'</select></label><p class="small-note" data-music-engine-note></p><div class="settings-grid" data-music-request-parameters></div>';
   section.querySelector('select').onchange=event=>{const selected=state.models.find(m=>m.id===event.target.value);save({...read(),music_model:event.target.value,music_quality:'model',...(selected?.architecture==='minimax-music'?{music_resing:false}: {})});render();};
   const controls=section.querySelector('[data-music-request-parameters]');
   const numbers=mini?[['seed','Seed (-1 = casuale)',-1,9007199254740991,1],['num_inference_steps','Passi di sintesi',1,128,1],['cfg_scale','CFG encoder musicale',0,100,.1],['top_k','Top K encoder',1,16384,1],['diffusion_cfg','CFG sintesi audio',0,20,.1]]:[['seed','Seed (-1 = casuale)',-1,9007199254740991,1],['num_inference_steps','Passi di sintesi',1,128,1],['cfg_scale','CFG',0,20,.1]];
   for(const [key,label,min,max,step] of numbers)controls.insertAdjacentHTML('beforeend',`<label class="field"><span>${label}</span><input type="number" data-music-request="${key}" min="${min}" max="${max}" step="${step}"></label>`);
   if(mini)for(const [key,values] of [['sampler',state.image_options?.vision_samplers||['euler']],['scheduler',state.image_options?.vision_schedulers||['simple']]])controls.insertAdjacentHTML('beforeend',`<label class="field"><span>${key==='sampler'?'Sampler':'Scheduler'}</span><select data-music-request="${key}">${values.filter(v=>v!=='qwen21_turbo').map(v=>`<option>${esc(v)}</option>`).join('')}</select></label>`);
   else controls.insertAdjacentHTML('beforeend','<label class="field"><span>Pianificazione musicale</span><select data-music-request="cot"><option value="full">Melodia e accordi</option><option value="melody">Solo melodia</option><option value="off">Diretto</option></select></label>');
   for(const input of controls.querySelectorAll('[data-music-request]'))input.oninput=()=>{if(model)update(model,input.dataset.musicRequest,input.type==='number'?Number(input.value):input.value);};
  }
  section.querySelector('[data-music-request-model]').value=value.music_model||'';
  section.querySelector('[data-music-engine-note]').textContent=mini?'MiniMax Music 3: descrizione musicale e testo, poi sintesi audio. Senza limite esplicito usa massimo 120 s. ABC e Re-sing con melodia originale richiedono YuE2.':'YuE2: stile, testo e spartito ABC facoltativo. Re-sing usa la melodia della canzone allegata e conserva la base originale.';
  const p=musicParameters(state,value)||{};
  for(const input of section.querySelectorAll('[data-music-request]'))if(document.activeElement!==input)input.value=p[input.dataset.musicRequest]??'';
  const abc=panel.querySelector('[data-music-field="abc"]')?.closest('label,section');if(abc)abc.hidden=!!mini||!!value.music_resing;
  const cot=section.querySelector('[data-music-request="cot"]');if(cot)cot.disabled=!!value.music_resing;
  if(value.music_resing)section.querySelector('[data-music-engine-note]').textContent+=' Allega una canzone (3 s–5 min). Il campo Testo ha la priorità; se è vuoto Assistant inventa il nuovo testo dal prompt, anche con Assistant Off. La melodia viene letta dalla canzone.';
  section.hidden=!state.music_options?.request_controls;
  const quality=panel.querySelector('[data-music-quality]');if(quality)quality.hidden=!!value.music_model;
  const duration=panel.querySelector('[data-duration-seconds="chat"]');if(duration)duration.max=mini?'360':'900';
 }
 return {render};
}

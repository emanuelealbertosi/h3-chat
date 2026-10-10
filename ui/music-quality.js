import {escape as esc} from './render.js';
const defaults={high:{model:'',steps:60},low:{model:'',steps:32}};
const names={model:'Parametri del modello',high:'Alta',low:'Bassa'};
export function musicQualitySummary(state,settings,choice=''){
 const quality=choice||settings.music_quality||'model',profile=settings.music_quality_profiles?.[quality]||defaults[quality];
 const id=profile?.model||settings.music_model,model=state.models.find(m=>m.id===id);
 const steps=profile?.steps??settings.music_overrides?.[id]?.num_inference_steps??state.music_options?.defaults?.num_inference_steps??32;
 return profile&&!profile.model?names[quality]+' · scegli il modello nelle impostazioni':(names[quality]||names.model)+' · '+(model?.name||'Modello non disponibile')+' · '+steps+' passi';
}
export function initMusicQuality({read,save,getState}){
 const holder=document.querySelector('#music-inputs'),section=document.createElement('section');section.className='prompt-field';section.dataset.musicQuality='';
 section.innerHTML='<span class="prompt-field-label">Qualità musicale</span><div class="prompt-choices" aria-label="Qualità musicale"></div><p class="small-note" data-music-quality-summary></p>';
 const group=section.querySelector('.prompt-choices');
 for(const [id,label] of [['','Predefinita'],['high','Alta'],['low','Bassa']]){const b=document.createElement('button');b.type='button';b.className='prompt-choice';b.dataset.musicQuality=id;b.textContent=label;b.onclick=()=>save({...read(),music_quality:id});group.append(b);}
 holder.prepend(section);
 return {render(){const state=getState();if(!state)return;const choice=read().music_quality||'';for(const b of group.children){b.setAttribute('aria-pressed',String(b.dataset.musicQuality===choice));const profile=state.settings.music_quality_profiles?.[b.dataset.musicQuality];b.disabled=!!b.dataset.musicQuality&&!profile?.model;b.title=b.disabled?'Collega un modello a questo preset in Impostazioni → Musica.':'';}section.querySelector('[data-music-quality-summary]').textContent=musicQualitySummary(state,state.settings,choice)+' · Alta usa normalmente BF16 e 60 passi; Bassa Q8 e 32 passi. Modelli e passi sono modificabili nelle impostazioni.';}};
}
export function renderMusicQualityPreferences(container,{state,draft,changed,rerender,onModel=()=>{}}){
 draft.music_quality??='model';draft.music_quality_profiles??=structuredClone(defaults);
 const models=state.models.filter(m=>m.capabilities.includes('music'));
 const section=document.createElement('section');section.className='infographic-advanced music-quality-presets';
 section.innerHTML='<h3>Qualità musicale</h3><p class="small-note">Alta: collega YuE2 BF16, 60 passi. Bassa: collega YuE2 Q8, 32 passi. I file restano nei percorsi scelti con «Sfoglia e collega YuE2». La voce narrata usa le proprie impostazioni TTS.</p><div class="prompt-choices" aria-label="Qualità musica predefinita">'+Object.entries(names).map(([id,label])=>`<button type="button" class="prompt-choice" data-music-default-quality="${id}" aria-pressed="${draft.music_quality===id}" ${id!=='model'&&!draft.music_quality_profiles[id].model?'disabled':''}>${label}</button>`).join('')+'</div>';
 const fields=document.createElement('div');fields.className='settings-grid';
 for(const id of ['high','low']){
  const profile=draft.music_quality_profiles[id];
  fields.insertAdjacentHTML('beforeend',`<label class="field"><span>Modello qualità ${names[id]}</span><select data-music-quality-model="${id}"><option value="">Scegli un modello collegato…</option>${models.map(m=>`<option value="${esc(m.id)}" ${m.id===profile.model?'selected':''}>${esc(m.name)}${m.ready?'':' · non disponibile'}</option>`).join('')}</select></label><label class="field"><span>Passi qualità ${names[id]}</span><input type="number" min="1" max="128" step="1" data-music-quality-steps="${id}" value="${profile.steps}"></label>`);
 }
 section.append(fields);container.querySelector('.music-preset-summary').before(section);
 for(const b of section.querySelectorAll('[data-music-default-quality]'))b.onclick=()=>{draft.music_quality=b.dataset.musicDefaultQuality;const profile=draft.music_quality_profiles[draft.music_quality];if(profile?.model){draft.music_model=profile.model;onModel(profile.model);}rerender();changed();};
 for(const input of section.querySelectorAll('[data-music-quality-model]'))input.onchange=()=>{const id=input.dataset.musicQualityModel;draft.music_quality_profiles[id].model=input.value;if(draft.music_quality===id){draft.music_model=input.value;onModel(input.value);}rerender();changed();};
 for(const input of section.querySelectorAll('[data-music-quality-steps]'))input.oninput=()=>{draft.music_quality_profiles[input.dataset.musicQualitySteps].steps=Number(input.value);changed();};
}

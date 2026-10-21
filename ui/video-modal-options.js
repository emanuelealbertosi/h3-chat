import {escape as esc} from './render.js';
import {videoSeed} from './video-seed.js';
import {bindAttention} from './video-attention.js';

// Request-local model/size/acceleration controls; saved presets stay unchanged.
export function videoModalOptions(form,data,{parameters={},pickFile,onModel,initialLoras=[],originalSeeds=false}={}){
 const explicitSeed=parameters.seed;
 const models=data.models||[],original=data.model_id||models[0]?.id||'';
 const originalPreset=models.find(m=>m.id===original)?.parameters||{};
 parameters={...originalPreset,...parameters};
 let launchParameters={...parameters};
 // Standard videos saved before PDD setup have an empty adapter path. Reuse
 // this model's configured adapter without enabling Turbo automatically.
 if(!parameters.pdd_lora)parameters.pdd_lora=originalPreset.pdd_lora||'';
 const host=document.createElement('section');host.className='video-modal-options';
 host.innerHTML=`${models.length?`<label class="field"><span>Modello per questa generazione</span><select name="model">${models.map(m=>`<option value="${esc(m.id)}" ${m.id===original?'selected':''}>${esc(m.name)}</option>`).join('')}</select></label>`:''}<label class="check"><input type="checkbox" name="experimental_resolution" ${parameters.experimental_resolution?'checked':''}> Risoluzione sperimentale · fino a 2 MP</label><p class="small-note">Oltre 0,98 MP aumentano memoria e tempi. L’opzione si applica soltanto a questa richiesta.</p><details><summary>PDD · turbo a 8 passi</summary><label class="check"><input name="pdd_enabled" type="checkbox" ${parameters.pdd_enabled?'checked':''}> Usa adattatore PDD</label><label class="field"><span>Adattatore PDD compatibile (FL2VA o Ref2VA)</span><input name="pdd_lora" type="text" value="${esc(parameters.pdd_lora||'')}" placeholder="Percorso del file .safetensors"></label>${pickFile?'<button class="btn small" type="button" data-pdd-file>Sfoglia adattatore</button>':''}<p class="small-note">PDD richiede il file compatibile con il diffusore e usa 8 passi, Euler, CFG 1 e shift 12/3. Sui modelli modificati è sperimentale.</p></details>`;
 if(!form.querySelector('[name="attention"]'))host.insertAdjacentHTML('beforeend',`<label class="field"><span>Accelerazione attenzione</span><select name="attention">${[['auto','Automatico · Sage'],['veda','VEDA'],['sage','SageAttention'],['pytorch','PyTorch']].map(([id,label])=>`<option value="${id}" ${id===(parameters.attention||'auto')?'selected':''}>${label}</option>`).join('')}</select></label>`);
 const longtake=document.createElement('details');longtake.innerHTML='<summary>LongTakeNoCuts · sperimentale</summary><label class="check"><input type="checkbox" name="longtake_enabled"> Continuità lunga e rifinitura delle clip selezionate</label><p class="small-note">Aggiunge 5 passi per clip. Usa il movimento della versione precedente quando compatibile; conserva gli stacchi della regia e l’audio. Può cambiare sfondo e dettagli. Le modifiche locali non rigenerano le clip vicine. Nessuna segmentazione automatica.</p><p class="small-note" data-longtake-ready></p>';host.append(longtake);
 const longtakeInput=longtake.querySelector('input');longtakeInput.checked=!!parameters.longtake_enabled;longtakeInput.disabled=!data.longtake_experimental;longtake.querySelector('[data-longtake-ready]').textContent=data.longtake_experimental?'':'Disponibile dopo l’aggiornamento del motore, al termine della generazione in corso.';
 form.prepend(host);const q=s=>host.querySelector(s),attention=form.querySelector('[name="attention"]');
 const attentionControl=bindAttention(attention,{parameters,explicit:!!data.attention_choices});
 const attentionNote=document.createElement('p');attentionNote.className='small-note';attentionNote.textContent=data.attention_choices?'VEDA 8 e 56 rispettano il numero scelto. VEDA automatico conserva la protezione memoria. ComfyKitchen richiede il kernel INT8 compatibile. PyTorch mantiene le ottimizzazioni native.':'VEDA 8/56 e ComfyKitchen si abiliteranno dopo l’aggiornamento a coda libera.';(attention.closest('label')||attention).after(attentionNote);
 const referenceSeed=()=>{
  if(!Array.isArray(data.clips))return data.parameters?.seed;
  const first=data.clips.find(c=>c.clip===1);if(!first)return undefined;
  const versions=first.versions||[],chosen=versions.find(v=>v.id===first.selected_version);
  const valid=v=>Number.isInteger(v?.seed)&&v.seed>=0&&v.seed<=2147483647;
  return (valid(chosen)?chosen:versions.find(valid))?.seed;
 };
 const seed=videoSeed(host,{label:originalSeeds?'Seed ricreazione':'Seed clip',initial:originalSeeds?undefined:explicitSeed,preset:parameters.seed??-1,original:originalSeeds,referenceSeed});
 const modelField=q('[name="model"]')?.closest('label');if(modelField)modelField.after(seed.element);else host.prepend(seed.element);
 const library=[...(data.loras||[])];let selected=[...(parameters.loras||[])];
 for(const item of initialLoras){const found=library.find(x=>x.id===item.id);if(found&&item.model_id===original&&!selected.some(x=>x.path===found.path))selected.push({path:found.path,weight:item.weight});}
 const adapters=document.createElement('details');adapters.className='video-lora-options';
 adapters.innerHTML='<summary>LoRA video · modifica mirata</summary><div data-video-loras></div><label class="field"><span>Guida del video originale</span><select name="source_conditioning"><option value="reference">Riferimento leggero · risoluzione separata</option><option value="aligned">Guida allineata · stessa griglia del video finale</option></select></label><p class="small-note">Character Swap e VFX Edit usano la guida allineata. Richiede più memoria e tempo: la risoluzione sorgente separata non si applica. Inizia con un tratto breve a 0,50 MP. Non garantisce una copia esatta dei movimenti.</p>';
 host.append(adapters);const sourceMode=adapters.querySelector('[name="source_conditioning"]');sourceMode.value=parameters.source_conditioning||'reference';
 const customAdapters=()=>selected.filter(x=>x.weight&&library.find(l=>l.path===x.path)?.profile==='custom');
 const explainPddConflict=items=>'PDD non attivato: combinazione non verificata con '+items.map(x=>library.find(l=>l.path===x.path)?.name||x.path.split(/[\\/]/).at(-1)).join(', ')+'. I LoRA restano selezionati. Per usare PDD, rimuovili esplicitamente.';
 const syncAdapters=()=>{
  const requires=selected.some(x=>x.weight&&library.find(l=>l.path===x.path)?.profile!=='custom');
  sourceMode.disabled=requires;if(requires)sourceMode.value='aligned';
  if(q('[name="pdd_enabled"]').checked&&customAdapters().length){
   q('[name="pdd_enabled"]').checked=false;
   compatibility.textContent=explainPddConflict(customAdapters());
  }
  if(selected.length)adapters.open=true;
  form.dataset.sourceConditioning=sourceMode.value;form.dispatchEvent(new Event('source-conditioning'));
 };
 sourceMode.onchange=()=>{form.dataset.sourceConditioning=sourceMode.value;form.dispatchEvent(new Event('source-conditioning'));};
 function renderAdapters(){
  const list=adapters.querySelector('[data-video-loras]');
  list.innerHTML=library.map((l,i)=>{const item=selected.find(x=>x.path===l.path);return `<label class="lora-item"><input type="checkbox" data-video-lora="${i}" ${item?'checked':''}><span><strong>${esc(l.name)}</strong><small>${esc(l.profile==='character_swap'?'Sostituzione personaggio':l.profile==='vfx_ffp'?'Modifica attributi · primo frame modificato facoltativo':'LoRA H3')}</small></span><input type="number" aria-label="Peso ${esc(l.name)}" data-video-lora-weight="${i}" min="-2" max="2" step="0.1" value="${item?.weight??1}" ${item?'':'disabled'}></label>`;}).join('')||'<p class="small-note">Collega una cartella LoRA nelle Preferenze, oppure scegli un file MiniMax H3.</p>';
  for(const box of list.querySelectorAll('[data-video-lora]'))box.onchange=()=>{const l=library[Number(box.dataset.videoLora)];selected=selected.filter(x=>x.path!==l.path);if(box.checked)selected.push({path:l.path,weight:1});renderAdapters();};
  for(const input of list.querySelectorAll('[data-video-lora-weight]'))input.onchange=()=>{const l=library[Number(input.dataset.videoLoraWeight)],item=selected.find(x=>x.path===l.path);if(item)item.weight=Number(input.value);syncAdapters();};
  syncAdapters();
 }
 if(pickFile){const browse=document.createElement('button');browse.type='button';browse.className='btn small';browse.textContent='Scegli LoRA dal filesystem';browse.onclick=()=>pickFile('',path=>{if(!path)return;if(!library.some(x=>x.path===path))library.push({path,name:path.split(/[\\/]/).at(-1),profile:path.includes('character_swap')?'character_swap':path.includes('vfx_edit')?'vfx_ffp':'custom'});if(!selected.some(x=>x.path===path))selected.push({path,weight:1});renderAdapters();});adapters.append(browse);}
 for(const item of selected)if(!library.some(x=>x.path===item.path))library.push({path:item.path,name:item.path.split(/[\\/]/).at(-1),profile:item.path.includes('character_swap')?'character_swap':item.path.includes('vfx_edit')?'vfx_ffp':'custom'});
 const compatibility=document.createElement('p');compatibility.className='small-note';compatibility.setAttribute('role','status');host.append(compatibility);
 renderAdapters();
 const resolution=()=>{const input=form.querySelector('[name="megapixels"]');if(input){input.max=q('[name="experimental_resolution"]').checked?'2':'0.98';if(Number(input.value)>Number(input.max))input.value=input.max;}};
 q('[name="experimental_resolution"]').onchange=resolution;resolution();
 if(pickFile)q('[data-pdd-file]').onclick=()=>pickFile(q('[name="pdd_lora"]').value,path=>{q('[name="pdd_lora"]').value=path;});
 longtakeInput.onchange=()=>{if(longtakeInput.checked)q('[name="pdd_enabled"]').checked=false;};
 const turbo=()=>{if(!q('[name="pdd_enabled"]').checked)return;longtakeInput.checked=false;
  for(const [key,v] of Object.entries({steps:8,video_steps:8,sampler:'euler',cfg:1})){
   const input=form.querySelector(`[name="${key}"]`);if(input){input.value=String(v);input.dispatchEvent(new Event('input',{bubbles:true}));}
  }
 };
 q('[name="pdd_enabled"]').onchange=()=>{
  compatibility.textContent='';
  if(q('[name="pdd_enabled"]').checked){
   const rejected=customAdapters();
   if(rejected.length){q('[name="pdd_enabled"]').checked=false;compatibility.textContent=explainPddConflict(rejected);return;}
  }
  turbo();
 };
 turbo();
 form.addEventListener('input',e=>{if(['steps','video_steps'].includes(e.target.name)&&e.target.value!==''&&Number(e.target.value)!==8)q('[name="pdd_enabled"]').checked=false;});
 const select=q('[name="model"]');if(select)select.onchange=()=>{
  const preset=models.find(m=>m.id===select.value)?.parameters||{};
  onModel?.(preset);
  launchParameters={...preset};
  seed.setPreset(preset.seed??-1);
  attentionControl.set(preset);
  longtakeInput.checked=false;
  q('[name="experimental_resolution"]').checked=!!preset.experimental_resolution;
  q('[name="pdd_enabled"]').checked=!!preset.pdd_enabled;q('[name="pdd_lora"]').value=preset.pdd_lora||'';
  resolution();syncAdapters();turbo();
 };
 return {set(selection){
  const model=models.find(m=>m.id===selection.model);if(!model)throw Error('Il modello dell’ultimo lancio non è disponibile: ricollegalo oppure scegli un altro modello.');
  if(select)select.value=model.id;
  const p={...model.parameters,...selection.parameters};launchParameters={...p};
  seed.set(p.seed,model.parameters?.seed??-1);attentionControl.set(p);
  longtakeInput.checked=!!p.longtake_enabled;
  q('[name="experimental_resolution"]').checked=!!p.experimental_resolution;
  q('[name="pdd_enabled"]').checked=!!p.pdd_enabled;q('[name="pdd_lora"]').value=p.pdd_lora||'';
  selected=(p.loras||[]).map(x=>({...x}));
  for(const item of selected)if(!library.some(l=>l.path===item.path))library.push({path:item.path,name:item.path.split(/[\\/]/).at(-1),profile:item.path.includes('character_swap')?'character_swap':item.path.includes('vfx_edit')?'vfx_ffp':'custom'});
  sourceMode.value=p.source_conditioning||'reference';resolution();renderAdapters();turbo();
 },read(){const enabled=q('[name="pdd_enabled"]').checked,number=seed.read();return {model:select?.value||original,
  parameters:{...(data.launch_settings?Object.fromEntries(['steps','cfg','sampler','scheduler','offload','shift_video','shift_audio','veda_predictor','veda_sparsity','veda_reference_sparsity'].filter(k=>launchParameters[k]!==undefined).map(k=>[k,launchParameters[k]])):{}),...(data.longtake_experimental?{longtake_enabled:longtakeInput.checked}:{}),...attentionControl.read(),experimental_resolution:q('[name="experimental_resolution"]').checked,pdd_enabled:enabled,pdd_lora:q('[name="pdd_lora"]').value,
   loras:selected,source_conditioning:sourceMode.value,...(number==null?{}:{seed:number}),...(enabled?{steps:8,sampler:'euler',cfg:1}:{})}};}};
}

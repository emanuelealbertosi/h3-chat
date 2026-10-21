import {escape as esc} from './render.js';
import {initMossPresets} from './moss-presets.js';
import {mossNegativeDefault} from './image-negative-defaults.js';
import {IMAGE_FORMATS,imageFormatLabel} from './image-formats.js';
import {imageModelOptions} from './image-model-options.js';

export function imageRequestValues(state,value){
 const model=state?.models.find(m=>m.id===value.image_model);if(!model)return null;
 const s=state.settings,preset={width:model.width??s.width,height:model.height??s.height,steps:model.steps??s.steps,cfg:model.cfg??s.image_cfg,
  sampler:model.sampler&&model.sampler!=='auto'?model.sampler:s.image_sampler,scheduler:model.scheduler&&model.scheduler!=='auto'?model.scheduler:s.image_scheduler,
  aspect:s.image_aspect||'auto',seed:s.seed,negative_prompt:s.negative_prompt||(model.architecture==='moss'?mossNegativeDefault(state):'')||'',strength:model.strength??s.strength,...(model.architecture==='fibo2'&&!model.quantization?{fibo_offload:'sequential'}:{})};
 const p={...preset,...s.image_overrides?.[model.id],...value.image_presets?.[model.id]};
 if(p.megapixels===undefined)p.megapixels=Number((p.width*p.height/1e6).toFixed(2));
 const ratio=p.aspect&&p.aspect!=='auto'?p.aspect.split(':').map(Number):[p.width,p.height],area=p.megapixels*1e6;
 if(Number.isFinite(area)&&area>0){
  const grid=imageModelOptions(model,state.image_options||{}).grid;
  p.width=Math.ceil(Math.sqrt(area*ratio[0]/ratio[1])/grid)*grid;p.height=Math.ceil(area/p.width/grid)*grid;
  if(model.architecture==='moss'&&p.aspect!=='auto'){const k=Math.ceil(Math.sqrt(area/(ratio[0]*ratio[1])));p.width=ratio[0]*k;p.height=ratio[1]*k;}
 }
 return p;
}

export function imageRequestParameters(state,value){
 const p=imageRequestValues(state,value);if(!p)return null;
 for(const [key,min,max] of [['steps',1,100],['seed',-1,2147483647]]){
  if(!Number.isInteger(p[key])||p[key]<min||p[key]>max)throw Error(key==='seed'?'Seed immagine: usa -1 oppure un intero da 0 a 2147483647.':'Passi immagine: scegli un intero tra 1 e 100.');
 }
 if(!Number.isFinite(p.megapixels)||p.megapixels<.25||p.megapixels>4)throw Error('Megapixel: scegli un valore tra 0,25 e 4.');
 const m=state.models.find(m=>m.id===value.image_model),s=state.settings,overrides={...s.image_overrides?.[m.id],...value.image_presets?.[m.id]};
 p.width=overrides.width??m.width??s.width;p.height=overrides.height??m.height??s.height;
 if(!Number.isFinite(p.cfg)||p.cfg<0||p.cfg>30)throw Error('CFG immagine: scegli un valore tra 0 e 30.');
 if(m.architecture==='moss'&&(!Number.isFinite(p.strength)||p.strength<.05||p.strength>1))throw Error('Intensità MOSS img2img: scegli da 0,05 a 1.');
 return p;
}

export function initImageRequest({holder,getState,visualControls,savePresets,getLastSeed,notify}){
 const formatHost=document.createElement('section');formatHost.className='image-format-controls';holder.prepend(formatHost);
 const host=document.createElement('section');host.className='image-request-controls';holder.append(host);let signature='',lastEditedKey=null,presetsUI=null;
 function render(force=false){
  const state=getState(),value=visualControls.read(),model=state?.models.find(m=>m.id===value.image_model),p=imageRequestValues(state,value);host.hidden=formatHost.hidden=!model||!state?.image_options?.request_controls;if(host.hidden)return;
  const options=state.image_options,{samplers,schedulers}=imageModelOptions(model,options);
  const next=JSON.stringify([model.id,samplers,schedulers,!!options.moss_presets,!!options.last_seed]);
  if(signature!==next){
   signature=next;
   const number=(key,label,min,max,step=1)=>`<label class="field"><span>${label}</span><input type="number" data-image-request="${key}" min="${min}" max="${max}" step="${step}"></label>`;
   const choice=(key,label,items)=>`<label class="field"><span>${label}</span><select data-image-request="${key}">${items.map(x=>`<option value="${esc(x)}">${x==='auto'?'Automatico · preset':x==='sequential'?'Prudente · meno VRAM':x==='resident'?'Più GPU · pesi stabili':x==='full'?'Tutto su GPU · sperimentale':x==='group'?'Gruppi di 16 · sperimentale':esc(x)}</option>`).join('')}</select></label>`;
   formatHost.innerHTML=`<h3>Formato immagine</h3><div class="settings-grid"><label class="field"><span>Proporzioni dell’immagine</span><select data-image-request="aspect">${IMAGE_FORMATS.map(([value,label])=>`<option value="${value}">${label}</option>`).join('')}</select></label>${number('megapixels','Megapixel (MP)',.25,4,.05)}</div><p class="small-note" data-image-canvas></p><p class="small-note">Vale per il modello selezionato e resta salvato in questa chat. Il formato scritto nel prompt ha priorità: per esempio «16:9», «9:16» o «quadrato», anche nei lotti e nelle modifiche con immagini.</p>`;
   host.innerHTML=`<h3>Parametri per questa chat</h3><div class="settings-grid">${number('steps','Passi',1,100)}${number('cfg','CFG',0,30,.1)}${choice('sampler','Sampler',samplers)}${choice('scheduler','Scheduler',schedulers)}${model.architecture==='fibo2'&&!model.quantization?choice('fibo_offload','Memoria GPU',['sequential','resident','group','full']):''}${number('seed','Seed (-1 = casuale)',-1,2147483647)}${model.architecture==='moss'?number('strength','Intensità img2img · con un allegato',.05,1,.05):''}</div><label class="field"><span>Negative prompt</span><textarea rows="2" maxlength="8000" data-image-request="negative_prompt"></textarea></label><p class="small-note">Valgono dal prossimo invio e restano salvati per questo modello in questa chat. I valori espliciti nel prompt prevalgono: formato, dimensioni, passi, CFG, sampler, scheduler e seed. Esempi: 16:9, 1024x576, seed 42. Non cambiano le Preferenze generali.</p>${model.quantization==='int8_convrot'?'<p class="small-note">FIBO INT8 conserva i pesi quantizzati e trasferisce i componenti tra encoder, generazione e decodifica.</p>':model.architecture==='fibo2'?'<p class="small-note">Tutto su GPU: la RAM condivisa dipende dal driver e può essere più lenta o non evitare un errore di memoria. Più GPU conserva una parte dei pesi in VRAM.</p>':''}${model.architecture==='moss'?'<p class="small-note">MOSS: puoi allegare una sola immagine per img2img sperimentale. Intensità bassa conserva di più; 1 ridisegna completamente. Non è un modello Edit addestrato: identità e modifiche precise non sono garantite. Senza allegati genera da testo. Prompt normale anche con Assistant Off. Preset: 50 passi, CFG 3, Euler / sgm_uniform. Il seed fisso aiuta a confrontare una modifica alla volta.</p>':''}<button type="button" class="text-button" data-image-request-reset>Ripristina preset del modello</button>`;
   const record=value=>({...value,image_history:{...value.image_history,[model.id]:[...(value.image_history?.[model.id]||[]),value.image_presets?.[model.id]??null].slice(-20)}});
   if(options.last_seed){
    const field=host.querySelector('[data-image-request="seed"]').closest('label'),group=document.createElement('div'),button=document.createElement('button'),note=document.createElement('p');
    group.className='image-seed-controls';button.type='button';button.className='text-button';button.dataset.imageLastSeed='';button.textContent='Usa ultimo seed';
    button.title='Recupera il seed effettivo dell’ultima immagine completata con questo modello, anche in un’altra chat.';
    note.className='small-note';note.dataset.imageLastSeedNote='';field.before(group);group.append(field,button,note);
    button.onclick=async()=>{
     if(button.disabled)return;button.disabled=true;
     try{
      const result=await getLastSeed(model.id);
      if(visualControls.read().image_model!==model.id||!button.isConnected)return;
      if(!Number.isInteger(result.seed)||result.seed<0)throw Error('Nessuna generazione completata con un seed disponibile per questo modello.');
      const value=record(visualControls.read());lastEditedKey=null;
      visualControls.set({...value,image_presets:{...value.image_presets,[model.id]:{...value.image_presets?.[model.id],seed:result.seed}}});
      render(true);note.dataset.seed=String(result.seed);note.textContent='Recuperato seed '+result.seed+' dall’ultima immagine completata. Il valore resta fisso fino alla prossima modifica.';
     }catch(e){notify(e.message,true);}finally{button.disabled=false;}
    };
   }
   presetsUI=null;
   if(model.architecture==='moss'&&options.moss_presets){
    const library=document.createElement('section');library.className='moss-preset-library';host.querySelector('h3').after(library);
    presetsUI=initMossPresets({holder:library,getState,savePresets,notify,
     getParameters:()=>imageRequestParameters(getState(),visualControls.read()),
     applyParameters:parameters=>{const value=record(visualControls.read());lastEditedKey=null;visualControls.set({...value,image_presets:{...value.image_presets,[model.id]:{...value.image_presets?.[model.id],...parameters}}});render(true);}});
   }
   for(const input of [...formatHost.querySelectorAll('[data-image-request]'),...host.querySelectorAll('[data-image-request]')]){
    input.onfocus=()=>{input.undoRecorded=false;};
    input.oninput=()=>{
     const key=input.dataset.imageRequest;let value=visualControls.read();if(!input.undoRecorded||lastEditedKey!==key){value=record(value);input.undoRecorded=true;}lastEditedKey=key;
     const patch={...value.image_presets?.[model.id],[key]:input.type==='number'?(input.value===''?null:Number(input.value)):input.value};
     visualControls.set({...value,image_presets:{...value.image_presets,[model.id]:patch}});
    };
   }
   const undo=document.createElement('button');undo.type='button';undo.className='text-button';undo.dataset.imageRequestUndo='';undo.textContent='↶ Annulla ultima modifica';host.querySelector('[data-image-request-reset]').before(undo);
   undo.onclick=()=>{const value=visualControls.read(),history=[...(value.image_history?.[model.id]||[])];if(!history.length)return;lastEditedKey=null;const previous=history.pop(),presets={...value.image_presets};if(previous===null)delete presets[model.id];else presets[model.id]=previous;visualControls.set({...value,image_presets:presets,image_history:{...value.image_history,[model.id]:history}});render();};
   host.querySelector('[data-image-request-reset]').onclick=()=>{const value=record(visualControls.read()),presets={...value.image_presets};delete presets[model.id];visualControls.set({...value,image_presets:presets});render();};
  }
  for(const input of [...formatHost.querySelectorAll('[data-image-request]'),...host.querySelectorAll('[data-image-request]')])if(force||document.activeElement!==input)input.value=p[input.dataset.imageRequest]??'';
  formatHost.querySelector('[data-image-canvas]').textContent=imageFormatLabel(p.aspect)+' · Uscita: '+p.width+' × '+p.height+' px · '+(p.width*p.height/1e6).toFixed(2)+' MP. La griglia del motore può richiedere un piccolo arrotondamento verso l’alto.';
  host.querySelector('[data-image-request-undo]').disabled=!(value.image_history?.[model.id]?.length);
  const seedNote=host.querySelector('[data-image-last-seed-note]');if(seedNote?.dataset.seed&&seedNote.dataset.seed!==String(p.seed))seedNote.textContent='';
  presetsUI?.render();
 }
 return {render};
}

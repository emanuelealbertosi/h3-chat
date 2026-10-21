import {initVideoRequest,effectiveVideoResolution} from './video-request.js';
import {videoSeed} from './video-seed.js';

export function initVideoQuality({read,save,getState,pickFile}){
 const holder=document.querySelector('#video-hint');
 holder.insertAdjacentHTML('afterbegin','<label>Qualità <select id="video-quality" aria-label="Qualità video MiniMax"><option value="high">Alta · preset attuale</option><option value="medium">Media · più rapida</option></select></label><p id="video-quality-summary" class="small-note"></p>');
 const select=document.querySelector('#video-quality');
 document.querySelector('#video-quality-summary').insertAdjacentHTML('afterend','<label>Risoluzione <select id="video-resolution" aria-label="Risoluzione video della richiesta"><option value="">Preset del modello</option><option value="0.5">0,50 MP</option><option value="0.7">0,70 MP</option><option value="0.98">0,98 MP · nativa</option></select></label><p id="video-resolution-note" class="small-note"></p>');
 const resolution=document.querySelector('#video-resolution');resolution.onchange=()=>{const value=read(),parameters={...value.video_parameters};if(resolution.value)parameters.megapixels=Number(resolution.value);else delete parameters.megapixels;save({...value,video_parameters:parameters,...(resolution.value&&Number(resolution.value)>.5?{video_quality:'high'}:{})});};
 const seedHost=document.createElement('div');document.querySelector('#video-resolution-note').after(seedHost);
 const seed=videoSeed(seedHost,{onChange:value=>{const current=read(),parameters={...current.video_parameters};if(value==null)delete parameters.seed;else parameters.seed=value;save({...current,video_parameters:parameters});}});
 holder.insertAdjacentHTML('afterbegin','<label>Formato <select id="video-format" aria-label="Formato video della richiesta"><option value="">Automatico · prompt / allegati</option><option value="16:9">16:9</option><option value="9:16">9:16</option><option value="1:1">1:1</option><option value="4:3">4:3</option><option value="3:4">3:4</option></select></label><p id="video-format-note" class="small-note"></p>');
 const format=document.querySelector('#video-format');format.onchange=()=>{const value=read(),parameters={...value.video_parameters};if(format.value)parameters.aspect=format.value;else delete parameters.aspect;save({...value,video_parameters:parameters});};
 holder.insertAdjacentHTML('beforeend','<label>Durata segmenti <select id="video-segments" aria-label="Durata massima segmenti video"><option value="">Preset · 15 s</option><option value="5">5 s</option><option value="10">10 s</option><option value="15">15 s</option></select></label><p id="video-segments-note" class="small-note"></p>');
 const segments=document.querySelector('#video-segments');segments.onchange=()=>save({...read(),video_segment_seconds:segments.value?Number(segments.value):null});
 holder.insertAdjacentHTML('beforeend','<label>Passi <select id="video-steps" aria-label="Passi video MiniMax"><option value="">Preset · dal modello</option><option value="12">12 passi</option><option value="16">16 passi</option><option value="20">20 passi</option></select></label>');
 const stepSelect=document.querySelector('#video-steps');stepSelect.onchange=()=>{const value=read(),steps=stepSelect.value===''?null:Number(stepSelect.value),state=getState(),preset=state.settings.video_overrides?.[value.video_model||state.settings.video_model]||{};save({...value,video_steps:steps,...(steps!==null&&steps!==8&&(value.video_parameters?.pdd_enabled??preset.pdd_enabled)?{video_parameters:{...value.video_parameters,pdd_enabled:false}}:{})});};
 holder.insertAdjacentHTML('beforeend','<label>Regia <select id="video-editing" aria-label="Regia video"><option value="continuous">Continuazione · movimento continuo</option><option value="storyboard">Storyboard · stacchi</option><option value="modify">Modifica video · da prompt</option></select></label><p id="video-editing-summary" class="small-note"></p>');
 const editing=document.querySelector('#video-editing');
 editing.onchange=()=>save({...read(),video_editing:editing.value,...(editing.value==='storyboard'?{assistant:true}:{})});
 select.onchange=()=>{const value=read(),parameters={...value.video_parameters};if(select.value==='medium')delete parameters.megapixels;save({...value,video_quality:select.value,video_parameters:parameters});};
 const advanced=initVideoRequest({holder,read,save,getState,pickFile});
 return {validate(){seed.validate();},render(){
  const state=getState();if(!state)return;
  advanced.render();
  const value=read(),maxSegment=value.video_segment_seconds||15;
  format.value=value.video_parameters?.aspect||'';segments.value=value.video_segment_seconds==null?'':String(value.video_segment_seconds);
  const activeModel=state.models.find(m=>m.id===(value.video_model||state.settings.video_model));
  const seedPreset=state.settings.video_overrides?.[activeModel?.id]?.seed??state.video_options?.defaults?.seed??-1;
  seed.set(value.video_parameters?.seed,seedPreset,!state.video_options?.seed_control||!!activeModel?.remote_media,activeModel?.remote_media?'Il seed si configura sul server esterno.':'Il seed in chat sarà attivo dopo il prossimo riavvio del motore, al termine dei lavori in corso.');
  format.disabled=!state.video_options?.format_control||value.video_editing==='modify';
  segments.disabled=!state.video_options?.segment_controls||!!activeModel?.remote_media||value.video_editing==='modify';
  document.querySelector('#video-format-note').textContent=format.value?'Formato forzato: '+format.value+'. Prevale sulle proporzioni degli allegati e sul formato scritto nel prompt.':'Automatico segue il prompt e i fotogrammi guida. Scegli un formato per forzare tutta la generazione.';
  document.querySelector('#video-segments-note').textContent='Ogni segmento dura al massimo '+maxSegment+' secondi; la coda può essere più breve. Con una canzone viene conservata tutta la durata della traccia: segmenti più corti richiedono più generazioni.';
  const medium=read().video_quality==='medium';select.value=medium?'medium':'high';
  resolution.disabled=!state.video_options?.request_controls;
  const requestedMp=value.video_parameters?.megapixels;for(const option of [...resolution.querySelectorAll('[data-custom]')])option.remove();if(typeof requestedMp==='number'&&![.5,.7,.98].includes(requestedMp)){const option=document.createElement('option');option.value=String(requestedMp);option.textContent=requestedMp.toLocaleString('it-IT')+' MP · richiesta salvata';option.dataset.custom='';resolution.append(option);}resolution.value=requestedMp==null?'':String(requestedMp);
  const presetParameters={...value.video_parameters};delete presetParameters.megapixels;const presetMp=effectiveVideoResolution({...value,video_parameters:presetParameters},state);
  resolution.options[0].textContent=activeModel?.remote_media&&!medium?'Preset · dal server':'Preset · '+presetMp.toLocaleString('it-IT')+' MP';
  document.querySelector('#video-resolution-note').textContent='0,98 MP è la risoluzione nativa H3. Una risoluzione più alta richiede più tempo e memoria. Scegliendo 0,70 o 0,98 MP si attiva Alta; Media usa al massimo 0,50 MP. La scelta resta impostata per questa chat.';
  editing.value=['storyboard','modify'].includes(read().video_editing)?read().video_editing:'continuous';
  document.querySelector('#video-editing-summary').textContent=editing.value==='modify'?'Scrivi la modifica nel prompt e allega il video, oppure sceglilo dalla galleria dopo Invia. Nella finestra scegli le clip o i tratti; le immagini possono definire identità, vestiti, sfondi e oggetti. Il video originale guida i movimenti.':editing.value==='storyboard'?`Scrivi nel prompt il numero di clip, per esempio «9 clip»: deve bastare per coprire l’audio con segmenti di massimo ${maxSegment} secondi. Assistant raggruppa gli stacchi interni nei prompt. Senza un numero usa il minimo necessario. La canzone resta continua. Solo MiniMax standalone.`:'Ogni clip continua il fotogramma finale del precedente. Adatto a un movimento o un’azione senza stacchi.';
  const model=state.models.find(m=>m.id===(read().video_model||state.settings.video_model)),v={...state.video_options?.defaults,...state.settings.video_overrides?.[model?.id],...read().video_parameters};
  const requested=read().video_steps;for(const option of [...stepSelect.querySelectorAll('[data-custom]')])option.remove();if(Number.isInteger(requested)&&![12,16,20].includes(requested)){const option=document.createElement('option');option.value=requested;option.textContent=requested+' passi · personalizzati';option.dataset.custom='';stepSelect.append(option);}stepSelect.value=requested==null?'':String(requested);
  const mp=effectiveVideoResolution(value,state),steps=v.pdd_enabled?8:requested??(medium?Math.min(v.steps??12,8):v.steps??12);
  document.querySelector('#video-quality-summary').textContent=(model?.remote_media&&!medium?'Alta conserva i parametri del server.':`${medium?'Media':'Alta'} · circa ${mp.toLocaleString('it-IT')} MP · ${steps} passi.`)+' La scelta esplicita dei passi prevale sul profilo Media. Media riduce dettaglio e rifinitura per generare più rapidamente; mantiene durata e proporzioni. Il lip-sync usa almeno 8 passi. Questi profili valgono per MiniMax, non per Manim o infografiche HTML.';
 }};
}

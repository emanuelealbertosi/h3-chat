import {reloadEditDraft,lastLaunchDraft} from './video-edit-reload.js';
import {videoGuideFields} from './video-auto-guides.js';
import {uploadFile} from './file-upload.js';
import {videoModalOptions} from './video-modal-options.js';
import {escape as esc} from './render.js';
import {videoStepButtons,bindVideoSteps} from './video-steps.js';
import {openGallery} from './gallery.js';
import {videoTimeline} from './video-timeline.js';
import {videoTimelinePreview} from './video-timeline-preview.js';
import {mountClipTools} from './video-clip-tools.js';
import {addBrowserPreview} from './video-browser-preview.js';
import {draftSignature,remapEditorDraft,videoEditorDraft} from './video-editor-draft.js';
import {videoResplit} from './video-resplit.js';
import {videoConversionProgress} from './video-conversion-progress.js';
import {selectedSeedLabel} from './video-clip-versions.js';
import {mountEditMemory,memoryPatch,mountEditEndFrame,endFramePatch} from './video-edit-memory.js';

export const clipClock=value=>{const millis=Math.round(Math.max(0,Number(value)||0)*1000),seconds=Math.floor(millis/1000);return Math.floor(seconds/60)+':'+String(seconds%60).padStart(2,'0')+(millis%1000?'.'+String(millis%1000).padStart(3,'0'):'');};

export function chooseVideoForEdit({api,onSelect}){
 let segmentSeconds=Number(localStorage.getItem('h3.video-import.segment-seconds'))===10?10:15;
 const dialog=document.createElement('dialog');dialog.className='upscale-dialog';dialog.innerHTML=`<header><h2>Modifica video</h2><button type="button" class="icon-button" data-close aria-label="Chiudi">×</button></header><p>Scegli un video generato o carica un video esterno. Scegli intervalli da 10 o 15 secondi per un video esterno.</p><div class="upscale-choices"><button type="button" class="btn" data-gallery>Dalla galleria</button><button type="button" class="btn primary" data-upload>Carica dal PC</button></div><input type="file" hidden><p class="settings-error" role="alert" hidden></p>`;document.body.append(dialog);
 const q=s=>dialog.querySelector(s);dialog.onclose=()=>dialog.remove();q('[data-close]').onclick=()=>dialog.close();
 const sizes=document.createElement('div');sizes.className='video-edit-mode';sizes.setAttribute('role','group');sizes.setAttribute('aria-label','Durata dei segmenti importati');
 sizes.innerHTML=[10,15].map(n=>`<button type="button" class="btn small" data-import-seconds="${n}" aria-pressed="${n===segmentSeconds}">${n} secondi</button>`).join('');
 q('.upscale-choices').before(sizes);
 const note=document.createElement('p');note.className='small-note';note.textContent='10 secondi lasciano più margine per la risoluzione. 15 secondi producono meno clip. Puoi risuddividere il video anche dalla modale di modifica.';sizes.after(note);
 for(const b of sizes.querySelectorAll('button'))b.onclick=()=>{segmentSeconds=Number(b.dataset.importSeconds);localStorage.setItem('h3.video-import.segment-seconds',String(segmentSeconds));for(const button of sizes.querySelectorAll('button'))button.setAttribute('aria-pressed',String(Number(button.dataset.importSeconds)===segmentSeconds));};
 const selected=async media=>{dialog.close();await onSelect(media,{segmentSeconds});};
 q('[data-gallery]').onclick=()=>openGallery({api,kind:'video',multiple:false,onSelect:items=>selected(items[0])});q('[data-upload]').onclick=()=>q('input').click();
 q('input').onchange=async e=>{const error=q('[role="alert"]'),button=q('[data-upload]');try{const file=e.target.files[0];if(!file)return;button.disabled=true;button.textContent='Caricamento…';const media=await uploadFile(file,{api});await selected(media);}catch(e){error.textContent=e.message;error.hidden=false;}finally{button.disabled=false;button.textContent='Carica dal PC';e.target.value='';}};dialog.showModal();return dialog;
}

export async function openVideoEdit({api,chatId,source,busy,onQueued,pickFile,initialPrompt="",initialReferences=[],initialSteps=null,initialAssistant=true,initialLoras=[],segmentSeconds=null,initialParameters={},initialModel=null,initialPromptReferences=null,selectFirst=true,editorDraft=undefined,initialEdit=null}){
 let data;
 {
  const loading=document.createElement('dialog');loading.className='prompt-options-dialog';loading.innerHTML='<header><h2>Preparazione timeline</h2></header><p>Recupero clip e impostazioni salvate…</p>';document.body.append(loading);loading.showModal();
  const progress=videoConversionProgress(loading,{api,path:'/chats/'+chatId+'/video-import-progress/'+source+'?segment_seconds='+(segmentSeconds||15),label:'Lettura della timeline…'});
  try{data=await api('/chats/'+chatId+'/video-edit/'+source+(segmentSeconds===10||segmentSeconds===15?'?segment_seconds='+segmentSeconds:''));}
  finally{progress.stop();loading.close();loading.remove();}
 }
 const explicit=initialPrompt||initialReferences.length||initialSteps!=null||initialModel||Object.keys(initialParameters).length;
 let restored=initialEdit?reloadEditDraft(data,initialEdit,{model:initialModel||data.model_id,parameters:initialParameters,steps:initialSteps,assistant:initialAssistant,references:initialReferences}):editorDraft===undefined?(explicit?null:data.editor_draft||lastLaunchDraft(data)):editorDraft;
 if(restored){
  if(JSON.stringify(restored.state.signature)!==JSON.stringify(draftSignature(data.clips)))throw Error('La bozza appartiene a una suddivisione diversa del video.');
  initialModel=restored.state.model;initialParameters=restored.state.parameters;initialSteps=restored.state.values.video_steps===''?null:Number(restored.state.values.video_steps);initialAssistant=restored.state.values.assistant;
  initialPrompt='';initialReferences=restored.image_refs.filter(r=>!data.images.some(x=>x.id===r.id));initialLoras=[];
 }
 if(initialModel&&data.models?.some(m=>m.id===initialModel))data.model_id=initialModel;
 const clipLaunches={...data.last_launch?.clip_launches,...restored?.state.clip_launches};
 let launchDirty=!!explicit||!!restored&&!restored.last_launch,restoringLaunch=false;
 const versions=()=>Object.fromEntries(data.clips.filter(c=>c.selected_version).map(c=>[String(c.clip),c.selected_version]));
 const dialog=document.createElement('dialog');dialog.className='video-edit-dialog video-clip-dialog';dialog.ariaLabel='Modifica clip del video';
 dialog.innerHTML=`<header><div><span class="eyebrow">POST-PRODUZIONE</span><h2>Modifica clip</h2><p>Clicca un segmento per modificarlo. Le caselle selezionano i clip da generare; il dettaglio mostra una clip alla volta.</p></div><button type="button" class="icon-button" data-close aria-label="Chiudi">×</button></header><form><div class="video-dialog-body"><section class="video-timeline-section"><div class="video-timeline-heading"><strong>Segmenti del video</strong><button type="button" class="btn small" data-clear-clips>Deseleziona tutte</button></div><div data-timeline></div></section><p class="video-edit-empty" data-empty>Seleziona un segmento nella timeline per aprire anteprima, intervallo e modifica.</p><div class="video-edit-clips"></div><section class="video-edit-settings"><h3>Generazione degli spezzoni</h3><div class="video-edit-basics"><label class="field"><span>Risoluzione (MP)</span><input name="megapixels" type="number" min="0.2" max="2" step="0.01" placeholder="Formato originale"></label><div class="field" data-clip-steps><span>Passi</span>${videoStepButtons(null,{preset:true})}<input name="video_steps" aria-label="Passi personalizzati dei clip" type="number" min="1" max="50" step="1" placeholder="Preset del modello"></div></div><div class="video-edit-toolbar"><label class="check"><input type="checkbox" name="assistant" checked> Assistant On</label><label class="check"><input type="checkbox" name="remount" checked> Rimonta nel video</label></div><p class="small-note" data-remount-note></p><details class="video-edit-batch"><summary>Stessa modifica su più clip</summary><label class="field"><span>Modifica comune</span><textarea data-common-prompt maxlength="6000" rows="2" placeholder="Sostituisci la ragazza con Picture 1; conserva movimenti, camera e sfondo…"></textarea></label><button type="button" class="btn small" data-apply-all>Applica a tutte le clip</button></details><details class="video-edit-source"><summary>Dettaglio del video sorgente</summary><label class="field"><span>Risoluzione della guida (MP)</span><input name="reference_megapixels" type="number" min="0.1" max="0.98" step="0.01" value="0.35"></label><p class="small-note">Modifica video passa i fotogrammi del tratto a 24 fps. Una guida più dettagliata richiede più memoria e tempo; il formato di uscita si imposta separatamente.</p></details><div class="video-edit-toolbar"><button type="button" class="btn small" data-gallery>Riferimenti dalla galleria</button><button type="button" class="btn small" data-upload>Carica immagini</button><input type="file" multiple data-files hidden></div></section><p class="settings-error" data-error role="alert" hidden></p></div><footer><span data-summary>Seleziona almeno un clip</span><button class="btn primary" type="submit" disabled>Crea nuova versione</button></footer></form>`;
 if(data.imported)dialog.querySelector('header p').textContent='Video esterno · Modifica video usa la clip completa come guida. Puoi cambiare personaggi, vestiti, sfondo e oggetti. Audio, durata e proporzioni sono conservati; la fedeltà dei movimenti dipende dal modello.';
 document.body.append(dialog);const q=s=>dialog.querySelector(s),draft=new Map(),cards=new Map(),versionSelectors=new Map(),extra=[],clipTools=[];let active=null,timeline,timelinePreview,editorControls,busyTimer,submitting=false;
 q('[name="assistant"]').checked=initialAssistant;

 q('[data-common-prompt]').value=initialPrompt;
 const initialImageIds=new Set(initialReferences.map(x=>x.id));
 for(const image of initialReferences){if(!image.mime?.startsWith('image/'))continue;if(!data.images.some(x=>x.id===image.id)){extra.push(image);data.images.push({index:data.images.length+1,id:image.id,name:image.name,url:image.url||'/media/'+image.path});}}
 if(restored){restored={...restored,state:remapEditorDraft(restored.state,data.images)};for(const clip of data.clips){const variant=clip.versions?.find(v=>v.id===restored.state.versions[String(clip.clip)]);if(variant){Object.assign(clip,{selected_version:variant.id,url:variant.url,preview_start:variant.preview_start,source_interval:variant.source_interval,prompt:variant.prompt,edited:variant.id!==clip.versions[0].id});}}}
 initialPrompt=initialPrompt.replace(/<Picture\s+(\d+)>/gi,(tag,n)=>{const ref=(initialPromptReferences||initialReferences)[Number(n)-1],image=ref&&data.images.find(x=>x.id===ref.id);return image?'<Picture '+image.index+'>':tag;});q('[data-common-prompt]').value=initialPrompt;
 if(initialSteps!=null)q('[name="video_steps"]').value=String(initialSteps);
 if(initialParameters.megapixels!=null)q('[name="megapixels"]').value=String(initialParameters.megapixels);
 let disposed=false;const dispose=()=>{if(disposed)return;disposed=true;clearInterval(busyTimer);editorControls?.close();for(const tools of clipTools)tools.close();timelinePreview?.close();timeline?.close();for(const v of dialog.querySelectorAll('video'))v.pause();dialog.remove();};dialog.onclose=dispose;const closeDialog=()=>{dialog.close();dispose();};q('[data-close]').onclick=closeDialog;
 bindVideoSteps(q('[data-clip-steps]'),q('[name="video_steps"]'));
 const local=videoModalOptions(q('form'),data,{parameters:initialParameters,pickFile,initialLoras,onModel:preset=>{q('[name="megapixels"]').value=preset.megapixels??.7;q('[name="video_steps"]').value=preset.steps??12;q('[name="video_steps"]').dispatchEvent(new Event('input',{bubbles:true}));}});
 videoResplit(q('.video-timeline-heading'),{data,source,api,chatId,isSubmitting:()=>submitting,setPending:value=>{submitting=value;if(!disposed)summary();},onError:message=>{error(message);summary();},resplit:async(origin,seconds)=>{
  const selection=local.read(),parameters={...selection.parameters,...(q('[name="megapixels"]').value!==''?{megapixels:Number(q('[name="megapixels"]').value)}:{})};
  if(data.draft_supported)await api('/chats/'+chatId+'/video-editor-draft/'+origin,{segment_seconds:seconds},'DELETE');
  await openVideoEdit({api,chatId,source:origin,busy,onQueued,pickFile,initialSteps:q('[name="video_steps"]').value===''?null:Number(q('[name="video_steps"]').value),initialAssistant:q('[name="assistant"]').checked,initialParameters:parameters,initialModel:selection.model,segmentSeconds:seconds,selectFirst:false,editorDraft:null});
  closeDialog();
 }});
 q('.video-edit-settings').insertBefore(q('.video-modal-options'),q('.video-edit-basics'));
 // Timeline first, then all controls, then the selected clip editor.
 const settingsPanel=q('.video-edit-settings'),body=q('.video-dialog-body');
 const assets=document.createElement('section');assets.className='video-edit-assets';
 assets.append(q('.video-edit-batch'),q('[data-gallery]').parentElement);q('.video-edit-clips').after(assets);
 q('.video-timeline-section').after(settingsPanel);q('.video-edit-source').open=true;
 const guideInput=q('[name="reference_megapixels"]');
 let savedGuide;try{savedGuide=Number(localStorage.getItem('h3-video-edit-guide-mp'));}catch{}
 if(savedGuide>=.1&&savedGuide<=.98)guideInput.value=String(savedGuide);
 const guideButtons=document.createElement('div');guideButtons.className='video-step-buttons';guideButtons.setAttribute('role','group');guideButtons.ariaLabel='Dettaglio sorgente video';
 for(const [value,label] of [[.15,'0,15 · leggero'],[.20,'0,20 · rapido'],[.35,'0,35 · bilanciato'],[.5,'0,50 · dettagliato']]){
  const button=document.createElement('button');button.type='button';button.className='btn small';button.textContent=label;button.dataset.guide=String(value);
  button.onclick=()=>{guideInput.value=String(value);guideInput.dispatchEvent(new Event('input',{bubbles:true}));};guideButtons.append(button);
 }
 guideInput.parentElement.before(guideButtons);
 const customGuide=document.createElement('details');customGuide.innerHTML='<summary>Valore personalizzato</summary>';guideInput.parentElement.before(customGuide);customGuide.append(guideInput.parentElement);
 const syncGuide=()=>{for(const button of guideButtons.children)button.setAttribute('aria-pressed',String(Number(button.dataset.guide)===Number(guideInput.value)));if(guideInput.value!==''&&Number(guideInput.value)>=.1&&Number(guideInput.value)<=.98)try{localStorage.setItem('h3-video-edit-guide-mp',guideInput.value);}catch{}};
 guideInput.addEventListener('input',syncGuide);syncGuide();
 const loadNote=document.createElement('p');loadNote.className='small-note';loadNote.dataset.memoryBudget='';q('.video-edit-source').after(loadNote);
 const updateBudget=()=>{const mp=Number(q('[name="megapixels"]').value)||data.parameters?.megapixels||.98,guide=Number(guideInput.value),aligned=q('form').dataset.sourceConditioning==='aligned';const duration=Math.max(0,...data.clips.map(c=>c.end-c.start));loadNote.textContent=`Uscita ${mp.toFixed(2)} MP · guida ${aligned?'stessa griglia':guide.toFixed(2)+' MP'} · fino a ${duration.toFixed(1)} s per clip. `+(duration>10&&mp>=.7?'Carico elevato: 56 gruppi riducono solo lo spazio dell’attenzione, non quello di tutte le attivazioni. Per una prova più leggera usa 10 s oppure, in modalità riferimento, una guida da 0,20–0,35 MP. ':'');};
 const sourceDetail=()=>{q('details.video-edit-source').hidden=q('form').dataset.sourceConditioning==='aligned';updateBudget();};q('form').addEventListener('input',updateBudget);q('form').addEventListener('source-conditioning',sourceDetail);sourceDetail();
 const resolution=q('[name="megapixels"]'),sizes=document.createElement('div');sizes.className='video-step-buttons';sizes.setAttribute('role','group');sizes.ariaLabel='Risoluzione di uscita';
 for(const [value,label] of [['','Originale'],[.5,'0,50 MP'],[.7,'0,70 MP'],[.98,'0,98 MP']]){const button=document.createElement('button');button.type='button';button.className='btn small';button.textContent=label;button.dataset.mp=String(value);button.onclick=()=>{resolution.value=String(value);resolution.dispatchEvent(new Event('input',{bubbles:true}));};sizes.append(button);}
 resolution.before(sizes);const syncSize=()=>{for(const button of sizes.children)button.setAttribute('aria-pressed',String(button.dataset.mp===resolution.value));};resolution.addEventListener('input',syncSize);syncSize();
 if(data.working_timeline||data.clips.some(c=>c.versions?.length>1)){
  q('header p').textContent='Timeline salvata · le anteprime includono le modifiche precedenti. Modifica altri tratti o monta tutte le clip già pronte.';
  const assemble=document.createElement('button');assemble.type='button';assemble.className='btn';assemble.textContent='Monta video completo';assemble.dataset.assemble='';q('footer').insertBefore(assemble,q('[type="submit"]'));
  assemble.title='Monta tutte le '+data.clips.length+' clip nelle versioni scelte, indipendentemente dalle caselle di rigenerazione.';
  const assemblyNote=document.createElement('p');assemblyNote.className='small-note';assemblyNote.dataset.assemblySummary='';q('.video-timeline-section').append(assemblyNote);
  assemble.onclick=async()=>{submitting=true;assemble.disabled=true;error('');try{if(busy?.())throw Error('Attendi o interrompi la tua richiesta in corso.');const result=await api('/chats/'+chatId+'/video-assemble',{source,versions:versions()});closeDialog();await onQueued?.(result);}catch(e){error(e.message);}finally{submitting=false;if(!disposed)summary();}};
 }
 const error=text=>{const box=q('[data-error]');box.textContent=text;box.hidden=!text;if(text){box.tabIndex=-1;box.scrollIntoView({block:'nearest'});box.focus({preventScroll:true});}};
 // Browser constraint validation runs before onsubmit, including hidden fields.
 // Keep its errors visible inside the dialog instead of silently blocking launch.
 q('form').addEventListener('invalid',event=>{
  event.preventDefault();const input=event.target,card=input.closest('.video-edit-clip');
  const label=input.getAttribute('aria-label')||input.closest('label')?.querySelector('span')?.textContent||input.name||'valore';
  error((card?'Clip '+card.id.match(/\d+$/)[0]+' · ':'')+'Controlla '+label+': '+input.validationMessage);
 },true);
 const selectAll=document.createElement('button');selectAll.type='button';selectAll.className='btn small';selectAll.dataset.selectAllClips='';selectAll.textContent='Seleziona tutti';q('.video-timeline-heading').insertBefore(selectAll,q('[data-clear-clips]'));
 const shortNote=document.createElement('p');shortNote.className='small-note';shortNote.hidden=!data.clips.some(c=>Math.round((c.end-c.start)*24)<24);shortNote.textContent='Questa timeline salvata contiene una coda inferiore a un secondo: viene conservata nel montaggio, senza rigenerarla. Le nuove importazioni distribuiscono la coda tra gli ultimi due segmenti.';q('.video-timeline-heading').after(shortNote);
 const batchRefs=document.createElement('label');batchRefs.className='check';batchRefs.innerHTML='<input type="checkbox" data-common-references checked> Stessi riferimenti e modalità della clip aperta';q('[data-apply-all]').before(batchRefs);
 const allAudio=document.createElement('section');allAudio.className='video-edit-source';allAudio.innerHTML='<label class="check"><input type="checkbox" data-lipsync-all> Lip-sync con l’audio del video su tutte le clip</label><p class="small-note">Usa automaticamente il tratto audio originale corrispondente a ogni clip, senza caricare una traccia esterna. Attiva anche la guida audio per MiniMax.</p>';
 q('[data-remount-note]').after(allAudio);
 const allLipsync=q('[data-lipsync-all]');
 function syncAllLipsync(){const clips=[...draft.values()],count=clips.filter(x=>x.lip_sync&&x.audio_guide).length;allLipsync.checked=!!clips.length&&count===clips.length;allLipsync.indeterminate=count>0&&count<clips.length;}
 function setClipAudio(item,card,lip,audio){item.lip_sync=lip;item.audio_guide=audio;card.querySelector('[data-lipsync]').checked=lip;card.querySelector('[data-audio-guide]').checked=audio;}
 allLipsync.onchange=()=>{for(const [number,card] of cards){const item=draft.get(number);setClipAudio(item,card,allLipsync.checked,allLipsync.checked||!!item.audio_guide);}syncAllLipsync();};
 const waiting=document.createElement('p');waiting.className='small-note';waiting.dataset.editorBusy='';settingsPanel.querySelector('h3').after(waiting);
 const dirtyLaunch=()=>{if(!restoringLaunch)launchDirty=true;};settingsPanel.addEventListener('input',dirtyLaunch);settingsPanel.addEventListener('change',dirtyLaunch);
 function restoreClipLaunch(number){
  const saved=clipLaunches[String(number)];if(!saved)return;
  restoringLaunch=true;
  try{
   q('[name="megapixels"]').value=saved.parameters.megapixels??'';local.set(saved);
   q('[name="video_steps"]').value=saved.steps??'';q('[name="assistant"]').checked=saved.assistant;
   if(saved.reference_megapixels!=null)guideInput.value=saved.reference_megapixels;
   for(const input of [q('[name="megapixels"]'),q('[name="video_steps"]'),guideInput])input.dispatchEvent(new Event('input',{bubbles:true}));
   launchDirty=false;error('');
  }catch(e){error(e.message);}finally{restoringLaunch=false;}
 }
 if(restored?.last_launch){const note=document.createElement('p');note.className='small-note';note.dataset.lastLaunch='';note.textContent='Ultime impostazioni di lancio recuperate · '+new Date(restored.saved_at*1000).toLocaleString('it-IT')+'. Le versioni già completate restano selezionate nella timeline. Per proseguire la stessa richiesta interrotta usa Riprendi clip mancanti nella chat.';settingsPanel.querySelector('h3').after(note);}
 const summary=()=>{const working=!!busy?.(),remount=q('[name="remount"]').checked;q('[data-remount-note]').textContent=remount?'Il risultato sarà il video completo aggiornato, con l’audio originale.':'Salva la timeline aggiornata e gli spezzoni separati con audio originale. Potrai continuare le modifiche e montare il video completo alla fine.';waiting.hidden=!working;waiting.textContent='La tua richiesta è ancora in corso. Puoi preparare e salvare la bozza; il lancio si abiliterà quando termina.';q('[type="submit"]').textContent=remount?'Crea nuova versione':'Genera spezzoni';const selected=[...draft.values()].filter(x=>x.enabled),count=selected.length,seconds=selected.reduce((sum,x)=>sum+(x.range?x.last-x.first:x.frames)/24,0);q('[data-summary]').textContent=count?count+' clip da modificare · '+clipClock(seconds)+' da generare'+(remount?' · '+(data.clips.length-count)+' clip riutilizzati':' · file separati'):'Seleziona almeno un clip';const variants=Number(q('[name="variants"]')?.value)||1;if(count&&variants>1)q('[data-summary]').textContent+=' · '+variants+' varianti/clip ('+(count*variants)+' generazioni)';q('[type="submit"]').disabled=!count||working||submitting;if(q('[data-assemble]')){q('[data-assemble]').disabled=working||submitting;const edited=data.clips.filter(c=>c.edited).length;q('[data-assembly-summary]').textContent='Monta video completo: tutte le '+data.clips.length+' clip · '+edited+' versioni modificate e '+(data.clips.length-edited)+' versioni originali. Le caselle selezionano soltanto le clip da rigenerare.';}for(const b of dialog.querySelectorAll('[data-segment-seconds]'))b.disabled=!!count;timeline?.update(new Set(selected.map(x=>x.clip)),active);};
 q('[name="remount"]').onchange=summary;q('[name="variants"]')?.addEventListener('input',summary);
 function focusClip(number,{enable=true}={}){
  if(data.launch_settings&&!launchDirty&&clipLaunches[String(number)])restoreClipLaunch(number);
  if(enable&&draft.get(number)?.frames>=24)draft.get(number).enabled=true;active=number;
  timelinePreview?.focusChanged();
  for(const [n,card] of cards){const show=n===number;card.hidden=!show;card.querySelector('[data-fields]').hidden=!show;const video=card.querySelector('video');
   if(show&&!video.getAttribute('src')){video.src=video.dataset.previewSrc;video.preload='metadata';video.load();}
   else if(!show&&video.getAttribute('src')){video.pause();video.removeAttribute('src');video.load();}
  }
  q('[data-empty]').hidden=number!==null;summary();
 }

 function references(card,item){
  const host=card.querySelector('[data-references]');host.replaceChildren();
  for(const image of data.images){const button=document.createElement('button');button.type='button';button.className='video-edit-reference';button.setAttribute('aria-pressed',String(item.mode==='i2v'?item.start_image===image.index:item.images.has(image.index)));button.innerHTML=`<img src="${esc(image.url)}" alt="" loading="lazy"><span>Picture ${image.index} · ${esc(image.name)}</span>`;
   button.onclick=()=>{if(item.mode==='i2v'){item.start_image=image.index;references(card,item);}else{if(item.images.has(image.index))item.images.delete(image.index);else{if(item.images.size>=9){error('Scegli fino a nove riferimenti per clip.');return;}item.images.add(image.index);}button.setAttribute('aria-pressed',String(item.images.has(image.index)));}error('');};host.append(button);
  }
 }
 for(const clip of data.clips){
  const frames=Math.round((clip.end-clip.start)*24),savedClip=restored?.state.clips.find(c=>c.clip===clip.clip),item={enabled:false,clip:clip.clip,prompt:initialPrompt,images:new Set(data.images.filter(x=>initialImageIds.has(x.id)).map(x=>x.index)),lip_sync:clip.lip_sync,audio_guide:!!clip.lip_sync,range:false,first:0,last:frames,frames,mode:'video',anchors:'none',anchor_image:null,start_image:clip.start_image||null,...(data.memory_recovery?{recover_memory:!!clip.memory?.default}:{}),...(data.end_frame_recovery?{end_frame:'none'}:{}),...savedClip};item.images=new Set(savedClip?.images||item.images);if(frames<24)item.enabled=false;draft.set(clip.clip,item);
  const card=document.createElement('article');card.className='video-edit-clip';card.id='video-clip-editor-'+clip.clip;card.hidden=true;cards.set(clip.clip,card);card.innerHTML=`<div class="video-edit-clip-head"><strong>Clip ${clip.clip} · ${clipClock(clip.start)}–${clipClock(clip.end)}</strong><video controls playsinline preload="none" src="${esc(clip.url)}" aria-label="Anteprima clip ${clip.clip}"></video></div><div data-fields hidden><div class="video-edit-mode" role="group" aria-label="Parte da modificare"><button type="button" class="btn small" data-whole aria-pressed="true">Intera clip</button><button type="button" class="btn small" data-part aria-pressed="false" ${frames<24?'disabled':''}>Solo un tratto</button></div><div class="video-edit-range" data-range hidden><div class="video-edit-track"><span data-track></span><input type="range" min="0" max="${frames}" step="1" value="0" data-first aria-label="Inizio del tratto, in fotogrammi"><input type="range" min="0" max="${frames}" step="1" value="${frames}" data-last aria-label="Fine del tratto, in fotogrammi"></div><div class="video-edit-times"><label>Da <input type="number" min="0" max="${frames/24}" step="any" value="0" data-start aria-label="Inizio del tratto in secondi"> s</label><label>A <input type="number" min="0" max="${frames/24}" step="any" value="${frames/24}" data-end aria-label="Fine del tratto in secondi"> s</label><button type="button" class="btn small" data-preview>Riproduci tratto</button></div><p data-range-info></p><p class="muted">Minimo 1 secondo. I tempi sono relativi a questa clip; il resto e la musica restano invariati. Il raccordo visivo può cambiare.</p></div><label class="field"><span>Cosa vuoi cambiare in questo clip?</span><textarea maxlength="6000" rows="3" placeholder="Ad esempio: primo piano del cantante, bocca sempre visibile, movimento lento della camera…" data-prompt></textarea></label><label class="check"><input type="checkbox" data-audio-guide ${item.audio_guide?'checked':''}> Usa l’audio originale come guida per MiniMax</label><p class="small-note">Disattivo: MiniMax lavora sul video senza ricevere l’audio. La traccia originale viene conservata nel montaggio.</p><label class="check"><input type="checkbox" data-lipsync ${item.lip_sync?'checked':''}> Lip-sync sulle voci originali</label><div class="video-edit-mode" role="group" aria-label="Sorgente del clip"><button type="button" class="btn small" data-video-mode>Modifica video</button><button type="button" class="btn small" data-reference-mode>Rigenera · riferimenti</button><button type="button" class="btn small" data-i2v-mode>I2V · immagine iniziale</button></div><p class="muted" data-image-mode-info></p><div class="video-edit-toolbar"><button type="button" class="btn small" data-clip-gallery>Scegli dalla galleria</button><button type="button" class="btn small" data-clip-upload>Carica immagine per questo clip</button><input type="file" data-clip-file hidden></div><details><summary data-image-summary>Riferimenti del clip · fino a 9 immagini</summary><div class="video-edit-references" data-references></div></details><details><summary>Regia precedente</summary><pre>${esc(clip.prompt)}</pre></details></div>`;
  q('.video-edit-clips').append(card);card.querySelector('[data-prompt]').value=initialPrompt;references(card,item);
  const usedSeed=document.createElement('p');usedSeed.className='small-note';usedSeed.dataset.usedSeed='';usedSeed.textContent=selectedSeedLabel(clip);card.querySelector('.video-edit-clip-head strong').after(usedSeed);
  const preview=card.querySelector('video');preview.dataset.previewSrc=clip.url;preview.removeAttribute('src');
  addBrowserPreview(card,preview,{id:source,path:clip.url},api);
  const previewControls=document.createElement('div');previewControls.className='video-clip-preview-controls';
  previewControls.append(card.querySelector('[data-fields]>.video-edit-mode'),card.querySelector('[data-range]'));
  card.querySelector('.video-edit-clip-head').append(previewControls);
  if(data.launch_settings){
   const controls=document.createElement('div');controls.className='video-clip-launch';
   controls.innerHTML='<button type="button" class="btn small" data-restore-clip-launch>Ripristina parametri dell’ultimo lancio di questa clip</button>';
   const button=controls.querySelector('button');button.disabled=!clipLaunches[String(clip.clip)];button.onclick=()=>restoreClipLaunch(clip.clip);card.refreshLaunch=()=>{button.disabled=!clipLaunches[String(clip.clip)];};
   card.querySelector('.video-edit-clip-head').append(controls);
  }
  if(data.clip_tools)clipTools.push(mountClipTools(previewControls,{api,chatId,source,clip,segmentSeconds:data.segment_seconds,data,pickFile,
   getRange:()=>item.range?[item.first/24,item.last/24]:null,getVersions:versions,busy:()=>submitting||busy?.(),
   onQueued:async result=>{closeDialog();await onQueued?.(result);}}));
  const refreshMemory=mountEditMemory(card,item,clip,!!data.memory_recovery),refreshEndFrame=mountEditEndFrame(card,item,clip,data);
  card.refreshMemory=()=>{refreshMemory();refreshEndFrame();};
  item.anchor_images=item.anchor_images||{};
  const anchors=document.createElement('section');anchors.className='video-edit-anchor-options';anchors.innerHTML='<label class="check"><input type="checkbox" data-anchor-first> Fotogrammi guida</label><div data-anchor-detail hidden><div class="video-edit-mode"><button type="button" class="btn small" data-anchor-mode="first" aria-pressed="true">Inizio</button><button type="button" class="btn small" data-anchor-mode="ends" aria-pressed="false">Inizio e fine</button><button type="button" class="btn small" data-anchor-mode="three" aria-pressed="false">Inizio · metà · fine</button></div><div class="video-edit-anchor-grid">'+[['first','iniziale'],['middle','a metà'],['last','finale']].map(([key,label])=>`<label class="field" data-anchor-field="${key}" ${key==='first'?'':'hidden'}><span>Fotogramma ${label}</span><select data-anchor-picture="${key}" aria-label="Fotogramma ${label} del clip"></select></label>`).join('')+'</div><p class="small-note">Scegli fotogrammi già modificati per mantenere lo stesso abito. L’originale conserva anche l’abito originale. Per raccordare due segmenti scegli la stessa immagine come finale del primo e inizio del successivo. I fotogrammi guidano il modello; non bloccano ogni movimento intermedio.</p></div>';
  card.querySelector('[data-image-mode-info]').before(anchors);
  item.auto_anchors=!!item.auto_anchors;item.anchor_edit_model=item.anchor_edit_model??data.anchor_edit_model??'';
  const automatic=document.createElement('div');automatic.className='video-edit-auto-guides';
  automatic.innerHTML='<label class="check"><input type="checkbox" data-auto-anchors> Modifica automaticamente i fotogrammi guida</label><div data-auto-guide-settings hidden><label class="field"><span>Modello per modificare le immagini</span><select data-guide-editor aria-label="Modello immagini per le guide"></select></label><p class="small-note">Estrae i fotogrammi del tratto selezionato e applica il prompt della clip alle immagini prima di generare il video. Prepara tutte le guide in un batch e le salva in galleria. Aggiunge il tempo di modifica delle immagini; la fedeltà dei movimenti dipende comunque dal modello video.</p></div>';
  anchors.querySelector('[data-anchor-detail]').prepend(automatic);
  const editor=automatic.querySelector('[data-guide-editor]');
  for(const model of data.anchor_edit_models||[]){const option=document.createElement('option');option.value=model.id;option.textContent=model.name;editor.append(option);}
  if([...editor.options].some(x=>x.value===item.anchor_edit_model))editor.value=item.anchor_edit_model;
  else item.anchor_edit_model=editor.value;
  editor.onchange=()=>{item.anchor_edit_model=editor.value;};
  if(!editor.options.length){automatic.querySelector('[data-auto-anchors]').disabled=true;automatic.title=data.anchor_edit_models===undefined?'Riavvia H3-Chat dopo i lavori in corso per attivare questa funzione.':'Configura prima un modello di modifica immagini nelle impostazioni.';}
  const refreshAnchors=()=>{for(const select of anchors.querySelectorAll('[data-anchor-picture]')){select.innerHTML='<option value="">Originale del tratto selezionato</option>'+data.images.map(x=>`<option value="${x.index}">Picture ${x.index} · ${esc(x.name)}</option>`).join('');select.value=item.anchor_images[select.dataset.anchorPicture]||'';}};refreshAnchors();card.refreshAnchors=refreshAnchors;
  const previewAnchor=select=>{const image=data.images.find(x=>x.index===item.anchor_images[select.dataset.anchorPicture]);let preview=select.parentElement.querySelector('img');if(!preview){preview=document.createElement('img');preview.className='video-edit-anchor-preview';preview.alt='Anteprima del fotogramma guida';select.after(preview);}preview.hidden=!image;if(image)preview.src=image.url;else preview.removeAttribute('src');};
  let anchorMode=item.anchors==='none'?'first':item.anchors;anchors.querySelector('[data-anchor-first]').checked=item.anchors!=='none';automatic.querySelector('[data-auto-anchors]').checked=item.auto_anchors;
  const anchorTimes=()=>{const first=item.range?item.first:0,last=item.range?item.last:frames;for(const [key,label,frame] of [['first','iniziale',first],['middle','a metà',first+Math.floor((last-first)/2)],['last','finale',last-1]])anchors.querySelector(`[data-anchor-field="${key}"]>span`).textContent=`Fotogramma ${label} · ${clipClock(frame/24)} nella clip`;};
  const syncAnchors=()=>{const first=anchors.querySelector('[data-anchor-first]').checked;item.anchors=first?anchorMode:'none';anchors.querySelector('[data-anchor-detail]').hidden=!first;if(!first){item.auto_anchors=false;automatic.querySelector('[data-auto-anchors]').checked=false;}automatic.querySelector('[data-auto-guide-settings]').hidden=!item.auto_anchors;anchors.querySelector('.video-edit-anchor-grid').hidden=item.auto_anchors;anchors.querySelector('[data-anchor-detail]>.small-note').hidden=item.auto_anchors;for(const field of anchors.querySelectorAll('[data-anchor-field]'))field.hidden=field.dataset.anchorField==='middle'?anchorMode!=='three':field.dataset.anchorField==='last'?anchorMode==='first':false;for(const button of anchors.querySelectorAll('[data-anchor-mode]'))button.setAttribute('aria-pressed',String(button.dataset.anchorMode===anchorMode));anchorTimes();};
  automatic.querySelector('[data-auto-anchors]').onchange=e=>{item.auto_anchors=e.target.checked;if(item.auto_anchors)anchorMode='three';syncAnchors();};
  anchors.querySelector('[data-anchor-first]').onchange=syncAnchors;for(const button of anchors.querySelectorAll('[data-anchor-mode]'))button.onclick=()=>{anchorMode=button.dataset.anchorMode;syncAnchors();};for(const select of anchors.querySelectorAll('[data-anchor-picture]'))select.onchange=e=>{const key=select.dataset.anchorPicture;if(e.target.value==='')delete item.anchor_images[key];else item.anchor_images[key]=Number(e.target.value);previewAnchor(select);};
  syncAnchors();for(const select of anchors.querySelectorAll('[data-anchor-picture]'))if(select.value)previewAnchor(select);
  const imageMode=value=>{item.mode=value;card.refreshMemory?.();anchors.hidden=value!=='video';card.querySelector('[data-video-mode]').setAttribute('aria-pressed',String(value==='video'));card.querySelector('[data-reference-mode]').setAttribute('aria-pressed',String(value==='reference'));card.querySelector('[data-i2v-mode]').setAttribute('aria-pressed',String(value==='i2v'));card.querySelector('[data-image-summary]').textContent=value==='i2v'?'Scegli una sola immagine iniziale':value==='video'?'Immagini opzionali · identità, outfit, sfondo o oggetti':'Riferimenti del clip · fino a 9 immagini';card.querySelector('[data-image-mode-info]').textContent=value==='i2v'?'Il primo fotogramma del tratto partirà da questa immagine. Audio e formato del filmato restano invariati; l’immagine viene adattata senza deformarla.':value==='video'?'Il modello riceve la clip completa come <Video 1>. Il prompt modifica solo gli attributi richiesti; il video guida azioni, camera e tempi. Immagini facoltative.':'Rigenera una nuova scena dalle immagini: il video originale non guida i movimenti.';references(card,item);};
  card.querySelector('[data-video-mode]').onclick=()=>imageMode('video');card.querySelector('[data-reference-mode]').onclick=()=>imageMode('reference');card.querySelector('[data-i2v-mode]').onclick=()=>imageMode('i2v');imageMode(item.mode);
  card.setImageMode=imageMode;
  const attachHere=images=>{addImages(images);if(images.length){const selected=data.images.find(x=>x.id===images[0].id);if(item.mode==='i2v')item.start_image=selected.index;else if(item.images.size<9)item.images.add(selected.index);references(card,item);}};
  card.querySelector('[data-clip-gallery]').onclick=()=>openGallery({api,kind:'image',multiple:false,onSelect:async images=>{attachHere(images);error('');}});
  card.querySelector('[data-clip-upload]').onclick=()=>card.querySelector('[data-clip-file]').click();
  card.querySelector('[data-clip-file]').onchange=async e=>{try{const file=e.target.files[0];if(file)attachHere([await uploadImage(file)]);error('');}catch(e){error(e.message);}finally{e.target.value='';}};
  if(!data.partial_edit)card.querySelector('[data-part]').hidden=true;

  card.querySelector('[data-prompt]').oninput=e=>{item.prompt=e.target.value;};card.querySelector('[data-lipsync]').onchange=e=>{setClipAudio(item,card,e.target.checked,e.target.checked||!!item.audio_guide);syncAllLipsync();};card.querySelector('[data-audio-guide]').checked=item.audio_guide??true;card.querySelector('[data-audio-guide]').onchange=e=>{setClipAudio(item,card,e.target.checked&&item.lip_sync,e.target.checked);syncAllLipsync();};
  const c=s=>card.querySelector(s),video=c('video');let previewOffset=clip.preview_start||0,previewing=false;
  if(clip.versions?.length){
   versionSelectors.set(clip.clip,id=>{const variant=clip.versions.find(v=>v.id===id);if(!variant)return;
    video.pause();previewing=false;clip.selected_version=variant.id;clip.url=variant.url;clip.preview_start=variant.preview_start;clip.source_interval=variant.source_interval;
    clip.prompt=variant.prompt;clip.edited=variant.id!==clip.versions[0].id;previewOffset=variant.preview_start||0;video.dataset.previewSrc=variant.url;video.src=variant.url;video.load();
    card.querySelector('pre').textContent=variant.prompt;usedSeed.textContent=selectedSeedLabel(clip);timeline?.refresh(clip.clip);timelinePreview?.refresh(clip.clip);summary();
   });
  }
  video.addEventListener('loadedmetadata',()=>{video.currentTime=previewOffset+(item.range?item.first/24:0);});
  const syncRange=()=>{card.refreshMemory?.();c('[data-first]').value=item.first;c('[data-last]').value=item.last;c('[data-start]').value=item.first/24;c('[data-end]').value=item.last/24;c('[data-track]').style.left=item.first/frames*100+'%';c('[data-track]').style.width=(item.last-item.first)/frames*100+'%';c('[data-range-info]').textContent='Rigenera '+clipClock((item.last-item.first)/24)+' · nel film '+clipClock(clip.start+item.first/24)+'–'+clipClock(clip.start+item.last/24);anchorTimes();summary();};
  const mode=partial=>{item.range=partial;c('[data-range]').hidden=!partial;for(const input of c('[data-range]').querySelectorAll('input'))input.disabled=!partial;c('[data-whole]').setAttribute('aria-pressed',String(!partial));c('[data-part]').setAttribute('aria-pressed',String(partial));previewing=false;video.pause();syncRange();timelinePreview?.focusChanged();};
  c('[data-whole]').onclick=()=>mode(false);c('[data-part]').onclick=()=>mode(true);
  const change=(edge,frame)=>{if(!Number.isFinite(frame)){syncRange();return;}if(edge==='first')item.first=Math.max(0,Math.min(item.last-24,Math.round(frame)));else item.last=Math.min(frames,Math.max(item.first+24,Math.round(frame)));previewing=false;video.pause();syncRange();timelinePreview?.focusChanged();if(video.readyState)video.currentTime=previewOffset+(edge==='first'?item.first:Math.max(item.first,item.last-1))/24;};
  c('[data-first]').oninput=e=>change('first',Number(e.target.value));c('[data-last]').oninput=e=>change('last',Number(e.target.value));
  c('[data-start]').onchange=e=>change('first',e.target.value===''?NaN:Number(e.target.value)*24);c('[data-end]').onchange=e=>change('last',e.target.value===''?NaN:Number(e.target.value)*24);
  c('[data-preview]').onclick=async()=>{try{video.currentTime=previewOffset+item.first/24;previewing=true;await video.play();}catch{previewing=false;error('Anteprima non disponibile. Puoi comunque scegliere i tempi del tratto.');}};
  video.addEventListener('play',()=>{if((clip.source_interval||data.imported)&&(video.currentTime<previewOffset||video.currentTime>=previewOffset+frames/24))video.currentTime=previewOffset;});
  video.addEventListener('timeupdate',()=>{const stop=previewing?previewOffset+item.last/24:(clip.source_interval||data.imported)?previewOffset+frames/24:Infinity;if(video.currentTime>=stop){previewing=false;video.pause();}});
  mode(item.range);c('[data-prompt]').value=item.prompt;c('[data-lipsync]').checked=item.lip_sync;
 }
 timeline=videoTimeline(q('[data-timeline]'),data.clips,{onVersion:(number,id)=>versionSelectors.get(number)?.(id),onFocus:number=>focusClip(number),onToggle:(number,enabled)=>{draft.get(number).enabled=enabled;if(enabled)focusClip(number);else if(active===number)focusClip([...draft.values()].find(x=>x.enabled)?.clip??null,{enable:false});else summary();}});
 const navigation=document.createElement('div');navigation.className='video-timeline-navigation';navigation.innerHTML=`<span>${data.clips.length} clip · ${clipClock(data.duration??data.clips.at(-1)?.end)}</span><button type="button" class="btn small" aria-label="Segmenti precedenti">‹</button><button type="button" class="btn small" aria-label="Segmenti successivi">›</button>`;
 q('.video-timeline-heading').insertBefore(navigation,q('[data-clear-clips]'));
 navigation.querySelectorAll('button').forEach((button,index)=>{button.onclick=()=>q('[data-timeline]').scrollBy({left:(index?1:-1)*q('[data-timeline]').clientWidth*.75,behavior:'smooth'});});
 timelinePreview=videoTimelinePreview(q('.video-timeline-section'),{clips:data.clips,audio:data.preview_audio,getFocusRange:()=>{const clip=data.clips.find(c=>c.clip===active),item=draft.get(active);return clip&&item?[clip.start+(item.range?item.first/24:0),item.range?clip.start+item.last/24:clip.end]:null;},onStart:()=>{timeline?.pausePreviews();for(const card of cards.values())card.querySelector('video').pause();}});
 selectAll.onclick=()=>{for(const item of draft.values())item.enabled=item.frames>=24;focusClip(active??[...draft.values()].find(x=>x.enabled)?.clip??null,{enable:false});error('');};
 q('[data-apply-all]').onclick=()=>{const prompt=q('[data-common-prompt]').value.trim();if(!prompt){error('Scrivi la modifica comune prima di applicarla a tutte le clip.');return;}const base=draft.get(active),share=q('[data-common-references]').checked&&base&&(base.mode==='i2v'?base.start_image:base.images.size);for(const [number,card] of cards){const item=draft.get(number);item.prompt=prompt;item.enabled=item.frames>=24;card.querySelector('[data-prompt]').value=prompt;if(base)setClipAudio(item,card,base.lip_sync,!!base.audio_guide);if(share){item.images=new Set(base.images);item.start_image=base.start_image;card.setImageMode(base.mode);}}syncAllLipsync();focusClip(active??[...draft.values()].find(x=>x.enabled)?.clip??null,{enable:false});error('');};
 q('[data-clear-clips]').onclick=()=>{for(const item of draft.values())item.enabled=false;focusClip(null,{enable:false});};
 function addImages(items){for(const image of items){if(!image.mime?.startsWith('image/'))throw Error('Scegli immagini come nuovi riferimenti.');if(data.images.some(x=>x.id===image.id))continue;if(extra.length>=9)throw Error('Puoi aggiungere fino a nove nuove immagini.');extra.push(image);data.images.push({index:data.images.length+1,id:image.id,name:image.name,url:image.url||'/media/'+image.path});}for(const card of q('.video-edit-clips').children){const number=Number(card.querySelector('video').getAttribute('aria-label').match(/\d+$/)[0]);references(card,draft.get(number));card.refreshAnchors?.();card.refreshMemory?.();}}
 async function uploadImage(file){return uploadFile(file,{api});}
 q('[data-gallery]').onclick=()=>openGallery({api,kind:'image',onSelect:async items=>{try{addImages(items);error('');}catch(e){error(e.message);throw e;}}});
 q('[data-upload]').onclick=()=>q('[data-files]').click();
 q('[data-files]').onchange=async e=>{try{for(const file of e.target.files)addImages([await uploadImage(file)]);error('');}catch(e){error(e.message);}finally{e.target.value='';}};
 dialog.querySelector('form').onsubmit=async event=>{event.preventDefault();const form=event.currentTarget;form.inert=true;form.setAttribute('aria-busy','true');submitting=true;const submit=q('[type="submit"]');submit.disabled=true;error('');try{if(busy?.())throw Error('Attendi o interrompi la tua richiesta in corso.');const patches=[...draft.values()].filter(x=>x.enabled).map(x=>({clip:x.clip,prompt:x.prompt,images:x.mode==='i2v'?[x.start_image]:[...x.images],lip_sync:x.lip_sync,audio_guide:x.audio_guide??true,...memoryPatch(x,!!data.memory_recovery),...endFramePatch(x,!!data.end_frame_recovery),...(x.mode==='i2v'?{mode:'i2v',start_image:x.start_image}:x.mode==='video'?{mode:'video',reference_megapixels:Number(q('[name="reference_megapixels"]').value),...videoGuideFields(x)}:{}),...(x.range?{start:x.first/24,end:x.last/24}:{})}));if(patches.some(x=>x.mode==='i2v'&&!x.start_image))throw Error('Scegli un’immagine iniziale per ogni clip I2V.');if(!patches.length||patches.some(x=>!x.prompt.trim()))throw Error('Descrivi le modifiche di ogni clip selezionato.');const selection=local.read();const parameters={...selection.parameters,...(q('[name="megapixels"]').value!==''?{megapixels:Number(q('[name="megapixels"]').value)}:{})};await editorControls?.saveForLaunch();const result=await api('/chats/'+chatId+'/video-edit',{source,...(data.imported?{segment_seconds:data.segment_seconds||15}:{}),versions:versions(),patches,parameters,...(selection.model?{model:selection.model}:{}),remount:q('[name="remount"]').checked,...(q('[name="video_steps"]').value!==''?{video_steps:Number(q('[name="video_steps"]').value)}:{}),assistant:dialog.querySelector('[name="assistant"]').checked,media:extra.map(x=>({id:x.id}))});closeDialog();await onQueued?.(result);}catch(e){error(e.message);}finally{submitting=false;form.inert=false;form.removeAttribute('aria-busy');if(!disposed)summary();}};
 if(restored){const s=restored.state;q('[data-common-prompt]').value=s.common_prompt;for(const key of ['megapixels','video_steps','reference_megapixels']){q(`[name="${key}"]`).value=s.values[key];q(`[name="${key}"]`).dispatchEvent(new Event('input',{bubbles:true}));}q('[name="remount"]').checked=s.values.remount;}
 if(restored?.last_launch)launchDirty=false;
 if((data.batch_requested||1)>1){
  const field=document.createElement('label');field.className='field';field.innerHTML='<span>Scegli una versione completa</span><select data-batch-branch><option value="">Scelta libera per clip</option></select>';
  const select=field.querySelector('select');for(let n=1;n<=data.batch_requested;n++){const o=document.createElement('option');o.value=String(n);o.textContent='Versione '+n+' su tutte le clip disponibili';select.append(o);}
  select.onchange=()=>{const n=Number(select.value);if(!n)return;for(const clip of data.clips){const v=[...(clip.versions||[])].reverse().find(v=>v.variant_index===n&&(!data.batch_id||v.variant_batch_id===data.batch_id));if(v)versionSelectors.get(clip.clip)?.(v.id);}summary();};
  q('.video-timeline-heading').after(field);
 }
 syncAllLipsync();dialog.showModal();if(restored)focusClip(restored.state.active,{enable:false});else if(selectFirst&&initialPrompt&&data.clips.length)focusClip(data.clips[0].clip);summary();
 const capture=()=>{const selection=local.read();return {signature:draftSignature(data.clips),model:selection.model,parameters:selection.parameters,values:{megapixels:q('[name="megapixels"]').value,video_steps:q('[name="video_steps"]').value,reference_megapixels:guideInput.value,assistant:q('[name="assistant"]').checked,remount:q('[name="remount"]').checked},active,common_prompt:q('[data-common-prompt]').value,image_ids:data.images.map(x=>x.id),clips:[...draft.values()].map(x=>({...x,images:[...x.images],anchor_images:{...x.anchor_images}})),versions:versions(),...(data.launch_settings?{clip_launches:clipLaunches}:{})};};
 // Refresh version choices too: another clip may have completed while this
 // dialog was open. Prepared imports now use the server's non-blocking cache.
 const reopen=async saved=>{await openVideoEdit({api,chatId,source,busy,onQueued,pickFile,segmentSeconds:data.segment_seconds||segmentSeconds,selectFirst:false,editorDraft:saved});closeDialog();};
 editorControls=videoEditorDraft(q('[data-timeline]'),{dialog,data,api,chatId,source,capture,reopen,restored:!!restored,beforeLaunch:()=>{
  if(!data.launch_settings)return;
  const selection=local.read(),parameters={...selection.parameters,...(q('[name="megapixels"]').value!==''?{megapixels:Number(q('[name="megapixels"]').value)}:{})};
  for(const clip of draft.values())if(clip.enabled)clipLaunches[String(clip.clip)]={model:selection.model,parameters:structuredClone(parameters),steps:q('[name="video_steps"]').value===''?null:Number(q('[name="video_steps"]').value),assistant:q('[name="assistant"]').checked,reference_megapixels:Number(guideInput.value),saved_at:Date.now()/1000};
  for(const card of cards.values())card.refreshLaunch?.();
 }});
 if(data.draft_error)error(data.draft_error);
 if(busy){let previous=!!busy();busyTimer=setInterval(()=>{const current=!!busy();if(current!==previous){previous=current;summary();for(const tools of clipTools)tools.refresh();}},1000);}
 return dialog;
}

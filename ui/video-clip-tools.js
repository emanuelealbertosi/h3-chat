import {openGallery} from './gallery.js';
import {uploadFile} from './file-upload.js';
import {openVideoExtend} from './video-extend.js';

const clock=n=>n.toLocaleString('it-IT',{maximumFractionDigits:3});

export function clipToolRequest({source,clip,range,versions,segmentSeconds},action,extra={}){
 return {source,clip,...(range?{start:range[0],end:range[1]}:{}),versions,
  ...(segmentSeconds?{segment_seconds:segmentSeconds}:{}),action,...extra};
}

export function mountClipTools(host,{api,chatId,source,clip,getRange,getVersions,segmentSeconds,busy,onQueued,data,pickFile}={}){
 const section=document.createElement('section');section.className='video-clip-tools';
 section.innerHTML='<strong>Post-produzione dello spezzone</strong><div class="video-edit-toolbar"><button type="button" class="btn small" data-clip-export>↓ Esporta spezzone</button><button type="button" class="btn small" data-clip-infographic>✧ Modifica con Infografica</button><button type="button" class="btn small" data-clip-replace>⇄ Sostituisci da PC / Galleria</button></div><p class="small-note">Usa la versione e il tratto selezionati sopra. La sostituzione viene salvata come nuova versione; il montaggio finale resta separato e conserva la canzone originale.</p><p class="settings-error" role="alert" hidden></p>';
 host.append(section);let pending=false,disposed=false,child;
 if(data?.extension_modes){const toolbar=section.querySelector('.video-edit-toolbar');for(const [side,label] of [['before','＋ Clip prima'],['after','＋ Clip dopo']]){const b=document.createElement('button');b.type='button';b.className='btn small';b.textContent=label;b.dataset.extend=side;b.onclick=()=>{child=openVideoExtend({api,chatId,source,clip,side,data,getVersions,segmentSeconds,busy,onQueued,pickFile});};toolbar.append(b);}}
 if(data?.clips?.length>1){
  const remove=document.createElement('button');remove.type='button';remove.className='btn small';remove.textContent='− Elimina clip dal montaggio';remove.dataset.clipDelete='';
  remove.onclick=()=>{
   const d=dialog('Elimina clip dal montaggio'),panel=d.querySelector('.prompt-options-body');
   panel.innerHTML='<p>Verrà creata una nuova versione senza questa clip e senza il tratto audio corrispondente. Il video originale resta disponibile. Non viene avviata una generazione AI.</p><button type="button" class="btn primary" data-confirm-delete>Elimina clip e monta</button>';
   panel.querySelector('[data-confirm-delete]').onclick=async()=>{pending=true;refresh();showError(null);try{if(busy?.())throw Error('Attendi la fine della richiesta attiva.');const result=await api('/chats/'+chatId+'/video-assemble',{source,versions:getVersions(),remove_clips:[clip.clip],...(segmentSeconds?{segment_seconds:segmentSeconds}:{})});d.close();await onQueued?.(result);}catch(e){showError(e);const box=d.querySelector('[role="alert"]');box.hidden=false;box.textContent=e.message;}finally{pending=false;refresh();}};
   d.showModal();
  };
  section.querySelector('.video-edit-toolbar').append(remove);
 }
 const buttons=[...section.querySelectorAll('button')],error=section.querySelector('[role="alert"]');
 const read=action=>clipToolRequest({source,clip:clip.clip,range:getRange(),versions:getVersions(),segmentSeconds},action);
 const showError=e=>{error.hidden=!e;error.textContent=e?.message||'';};
 const refresh=()=>{const working=!!busy?.();for(const b of buttons)b.disabled=pending||(working&&!b.dataset.extend);if(child?.classList.contains('video-extend-dialog')){const submit=child.querySelector('[type="submit"]');if(submit)submit.disabled=pending||working;}};
 async function queue(body){
  if(pending)return;
  pending=true;refresh();showError(null);
  try{if(busy?.())throw Error('Puoi preparare la timeline durante una generazione; avvia questa operazione quando termina.');const result=await api('/chats/'+chatId+'/video-clip',body);child?.close();await onQueued?.(result);}
  catch(e){showError(e);if(child){const box=child.querySelector('[role="alert"]');box.hidden=false;box.textContent=e.message;}}
  finally{pending=false;if(!disposed)refresh();}
 }
 function dialog(title){
  child?.close();const d=document.createElement('dialog');d.className='video-post-dialog prompt-options-dialog';
  d.innerHTML='<header><div><span class="eyebrow">POST-PRODUZIONE</span><h2></h2></div><button type="button" class="icon-button" data-close aria-label="Chiudi">×</button></header><div class="prompt-options-body"></div><p class="settings-error" role="alert" hidden></p>';
  d.querySelector('h2').textContent=title;d.querySelector('[data-close]').onclick=()=>d.close();d.onclose=()=>{d.remove();if(child===d)child=null;};document.body.append(d);child=d;return d;
 }
 section.querySelector('[data-clip-export]').onclick=()=>void queue(read('export'));
 section.querySelector('[data-clip-infographic]').onclick=()=>{
  const body=read('infographic'),range=getRange()||[0,clip.end-clip.start],d=dialog('Modifica con Infografica'),panel=d.querySelector('.prompt-options-body');
  panel.innerHTML='<p class="small-note" data-target></p><label class="field"><span>Descrivi composizione, scritte ed effetti</span><textarea rows="5" maxlength="24000" data-prompt placeholder="Dividi lo schermo in due: video a sinistra, titoli a destra. A 5 secondi appare una scritta neon con effetto bump…"></textarea></label><div data-options></div><p class="small-note">La clip viene collegata automaticamente. Durata, proporzioni e audio originale sono conservati. Nel canvas puoi modificare la grafica, esportare il risultato e inserirlo nella timeline.</p><button type="button" class="btn primary" data-create>Crea nel canvas</button>';
  panel.querySelector('[data-target]').textContent='Clip '+clip.clip+' · '+clock(range[0])+'–'+clock(range[1])+' s · durata esatta '+clock(range[1]-range[0])+' s';
  const values={layout:'full',style:'auto',palette:'auto'};
  for(const [key,label,choices] of [
   ['layout','Composizione',[['full','Intero'],['columns2','2 affiancati'],['rows2','2 sopra / sotto'],['columns3','3 affiancati'],['pip','Riquadro sovrapposto'],['grid2x2','4 pannelli'],['grid3x2','6 pannelli']]],
   ['style','Stile',[['auto','Dal prompt'],['professional','Professionale'],['playful','Giocoso'],['advert','Spot'],['tech','Tecnologico'],['comic','Fumetto']]],
   ['palette','Colori',[['auto','Dal prompt'],['natural','Naturali'],['pastel','Pastello'],['vivid','Vivaci'],['neon','Neon'],['dark','Scuri']]]]){
   const field=document.createElement('div');field.className='prompt-field';const title=document.createElement('span');title.className='prompt-field-label';title.textContent=label;const group=document.createElement('div');group.className='prompt-choices';group.setAttribute('role','group');group.ariaLabel=label;
   for(const [value,text] of choices){const b=document.createElement('button');b.type='button';b.className='prompt-choice';b.textContent=text;b.dataset.value=value;b.setAttribute('aria-pressed',String(value===values[key]));b.onclick=()=>{values[key]=value;for(const button of group.children)button.setAttribute('aria-pressed',String(button===b));};group.append(b);}
   field.append(title,group);panel.querySelector('[data-options]').append(field);
  }
  const create=panel.querySelector('[data-create]');create.onclick=async()=>{create.disabled=true;try{await queue({...body,prompt:panel.querySelector('[data-prompt]').value,infographic:values});}finally{create.disabled=false;}};
  d.showModal();panel.querySelector('[data-prompt]').focus();
 };
 section.querySelector('[data-clip-replace]').onclick=()=>{
  const body=read('replace'),d=dialog('Sostituisci lo spezzone'),panel=d.querySelector('.prompt-options-body');
  panel.innerHTML='<p>Inserisci un video già pronto come nuova versione del tratto selezionato.</p><p class="small-note">Il video viene adattato al formato senza deformarlo, a 24 fps. Se è più lungo, viene usato l’inizio; se è più corto, viene segnalato. La canzone originale resta continua. Il nuovo file non avvia MiniMax.</p><div class="video-edit-toolbar"><button type="button" class="btn primary" data-pc>Carica dal PC</button><button type="button" class="btn" data-gallery>Dalla galleria</button></div><input type="file" hidden data-file>';
  const select=media=>queue({...body,media_id:media.id,label:'Video importato · '+media.name.slice(0,100)});
  panel.querySelector('[data-gallery]').onclick=()=>openGallery({api,kind:'video',multiple:false,onSelect:items=>select(items[0])});
  panel.querySelector('[data-pc]').onclick=()=>panel.querySelector('[data-file]').click();
  panel.querySelector('[data-file]').onchange=async e=>{const b=panel.querySelector('[data-pc]');b.disabled=true;try{const file=e.target.files[0];if(file)await select(await uploadFile(file,{api}));}catch(e){const box=d.querySelector('[role="alert"]');box.hidden=false;box.textContent=e.message;}finally{b.disabled=false;e.target.value='';}};
  d.showModal();
 };
 refresh();return {refresh,close(){disposed=true;child?.close();}};
}

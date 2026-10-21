// Recover a precise interrupted job, never the latest unrelated chat prompt.
export function appendVideoResume(host,{api,message,chatId,busy,onQueued,notify}={}){
 if(message?.role!=='assistant'||!['failed','cancelled','interrupted'].includes(message.status)||message.meta?.intent!=='video')return;
 const button=document.createElement('button');button.type='button';button.className='text-button';button.dataset.videoResume='';
 button.textContent='Riprendi clip mancanti';button.title='Conserva le clip riuscite e riprende la stessa richiesta, con i suoi parametri originali.';host.append(button);
 button.onclick=async()=>{
  if(button.disabled)return;button.disabled=true;
  let dialog;
  try{
   const saved=await api('/chats/'+chatId+'/video-resume/'+encodeURIComponent(message.id));
   dialog=document.createElement('dialog');dialog.className='video-post-dialog prompt-options-dialog video-resume-dialog';
   dialog.innerHTML='<header><div><span class="eyebrow">RIPRESA VIDEO</span><h2>Riprendi dalle clip mancanti</h2></div><button type="button" class="icon-button" data-close aria-label="Chiudi">×</button></header><div class="prompt-options-body"><p data-summary></p><p class="small-note" data-missing></p><p class="small-note">Le clip già riuscite vengono riutilizzate. Modello, riferimenti, audio, prompt, seed e impostazioni della richiesta restano quelli originali. Le nuove versioni create in seguito non vengono incorporate automaticamente in questa ripresa.</p><p class="small-note" data-busy hidden>Una tua richiesta è ancora attiva o in coda. Puoi riprendere il video quando termina.</p><div class="video-edit-toolbar"><button type="button" class="btn" data-cancel>Annulla</button><button type="button" class="btn primary" data-submit>Riprendi generazione</button></div><p class="settings-error" role="alert" hidden></p></div>';
   dialog.querySelector('[data-summary]').textContent=saved.assembly_only?'Tutte le '+saved.total+' clip sono già salvate: verrà completato soltanto il montaggio.':saved.completed+' clip già salvate · '+saved.remaining+' da generare, su '+saved.total+' richieste.';
   dialog.querySelector('[data-missing]').textContent=saved.missing_clips.length?'Clip da generare: '+saved.missing_clips.slice(0,30).join(', ')+(saved.missing_clips.length>30?' e altre '+(saved.missing_clips.length-30):'')+'.':'Nessuna clip verrà rigenerata.';
   const submit=dialog.querySelector('[data-submit]'),error=dialog.querySelector('[role="alert"]');
   if(saved.timeline_available){
    const timeline=document.createElement('button');timeline.type='button';timeline.className='btn';timeline.dataset.openSavedTimeline='';timeline.textContent='Apri timeline salvata';
    dialog.querySelector('.video-edit-toolbar').prepend(timeline);
    timeline.onclick=async()=>{timeline.disabled=true;error.hidden=true;try{const {openVideoEdit}=await import('./video-edit.js');await openVideoEdit({api,chatId,source:saved.checkpoint_job_id||saved.job_id,busy,onQueued});dialog.close();}catch(e){error.hidden=false;error.textContent=e.message;timeline.disabled=false;}};
   }
   if(saved.assembly_only)submit.textContent='Completa montaggio';
   let sending=false;
   const refresh=()=>{submit.disabled=sending||!!busy?.();dialog.querySelector('[data-busy]').hidden=!busy?.();};
   const timer=setInterval(refresh,1000);
   dialog.onclose=()=>{clearInterval(timer);dialog.remove();button.disabled=false;};
   for(const control of dialog.querySelectorAll('[data-close],[data-cancel]'))control.onclick=()=>dialog.close();
   submit.onclick=async()=>{
    if(sending)return;sending=true;error.hidden=true;refresh();
    try{
     if(busy?.())throw Error('Attendi il completamento della tua richiesta attiva prima di riprendere il video.');
     const result=await api('/chats/'+chatId+'/video-resume',{job_id:saved.job_id});
     await onQueued?.(result);dialog.close();notify?.(result.status==='queued'?'Ripresa accodata: le clip riuscite sono conservate.':'Questa ripresa è già stata registrata.');
    }catch(e){error.hidden=false;error.textContent=e.message;}
    finally{sending=false;refresh();}
   };
   document.body.append(dialog);dialog.showModal();refresh();
  }catch(e){notify?.(e.message);if(!notify){let note=host.querySelector('[data-video-resume-error]');if(!note){note=document.createElement('span');note.className='render-error';note.dataset.videoResumeError='';note.setAttribute('role','alert');host.append(note);}note.textContent=e.message;}dialog?.remove();button.disabled=false;}
 };
 return button;
}

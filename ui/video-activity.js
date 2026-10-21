export function appendVideoActivity(host,{job,message,api}){
 const id=job?.id||message?.meta?.timing?.job_id,chatId=job?.chat_id;if(!id||!chatId)return;
 const button=document.createElement('button');button.type='button';button.className='text-button';button.textContent='Attività · apri log';host.append(button);
 button.onclick=()=>openVideoActivity({id,chatId,api});
}

export function openVideoActivity({id,chatId,api}){
 const dialog=document.createElement('dialog');dialog.className='video-activity-dialog';dialog.setAttribute('aria-label','Attività del video');
 dialog.innerHTML='<header><h2>Attività del video</h2><button type="button" class="icon-button" data-close aria-label="Chiudi">×</button></header><div class="video-activity-body"><h3 data-stage>Leggo l’attività…</h3><p data-detail></p><p data-count></p><progress max="1" data-progress></progress><p class="small-note" data-time></p><p class="settings-error" data-error hidden></p><h3>Ultimi passaggi</h3><ol data-events></ol></div>';
 document.body.append(dialog);const q=s=>dialog.querySelector(s);let timer,closed=false,useApi=true,latest=null;
 q('[data-close]').onclick=()=>dialog.close();dialog.onclose=()=>{closed=true;clearTimeout(timer);dialog.remove();};
 const duration=seconds=>Math.floor(seconds/60)+':'+String(Math.floor(seconds%60)).padStart(2,'0');
 async function refresh(){
  try{
   let data;
   if(useApi){try{data=await api('/chats/'+chatId+'/video-activity/'+id);}catch{useApi=false;}}
   if(!data){const response=await fetch('/media/outputs/'+id+'/activity.json',{cache:'no-store'});if(!response.ok)throw Error('I dettagli saranno disponibili a breve.');data=await response.json();}
   if(closed)return;latest=data;q('[data-stage]').textContent=data.stage;q('[data-detail]').textContent=data.detail===data.stage?'':data.detail;
   q('[data-count]').textContent=data.clips_completed+' / '+data.clips_total+' clip generate'+(data.phase==='instructions'?' · Prima si preparano le istruzioni, poi vengono generati i video.':'');
   const bar=q('[data-progress]');bar.max=data.clips_total||1;if(data.phase==='generation'||data.phase==='assembly'||data.status==='done')bar.value=data.clips_completed;else bar.removeAttribute('value');
   q('[data-time]').textContent='Tempo trascorso '+duration(Math.max(0,Date.now()/1000-data.created_at))+(data.last_signal_at?' · Ultimo segnale del motore '+duration(Math.max(0,Date.now()/1000-data.last_signal_at))+' fa':'');
   const error=q('[data-error]');error.hidden=!data.error;error.textContent=data.error||'';
   const list=q('[data-events]');list.replaceChildren();for(const event of data.events){const li=document.createElement('li'),clock=document.createElement('time'),label=document.createElement('span');clock.textContent=event.time;label.textContent=event.label;li.append(clock,label);list.append(li);}
   list.scrollTop=list.scrollHeight;
  }catch(e){if(!closed&&!latest)q('[data-detail]').textContent=e.message;}
  finally{if(!closed)timer=setTimeout(refresh,1500);}
 }
 dialog.showModal();refresh();return dialog;
}

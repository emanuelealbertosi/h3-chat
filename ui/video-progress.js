// One lazy player per job. Completed revisions only, never reused originals.
const panels=new Map();
export function clearUnusedVideoProgress(){
 for(const [id,state] of panels)if(!state.node.isConnected){clearTimeout(state.timer);const video=state.node.querySelector('video');video.pause();video.removeAttribute('src');video.load();state.audio.pause();state.audio.removeAttribute('src');state.audio.load();panels.delete(id);}
}
export function appendVideoProgress(host,{job,message,audios=[]}={}){
 const id=job?.id||message?.meta?.video_parameters?.timeline_id;
 if(!id||!/^[a-f0-9]{32}$/.test(id)||message?.meta?.intent!=='video')return;
 let state=panels.get(id);
 if(!state){
  const node=document.createElement('details');node.className='video-progress';
  node.innerHTML='<summary>Clip pronte · apri anteprima</summary><p class="small-note" data-status>Le anteprime si caricano soltanto quando le apri.</p><div class="video-progress-clips" role="group" aria-label="Clip completate"></div><video controls playsinline preload="none" hidden></video><p class="small-note" data-current></p>';
  state={node,loading:false,record:null,audios,timer:null};panels.set(id,state);
  const video=node.querySelector('video'),audio=new Audio();audio.preload='none';state.audio=audio;
  const sync=()=>{if(state.track){audio.currentTime=state.offset+video.currentTime;audio.playbackRate=video.playbackRate;}};
  video.onplay=()=>{if(state.track){sync();audio.play().catch(()=>{node.querySelector('[data-current]').textContent+=' · Premi di nuovo Play per attivare l’audio.';});}};
  video.onpause=video.onended=()=>audio.pause();video.onseeking=sync;video.onratechange=sync;
  async function refresh(){
   clearTimeout(state.timer);if(!node.open||!node.isConnected||state.loading)return;
   state.loading=true;
   try{
    const response=await fetch('/media/outputs/'+id+'/scenes.json',{cache:'no-store'});
    if(!response.ok)throw Error('La prima clip non è ancora pronta.');
    const record=await response.json();state.record=record;
    const ready=record.revision_request?new Set(record.revision_completed||[]):new Set(Array.from({length:record.completed||0},(_,i)=>i+1));
    const grid=node.querySelector('.video-progress-clips');
    for(const button of [...grid.children])if(!ready.has(Number(button.dataset.clip)))button.remove();
    for(const number of [...ready].sort((a,b)=>a-b)){
     const path=record.outputs?.[number-1];if(!path||!/^outputs\/[a-zA-Z0-9_./-]+\.mp4$/.test(path)||path.includes('..')||grid.querySelector('[data-clip="'+number+'"]'))continue;
     const b=document.createElement('button');b.type='button';b.className='btn small';b.dataset.clip=number;b.textContent='▷ '+number;
     b.onclick=()=>{
      audio.pause();const scene=record.timeline[number-1];state.offset=(record.audio_start||0)+scene.start;
      const index=record.plan?.audios?.find(a=>['reuse','lipsync'].includes(a.role))?.index;
      state.track=state.audios[index-1];if(state.track)audio.src='/media/'+state.track.path;
      video.pause();video.hidden=false;video.muted=!!state.track;video.src='/media/'+path;video.load();
      node.querySelector('[data-current]').textContent='Clip '+number+' · '+scene.duration.toLocaleString('it-IT')+' s'+(state.track?' · audio originale':'');
      for(const child of grid.children)child.setAttribute('aria-pressed',String(child===b));
     };grid.append(b);
    }
    node.querySelector('summary').textContent='Clip pronte · '+ready.size+(record.revision_request?' / '+record.revision_request.length:' / '+record.timeline.length);
    node.querySelector('[data-status]').textContent=ready.size?'Scegli una clip per riprodurla. Il montaggio completo continua senza interruzioni.':'In attesa della prima clip completata…';
   }catch(e){node.querySelector('[data-status]').textContent=e.message;}
   finally{state.loading=false;if(node.open&&node.isConnected)state.timer=setTimeout(refresh,10000);}
  }
  node.ontoggle=()=>{if(node.open)void refresh();else{clearTimeout(state.timer);video.pause();audio.pause();video.removeAttribute('src');video.load();video.hidden=true;audio.removeAttribute('src');audio.load();}};
 }
 state.audios=audios;host.append(state.node);
 clearUnusedVideoProgress();
}

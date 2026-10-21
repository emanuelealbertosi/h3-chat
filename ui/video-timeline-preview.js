export function previewTime(value){
 const parts=String(value).trim().replace(',','.').split(':');
 if(!parts.length||parts.length>3||parts.some(p=>!/^\d+(?:\.\d+)?$/.test(p)))throw Error('Usa un tempo come 0:15 oppure 1:30.');
 const numbers=parts.map(Number);if(numbers.some(n=>!Number.isFinite(n))||numbers.slice(1).some(n=>n>=60))throw Error('Minuti e secondi devono essere inferiori a 60.');
 return numbers.reduce((total,n)=>total*60+n,0);
}
const clock=t=>{const ms=Math.round(Math.max(0,t)*1000),s=Math.floor(ms/1000);return Math.floor(s/60)+':'+String(s%60).padStart(2,'0')+(ms%1000?'.'+String(ms%1000).padStart(3,'0'):'');};

export function previewPosition(clips,time){
 if(!clips.length)throw Error('La timeline non contiene clip.');
 const t=Math.max(clips[0].start,Math.min(clips.at(-1).end,time));
 const index=clips.findIndex(c=>t<c.end);const i=index<0?clips.length-1:index,clip=clips[i];
 return {clip,index,time:t,mediaTime:(clip.preview_start||0)+t-clip.start};
}

function ready(media,event,predicate,signal){
 if(signal.aborted)return Promise.reject(new DOMException('Anteprima annullata','AbortError'));
 if(predicate())return Promise.resolve();
 return new Promise((resolve,reject)=>{
  const finish=error=>{clearTimeout(timer);media.removeEventListener(event,check);media.removeEventListener('error',failure);signal.removeEventListener('abort',abort);error?reject(error):resolve();};
  const check=()=>{if(predicate())finish();},failure=()=>finish(Error('Il browser non riesce a riprodurre questo file.'));
  const abort=()=>finish(new DOMException('Anteprima annullata','AbortError'));
  const timer=setTimeout(()=>finish(Error('Il video sta impiegando troppo tempo a caricarsi. Riprova l’anteprima.')),20000);
  media.addEventListener(event,check);media.addEventListener('error',failure);signal.addEventListener('abort',abort,{once:true});
 });
}

// Play saved variants directly. The original audio is the one timeline clock;
// embedded clip audio is muted, and buffering pauses both audio and pictures.
export function videoTimelinePreview(host,{clips,audio,getFocusRange,onStart}={}){
 const duration=clips.at(-1)?.end||0,section=document.createElement('section');section.className='video-timeline-preview';
 section.innerHTML='<button type="button" class="btn" data-timeline-preview-open aria-expanded="false">▶ Anteprima timeline</button><div data-timeline-preview-body hidden><p class="small-note">Mostra le versioni già create e selezionate nella timeline, con l’audio originale.</p><div class="video-preview-range" role="group" aria-label="Parte della timeline da vedere"><button type="button" class="btn small" data-preview-range="all" aria-pressed="true">Intero video</button><button type="button" class="btn small" data-preview-range="clip">Clip aperta</button><button type="button" class="btn small" data-preview-range="custom">Intervallo</button></div><div class="video-preview-times" hidden><label class="field"><span>Da</span><input type="text" data-preview-start aria-label="Inizio anteprima"></label><label class="field"><span>A</span><input type="text" data-preview-end aria-label="Fine anteprima"></label></div><div class="video-preview-screen" data-preview-screen></div><div class="video-preview-controls"><button type="button" class="btn primary" data-timeline-play>▶ Riproduci</button><button type="button" class="btn" data-timeline-stop>Stop</button><button type="button" class="btn small" data-timeline-mute aria-pressed="false">🔊 Audio</button><input type="range" min="0" max="1" step="0.05" value="1" data-timeline-volume aria-label="Volume anteprima"></div><input type="range" min="0" step="0.0416666667" value="0" data-timeline-seek aria-label="Posizione nella timeline"><p class="small-note" data-timeline-clock></p><p class="small-note" role="status" data-timeline-status></p></div>';
 host.append(section);const q=s=>section.querySelector(s),toggle=q('[data-timeline-preview-open]'),body=q('[data-timeline-preview-body]'),seek=q('[data-timeline-seek]');
 let master,decks=[],front=0,position=0,range=[0,duration],mode='all',playing=false,disposed=false,operation,preload,frame,dragResume=false;
 const status=text=>{q('[data-timeline-status]').textContent=text;};
 toggle.disabled=!audio?.url||!duration;if(toggle.disabled)toggle.title='L’anteprima della timeline sarà disponibile dopo l’aggiornamento del motore.';
 q('[data-preview-start]').value=clock(0);q('[data-preview-end]').value=clock(duration);
 function paint(){
  seek.min=range[0];seek.max=range[1];seek.value=position;
  q('[data-timeline-clock]').textContent=clock(position)+' / '+clock(duration)+' · anteprima '+clock(range[0])+'–'+clock(range[1]);
  q('[data-timeline-play]').textContent=playing?'⏸ Pausa':'▶ Riproduci';
  q('[data-preview-range="clip"]').disabled=!getFocusRange?.();
  for(const b of section.querySelectorAll('[data-preview-range]'))b.setAttribute('aria-pressed',String(b.dataset.previewRange===mode));
 }
 function cancel(){operation?.abort();preload?.abort();cancelAnimationFrame(frame);}
 function pause(){
  if(master&&playing)position=Math.min(range[1],Math.max(range[0],master.currentTime-(audio.start||0)));
  playing=false;cancel();master?.pause();for(const d of decks)d.video.pause();paint();
 }
 function create(){
  if(master)return;master=document.createElement('audio');master.preload='metadata';master.src=audio.url;master.muted=false;master.hidden=true;master.dataset.timelineAudio='';body.append(master);
  master.addEventListener('ended',()=>{pause();position=range[1];paint();status('Fine anteprima.');});
  master.addEventListener('waiting',()=>{if(playing)void move(position,true);});
  for(let i=0;i<2;i++){
   const video=document.createElement('video');video.muted=true;video.playsInline=true;video.preload='auto';video.hidden=i!==front;video.setAttribute('aria-label','Video della timeline');
   video.addEventListener('waiting',()=>{if(playing&&decks[front]?.video===video)void move(Math.max(range[0],master.currentTime-(audio.start||0)),true);});
   q('[data-preview-screen]').append(video);decks.push({video,key:null});
  }
  master.load();
 }
 async function prepare(deck,mapped,signal){
  const v=deck.video,key=[mapped.clip.clip,mapped.clip.selected_version,mapped.clip.url,mapped.clip.preview_start||0].join('|');
  if(v.getAttribute('src')!==mapped.clip.url){v.pause();v.src=mapped.clip.url;v.load();deck.key=null;}
  await ready(v,'loadedmetadata',()=>v.readyState>=1,signal);
  // At the final endpoint display the last frame rather than seeking past EOF.
  const target=Math.min(mapped.mediaTime,(mapped.clip.preview_start||0)+mapped.clip.end-mapped.clip.start-1/24);
  if(Math.abs(v.currentTime-target)>1/96){v.currentTime=Math.max(0,target);await ready(v,'seeked',()=>!v.seeking,signal);}
  await ready(v,'canplay',()=>v.readyState>=2,signal);deck.key=key;
 }
 function prefetch(index){
  preload?.abort();if(index+1>=clips.length||clips[index+1].start>=range[1])return;
  const signal=(preload=new AbortController()).signal,next=previewPosition(clips,clips[index+1].start);
  void prepare(decks[1-front],next,signal).catch(()=>{});
 }
 async function move(time,resume=false){
  if(disposed)return;create();pause();position=Math.max(range[0],Math.min(range[1],time));paint();
  const op=operation=new AbortController(),signal=op.signal,mapped=previewPosition(clips,Math.min(position,range[1]-1/24));
  status('Caricamento anteprima · clip '+mapped.clip.clip+'…');
  try{
   await ready(master,'loadedmetadata',()=>master.readyState>=1,signal);
   const key=[mapped.clip.clip,mapped.clip.selected_version,mapped.clip.url,mapped.clip.preview_start||0].join('|');
   const next=decks[1-front].key===key?1-front:front;
   await prepare(decks[next],mapped,signal);if(signal.aborted||disposed)return;
   front=next;for(let i=0;i<decks.length;i++)decks[i].video.hidden=i!==front;
   master.currentTime=(audio.start||0)+position;
   await ready(master,'seeked',()=>!master.seeking,signal);if(signal.aborted||disposed)return;
   status('Clip '+mapped.clip.clip+(mapped.clip.versions?.find(v=>v.id===mapped.clip.selected_version)?.label?' · '+mapped.clip.versions.find(v=>v.id===mapped.clip.selected_version).label:''));
   if(resume&&position<range[1]){
    onStart?.();await decks[front].video.play();if(signal.aborted||disposed){decks[front].video.pause();return;}
    await master.play();if(signal.aborted||disposed){master.pause();return;}
    playing=true;paint();frame=requestAnimationFrame(tick);
   }
   prefetch(mapped.index);
  }catch(e){if(e.name!=='AbortError'){pause();status(e.message);}}
 }
 function tick(){
  if(!playing||disposed)return;
  position=Math.max(range[0],master.currentTime-(audio.start||0));
  if(position>=range[1]){pause();position=range[1];paint();status('Fine anteprima.');return;}
  const mapped=previewPosition(clips,position),deck=decks[front];
  const key=[mapped.clip.clip,mapped.clip.selected_version,mapped.clip.url,mapped.clip.preview_start||0].join('|');
  if(deck.key!==key){void move(position,true);return;}
  if(Math.abs(deck.video.currentTime-mapped.mediaTime)>.15){void move(position,true);return;}
  paint();frame=requestAnimationFrame(tick);
 }
 function setRange(next){
  const focus=getFocusRange?.();if(next==='clip'&&!focus)return;
  mode=next;q('.video-preview-times').hidden=mode!=='custom';
  try{
   const selected=mode==='all'?[0,duration]:mode==='clip'?focus:[previewTime(q('[data-preview-start]').value),previewTime(q('[data-preview-end]').value)];
   if(!selected.every(Number.isFinite)||selected[0]<0||selected[0]>=selected[1]||selected[1]>duration)throw Error('Scegli inizio e fine entro la durata del video.');
   range=selected;q('[data-timeline-play]').disabled=false;void move(range[0],false);
  }catch(e){pause();q('[data-timeline-play]').disabled=true;status(e.message);}paint();
 }
 toggle.onclick=()=>{body.hidden=!body.hidden;toggle.setAttribute('aria-expanded',String(!body.hidden));if(body.hidden)pause();else{create();setRange(mode);}};
 for(const b of section.querySelectorAll('[data-preview-range]'))b.onclick=()=>setRange(b.dataset.previewRange);
 q('[data-preview-start]').onchange=q('[data-preview-end]').onchange=()=>setRange('custom');
 q('[data-timeline-play]').onclick=()=>{if(playing)pause();else void move(position>=range[1]-1/24?range[0]:position,true);};
 q('[data-timeline-stop]').onclick=()=>void move(range[0],false);
 seek.oninput=()=>{const time=Number(seek.value);dragResume=dragResume||playing;pause();position=time;paint();};
 seek.onchange=()=>{const resume=dragResume||playing;dragResume=false;void move(Number(seek.value),resume);};
 q('[data-timeline-mute]').onclick=()=>{create();master.muted=!master.muted;q('[data-timeline-mute]').setAttribute('aria-pressed',String(master.muted));q('[data-timeline-mute]').textContent=master.muted?'🔇 Audio':'🔊 Audio';};
 q('[data-timeline-volume]').oninput=e=>{create();master.volume=Number(e.target.value);};
 const visibility=()=>{if(document.hidden)pause();};document.addEventListener('visibilitychange',visibility);
 paint();return {refresh(number){if(body.hidden)return;const mapped=previewPosition(clips,Math.min(position,range[1]-1/24));if(number==null||mapped.clip.clip===number)void move(position,playing);else if(clips[mapped.index+1]?.clip===number)prefetch(mapped.index);},focusChanged(){paint();if(mode==='clip'&&!body.hidden)setRange('clip');},close(){disposed=true;pause();document.removeEventListener('visibilitychange',visibility);for(const d of decks){d.video.removeAttribute('src');d.video.load();}if(master){master.removeAttribute('src');master.load();}}};
}

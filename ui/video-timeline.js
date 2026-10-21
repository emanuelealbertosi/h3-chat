import {escape as esc} from './render.js';
import {clipVersionsFan,modifiedVersionCount,selectedSeedLabel} from './video-clip-versions.js';

const clock=value=>{const millis=Math.round(Math.max(0,Number(value)||0)*1000),seconds=Math.floor(millis/1000);return Math.floor(seconds/60)+':'+String(seconds%60).padStart(2,'0')+(millis%1000?'.'+String(millis%1000).padStart(3,'0'):'');};

// Selection and focus are separate: several clips can be queued while only
// one editor is open. One decoder supplies lazy thumbnails for visible tiles.
export function videoTimeline(host,clips,{onFocus,onToggle,onVersion}={}){
 host.className='video-timeline';host.setAttribute('aria-label','Segmenti del video');
 const tiles=new Map();let disposed=false,processing=false,observer;
 const queue=[],decoder=document.createElement('video');decoder.muted=true;decoder.preload='metadata';
 const wait=(event,action)=>new Promise(resolve=>{
  let timer;const done=()=>{clearTimeout(timer);decoder.removeEventListener(event,done);decoder.removeEventListener('error',done);resolve();};
  decoder.addEventListener(event,done,{once:true});decoder.addEventListener('error',done,{once:true});timer=setTimeout(done,4000);action();
 });
 async function thumbnails(){
  if(processing)return;processing=true;
  try{while(queue.length&&!disposed){
   const {clip,canvas}=queue.shift(),url=clip.url,offset=clip.preview_start;
   if(!canvas.isConnected)continue;
   if(decoder.getAttribute('src')!==clip.url)await wait('loadeddata',()=>{decoder.src=clip.url;decoder.load();});
   if(disposed)break;
   if(url!==clip.url||offset!==clip.preview_start)continue;
   const seconds=(clip.preview_start||0)+Math.min(.1,(clip.end-clip.start)/2);
   if(decoder.readyState>=2&&Math.abs(decoder.currentTime-seconds)>.03)await wait('seeked',()=>{decoder.currentTime=seconds;});
   if(disposed)break;
   if(url!==clip.url||offset!==clip.preview_start)continue;
   if(decoder.readyState>=2&&decoder.videoWidth){const context=canvas.getContext('2d'),scale=Math.min(canvas.width/decoder.videoWidth,canvas.height/decoder.videoHeight);context.fillStyle='#153d40';context.fillRect(0,0,canvas.width,canvas.height);context.drawImage(decoder,(canvas.width-decoder.videoWidth*scale)/2,(canvas.height-decoder.videoHeight*scale)/2,decoder.videoWidth*scale,decoder.videoHeight*scale);canvas.dataset.previewReady='true';}
  }}finally{processing=false;}
 }
 const fan=clipVersionsFan(host,{thumbnail:(clip,canvas)=>{queue.push({clip,canvas});void thumbnails();},onChoose:onVersion,onClose:()=>{for(const tile of tiles.values())tile.querySelector('button').setAttribute('aria-expanded','false');}});
 for(const clip of clips){
  const tile=document.createElement('div');tile.className='video-timeline-tile';
  tile.innerHTML=`<button type="button" data-focus="${clip.clip}" aria-expanded="false" aria-controls="video-clip-editor-${clip.clip}" aria-label="Modifica clip ${clip.clip}, ${clock(clip.start)}–${clock(clip.end)}"><canvas width="224" height="126" aria-hidden="true"></canvas><span><strong>Clip ${clip.clip}</strong><small>${clock(clip.start)}–${clock(clip.end)}</small></span></button><label class="video-timeline-check"><input type="checkbox" data-enabled aria-label="Seleziona clip ${clip.clip}"> <span>Da modificare</span></label>`;
  host.append(tile);tiles.set(clip.clip,tile);
  const seed=document.createElement('small');seed.dataset.clipSeed='';seed.textContent=selectedSeedLabel(clip);tile.querySelector('button').append(seed);
  if(clip.edited){const label=document.createElement('small');label.dataset.editedLabel='';label.textContent='✓ Aggiornata';tile.querySelector('button>span').append(label);}
  if(clip.versions?.length>1){const label=document.createElement('small');label.dataset.versionLabel='';label.textContent=clip.versions.find(v=>v.id===clip.selected_version)?.label||'';tile.querySelector('button>span').append(label);}
  const badge=document.createElement('span');badge.className='video-timeline-version-count';badge.dataset.versionCount='';badge.dataset.count=modifiedVersionCount(clip);badge.textContent=modifiedVersionCount(clip);badge.title=badge.textContent+(modifiedVersionCount(clip)===1?' nuova versione creata':' nuove versioni create');badge.setAttribute('aria-label',badge.title);tile.querySelector('button').append(badge);
  tile.querySelector('button').setAttribute('aria-controls','video-clip-editor-'+clip.clip+' '+ 'video-timeline-versions');
  tile.querySelector('button').onclick=()=>{onFocus?.(clip.clip);fan.open(clip);tile.querySelector('button').setAttribute('aria-expanded','true');};
  tile.querySelector('input').onchange=e=>onToggle?.(clip.clip,e.target.checked);
  if(Math.round((clip.end-clip.start)*24)<24){tile.querySelector('input').disabled=true;tile.title='Coda inferiore a un secondo: conservata senza rigenerazione.';}
  tile.querySelector('button').onkeydown=e=>{if(!['ArrowLeft','ArrowRight','Home','End'].includes(e.key))return;e.preventDefault();const list=[...tiles.values()],index=list.indexOf(tile),next=e.key==='Home'?0:e.key==='End'?list.length-1:Math.max(0,Math.min(list.length-1,index+(e.key==='ArrowRight'?1:-1)));list[next].querySelector('button').focus();};
 }
 if(typeof IntersectionObserver!=='undefined'){
  observer=new IntersectionObserver(entries=>{for(const entry of entries){if(!entry.isIntersecting)continue;observer.unobserve(entry.target);const clip=clips.find(c=>c.clip===Number(entry.target.querySelector('button').dataset.focus));queue.push({clip,canvas:entry.target.querySelector('canvas')});}void thumbnails();},{root:host});
  for(const tile of tiles.values())observer.observe(tile);
 }
 return {
  refresh(number){const tile=tiles.get(number),clip=clips.find(c=>c.clip===number);if(!tile||!clip)return;
   fan.refresh(number);const badge=tile.querySelector('[data-version-count]'),count=modifiedVersionCount(clip);badge.textContent=count;badge.dataset.count=count;badge.title=count+(count===1?' nuova versione creata':' nuove versioni create');badge.setAttribute('aria-label',badge.title);
   tile.querySelector('[data-clip-seed]').textContent=selectedSeedLabel(clip);
   let edited=tile.querySelector('[data-edited-label]');if(clip.edited&&!edited){edited=document.createElement('small');edited.dataset.editedLabel='';edited.textContent='✓ Aggiornata';tile.querySelector('button>span').append(edited);}else if(!clip.edited)edited?.remove();
   let label=tile.querySelector('[data-version-label]');if(!label){label=document.createElement('small');label.dataset.versionLabel='';tile.querySelector('button>span').append(label);}
   label.textContent=clip.versions?.find(v=>v.id===clip.selected_version)?.label||'';
   queue.push({clip,canvas:tile.querySelector('canvas')});void thumbnails();
  },
  update(selected,active){fan.focusChanged(active);for(const [number,tile] of tiles){const enabled=selected.has(number);tile.classList.toggle('selected',enabled);tile.classList.toggle('active',number===active);tile.querySelector('input').checked=enabled;tile.querySelector('button').setAttribute('aria-expanded',String(number===fan.active));
   if(number===active){const viewport=host.getBoundingClientRect(),bounds=tile.getBoundingClientRect();if(bounds.left<viewport.left)host.scrollLeft+=bounds.left-viewport.left-3;else if(bounds.right>viewport.right)host.scrollLeft+=bounds.right-viewport.right+3;}
  }},
  pausePreviews(){fan.pause();},
  close(){disposed=true;fan.dispose();observer?.disconnect();queue.length=0;decoder.pause();decoder.removeAttribute('src');decoder.load();}
 };
}

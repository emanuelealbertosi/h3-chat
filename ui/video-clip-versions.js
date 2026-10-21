import {escape as esc} from './render.js';

export const modifiedVersionCount=clip=>Math.max(0,(clip.versions?.length||1)-1);
export const seedLabel=seed=>Number.isInteger(seed)&&seed>=0&&seed<=2147483647?'Seed: '+seed:'Seed non registrato';
export const selectedSeedLabel=clip=>seedLabel(clip.versions?.find(v=>v.id===clip.selected_version)?.seed??clip.seed);
const dateLabel=version=>{
 const date=version.created?new Date(version.created*1000):null;
 return date&&!Number.isNaN(date.getTime())?date.toLocaleString('it-IT',{day:'2-digit',month:'short',year:'numeric',hour:'2-digit',minute:'2-digit'}):null;
};

// The fan lives outside the scrolling timeline so its cards never get clipped.
// Thumbnails share the timeline's decoder; only one optional preview can play.
export function clipVersionsFan(host,{thumbnail,onChoose,onClose}={}){
 const panel=document.createElement('section');panel.className='video-timeline-versions';panel.hidden=true;panel.id='video-timeline-versions';
 panel.setAttribute('aria-label','Versioni della clip');host.after(panel);
 let current=null,observer,player=null,playButton=null;
 function pause(){if(player){player.pause();player.removeAttribute('src');player.load();player.remove();player=null;}if(playButton){playButton.setAttribute('aria-pressed','false');playButton.textContent='▶ Anteprima';playButton=null;}}
 function close(){pause();observer?.disconnect();panel.hidden=true;panel.replaceChildren();current=null;onClose?.();}
 function mark(){const buttons=[...panel.querySelectorAll('[data-version-id]')];for(const b of buttons){const selected=b.dataset.versionId===current?.selected_version||!current?.selected_version&&b===buttons[0];b.setAttribute('aria-pressed',String(selected));b.querySelector('[data-current]').textContent=selected?'✓ In uso':'Usa questa versione';}}
 function preview(clip,variant,article,button){
  if(playButton===button){pause();return;}pause();playButton=button;
  const video=document.createElement('video');player=video;video.muted=true;video.playsInline=true;video.preload='metadata';video.className='video-version-player';video.setAttribute('aria-hidden','true');
  const offset=variant.preview_start||0;video.onloadedmetadata=()=>{if(player!==video)return;video.currentTime=offset;void video.play().catch(()=>{if(player===video)pause();});};
  video.ontimeupdate=()=>{if(player===video&&video.currentTime>=offset+clip.end-clip.start)pause();};video.onended=()=>{if(player===video)pause();};video.onerror=()=>{if(player===video)pause();};
  article.querySelector('.video-version-media').append(video);button.setAttribute('aria-pressed','true');button.textContent='❚❚ Pausa';video.src=variant.url;
 }
 function open(clip){
  pause();observer?.disconnect();current=clip;panel.hidden=false;
  const variants=clip.versions?.length?clip.versions:[{id:'original',label:'Originale',url:clip.url,preview_start:clip.preview_start}];
  const count=modifiedVersionCount(clip);
  panel.innerHTML=`<div class="video-versions-heading"><strong>Clip ${clip.clip} · scegli la versione</strong><button type="button" class="text-button" data-close-versions aria-label="Chiudi versioni clip ${clip.clip}">Chiudi ×</button></div><p class="small-note">L’originale e ${count} ${count===1?'nuova versione':'nuove versioni'}. La scelta viene usata per le prossime modifiche e per il montaggio.</p><div class="video-versions-fan" role="group" aria-label="Versioni clip ${clip.clip}"></div><p class="small-note" role="status" data-version-status></p>`;
  const strip=panel.querySelector('.video-versions-fan');
  variants.forEach((variant,index)=>{
   const article=document.createElement('article');article.className='video-version-card';article.style.setProperty('--version-angle',Math.max(-5,Math.min(5,(index-(variants.length-1)/2)*2.5))+'deg');
   const label=variant.label||(index?'Versione '+index:'Originale'),date=dateLabel(variant);
   article.innerHTML=`<button type="button" data-version-id="${esc(variant.id)}" aria-label="Usa ${esc(label)} · clip ${clip.clip}" aria-pressed="false"><div class="video-version-media"><canvas width="320" height="180" aria-label="Anteprima ${esc(label)}"></canvas></div><span class="video-version-info"><strong>${esc(label)}</strong>${date?`<time datetime="${new Date(variant.created*1000).toISOString()}" title="${variant.created_source==='file'?'Data del file conservato':'Data di creazione'}">${esc(date)}</time>`:'<small>Data non disponibile</small>'}<small data-current></small></span></button><button type="button" class="text-button video-version-play" data-version-preview aria-label="Anteprima ${esc(label)} · clip ${clip.clip}" aria-pressed="false">▶ Anteprima</button>`;
   const info=document.createElement('small');info.dataset.versionSeed='';info.textContent=seedLabel(variant.seed);article.querySelector('.video-version-info').append(info);
   const choose=article.querySelector('[data-version-id]');choose.onclick=()=>{pause();onChoose?.(clip.clip,variant.id);mark();panel.querySelector('[data-version-status]').textContent=label+' selezionata per la clip '+clip.clip;};
   article.querySelector('[data-version-preview]').onclick=e=>preview(clip,variant,article,e.currentTarget);
   choose.onkeydown=e=>{if(!['ArrowLeft','ArrowRight','Home','End'].includes(e.key))return;e.preventDefault();const buttons=[...strip.querySelectorAll('[data-version-id]')],at=buttons.indexOf(choose),next=e.key==='Home'?0:e.key==='End'?buttons.length-1:Math.max(0,Math.min(buttons.length-1,at+(e.key==='ArrowRight'?1:-1)));buttons[next]?.focus();};
   strip.append(article);article.variant=variant;
  });
  panel.querySelector('[data-close-versions]').onclick=close;
  panel.onkeydown=e=>{if(e.key==='Escape'){e.preventDefault();e.stopPropagation();const number=current?.clip;close();host.querySelector(`[data-focus="${number}"]`)?.focus();}};
  mark();
  const load=article=>thumbnail({...clip,...article.variant},article.querySelector('canvas'));
  if(typeof IntersectionObserver!=='undefined'){observer=new IntersectionObserver(entries=>{for(const entry of entries)if(entry.isIntersecting){observer.unobserve(entry.target);load(entry.target);}},{root:strip});for(const article of strip.children)observer.observe(article);}
  else for(const article of strip.children)load(article);
 }
 return {open,close,pause,refresh(number){if(current?.clip===number)mark();},focusChanged(number){if(current&&current.clip!==number)close();},get active(){return current?.clip??null;},dispose(){close();panel.remove();}};
}

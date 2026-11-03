import {htmlPage} from './slide-html.js';
import '../static/infographic-motion.js';
import '../static/infographic-cinema.js';

export async function openMotionPreview(deck,media){
 const pages=[];for(const page of deck.pages){if(page.status!=='ready')break;pages.push(page);}
 if(!pages.length)throw Error('Attendi almeno la prima scena completa.');
 const motion={...deck.infographic,durations:deck.infographic.durations.slice(0,pages.length)},total=motion.durations.reduce((a,b)=>a+b,0);
 const dialog=document.createElement('dialog');dialog.className='motion-continuous-preview';dialog.style.cssText='width:min(1200px,96vw);max-width:96vw;max-height:94vh;padding:16px;overflow:auto;';
 dialog.innerHTML='<header style="display:flex;align-items:center;justify-content:space-between"><h2>Anteprima continua · regia e transizioni</h2><button type="button" class="icon-button" data-close aria-label="Chiudi anteprima continua">×</button></header><p data-note></p><div data-viewport style="width:100%;position:relative;overflow:hidden;background:#101820"><div data-stage style="position:absolute;top:0;left:0;transform-origin:top left;width:1280px"></div></div><div class="infographic-player"><button type="button" class="btn" data-play>▶ Riproduci tutto</button><input data-total-time type="range" min="0" step="0.02" value="0" aria-label="Tempo dell’infografica completa"><output data-clock></output></div><p class="small-note">Riproduzione continua delle scene pronte con lo stesso montaggio grafico dell’MP4. La voce, se disponibile, segue i tempi originali. La musica completa è nell’MP4.</p>';
 document.body.append(dialog);const q=s=>dialog.querySelector(s),stage=q('[data-stage]'),viewport=q('[data-viewport]');dialog.showModal();
 let raf=0,time=0,start=0,playing=false,voice=null,clips=[];
 const ratio={'16:9':9/16,'9:16':16/9,'1:1':1,'4:3':3/4,'16:10':10/16}[deck.format]||9/16;const height=ratio*1280;
 stage.style.height=height+'px';q('[data-total-time]').max=total;
 q('[data-note]').textContent=pages.length+' / '+deck.pages.length+' scene pronte · caricamento…';
 const scale=()=>{const width=viewport.clientWidth;stage.style.transform='scale('+width/1280+')';viewport.style.height=width*height/1280+'px';};
 const observer=new ResizeObserver(scale);observer.observe(viewport);
 function stop(){cancelAnimationFrame(raf);playing=false;voice?.pause();for(const {element} of clips)element.pause();q('[data-play]').textContent='▶ Riproduci tutto';}
 dialog.onclose=()=>{stop();observer.disconnect();dialog.remove();};q('[data-close]').onclick=()=>dialog.close();
 try{
  for(const [i,page] of pages.entries()){
   const article=await htmlPage(deck,page,i,media,stage);if(!dialog.isConnected)return dialog;const frame=article.querySelector('iframe');
   article.style.position='absolute';article.style.inset='0';article.style.overflow='visible';article.style.pointerEvents='none';
   frame.dataset.h3Scene=String(i);frame.style.position='absolute';frame.style.inset='0';frame.style.transformOrigin='center';
  }
  const item=media.find(m=>m.id===motion.voice_id&&m.mime?.startsWith('audio/')&&/^(outputs|uploads)\/[\w./-]+$/.test(m.path)&&!m.path.split('/').includes('..'));
  if(item){voice=document.createElement('audio');voice.preload='metadata';voice.src='/media/'+item.path;dialog.append(voice);}
  const docs=[...stage.querySelectorAll('iframe[data-h3-scene]')].map(f=>f.contentDocument),specs=motion.videos||(motion.video?[motion.video]:[]);H3Motion.videoTracks(docs,motion);
  clips=docs.flatMap(doc=>[...doc.querySelectorAll('video[data-h3-video]')].map(element=>({element,spec:specs.find(s=>s.asset_id===element.dataset.h3Video),start:Number(element.dataset.h3VideoStart)||0}))).filter(c=>c.spec);
  const apply=t=>{time=Math.max(0,Math.min(total,t));H3Motion.render(stage,motion,time);for(const {element,spec,start} of clips){if(!Number.isFinite(element.duration))continue;const elapsed=Math.max(0,time-start),target=spec.end==='loop'?elapsed%element.duration:Math.min(elapsed,Math.max(0,element.duration-.04));if(!playing||Math.abs(element.currentTime-target)>.15)element.currentTime=target;if(playing&&time>=start&&(spec.end==='loop'||elapsed<element.duration-.04))element.play().catch(()=>{});else element.pause();}if(voice&&Number.isFinite(voice.duration)&&Math.abs(voice.currentTime-time)>.15)voice.currentTime=Math.min(voice.duration,time);q('[data-total-time]').value=time;q('[data-clock]').textContent=time.toFixed(1)+' / '+total.toFixed(1)+' s';};
  function tick(now){if(!dialog.isConnected){stop();return;}apply((now-start)/1000);if(time<total)raf=requestAnimationFrame(tick);else stop();}
  q('[data-play]').onclick=()=>{if(playing){stop();return;}if(time>=total)time=0;playing=true;start=performance.now()-time*1000;if(voice){voice.currentTime=time;voice.play().catch(()=>{});}q('[data-play]').textContent='Ⅱ Pausa';raf=requestAnimationFrame(tick);};
  q('[data-total-time]').oninput=()=>{stop();apply(Number(q('[data-total-time]').value));};
  q('[data-note]').textContent=pages.length+' / '+deck.pages.length+' scene pronte · voce e narrazione non vengono rigenerate';scale();apply(0);
 }catch(e){stop();q('[data-note]').textContent='Anteprima non disponibile: '+e.message;}
 return dialog;
}

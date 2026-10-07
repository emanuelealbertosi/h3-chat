/* Trusted timeline interpreter. Generated HTML never supplies JavaScript. */
(()=>{
 const states=new WeakMap(),effects=['fade','slide','zoom','pan','blur','wipe','strobe','typewriter','appear'];
 const clamp=v=>Math.max(0,Math.min(1,v));
 function number(value,fallback,low=0,high=180){const n=Number(value);return value!==undefined&&value!==''&&Number.isFinite(n)?Math.max(low,Math.min(high,n)):fallback;}
 function freeze(doc){for(const element of doc.querySelectorAll('*')){element.style?.setProperty('animation','none','important');element.style?.setProperty('transition','none','important');}}
 function ease(t,kind){t=clamp(t);return kind==='linear'?t:kind==='snap'?1-Math.pow(1-t,4):t*t*(3-2*t);}
 function prepare(doc){
  if(states.has(doc))return states.get(doc);
  const entries=[...doc.querySelectorAll('[data-motion]')].slice(0,160).map(element=>{
   const css=doc.defaultView.getComputedStyle(element),base={opacity:css.opacity,transform:css.transform,filter:css.filter,clipPath:css.clipPath};
   return {element,base,effect:effects.includes(element.dataset.motion)?element.dataset.motion:'fade'};
  });states.set(doc,entries);return entries;
 }
 function apply(doc,time,duration){
  const entries=prepare(doc),latest=Math.max(0,...entries.filter(e=>e.effect!=='pan').map(({element})=>number(element.dataset.start,0)+number(element.dataset.duration,.65,.05,30)));
  // Compress only overlong choreography; preserve its ordering and layout.
  // The last entrance finishes with a short readable hold before the cut.
  const scale=latest>duration*.9?duration*.9/latest:1;
  for(const {element,base,effect} of entries){
   const start=number(element.dataset.start,0)*scale,span=Math.max(.02,number(element.dataset.duration,.65,.05,30)*scale),raw=clamp((time-start)/span),p=ease(raw,element.dataset.ease),visible=time>=start;
   let opacity=visible?Number(base.opacity):0,transform='',filter=base.filter==='none'?'':base.filter,clip=base.clipPath;
   if(['fade','slide','zoom','blur'].includes(effect))opacity*=p;
   if(effect==='slide')transform=`translateY(${(1-p)*70}px)`;
   if(effect==='zoom')transform=`scale(${.87+.13*p})`;
   if(effect==='pan')transform=`scale(1.08) translateX(${(clamp((time-start)/Math.max(.1,duration-start))-.5)*50}px)`;
   if(effect==='blur')filter+=` blur(${(1-p)*18}px)`;
   if(effect==='wipe'||effect==='typewriter')clip=`inset(0 ${(1-(effect==='typewriter'?raw:p))*100}% 0 0)`;
   if(effect==='strobe'&&visible&&raw<1)opacity*=Math.floor(raw*6)%2===0?1:.25;
   if(element.dataset.out!==undefined){const out=number(element.dataset.out,duration,0,duration/scale)*scale,exit=ease((time-out)/span,element.dataset.ease);opacity*=1-exit;if(effect==='blur')filter+=` blur(${exit*18}px)`;}
   element.style.setProperty('opacity',String(opacity),'important');element.style.setProperty('transform',(transform+' '+(base.transform==='none'?'':base.transform)).trim()||'none','important');element.style.setProperty('filter',filter.trim()||'none','important');element.style.setProperty('clip-path',clip||'none','important');
  }
 }
 function render(doc,motion,time){
  const frames=[...doc.querySelectorAll('[data-h3-scene]')],durations=motion.durations;let start=0,index=durations.length-1;
  for(let i=0;i<durations.length;i++){if(time<start+durations[i]||i===durations.length-1){index=i;break;}start+=durations[i];}
  const local=Math.max(0,time-start),span=Math.min(.45,durations[index]/3),progress=ease(local/span,'smooth');
  frames.forEach((frame,i)=>{
   const current=i===index,previous=i===index-1&&local<span&&motion.transition!=='cut';
   frame.style.visibility=current||previous?'visible':'hidden';frame.style.zIndex=String(i);frame.style.opacity=current?(index&&motion.transition!=='cut'?String(progress):'1'):previous?String(1-progress):'0';frame.style.transform='none';frame.style.clipPath='none';
   if(current&&index){if(motion.transition==='slide')frame.style.transform=`translateX(${(1-progress)*100}%)`;if(motion.transition==='zoom')frame.style.transform=`scale(${1.12-.12*progress})`;if(motion.transition==='wipe'){frame.style.opacity='1';frame.style.clipPath=`inset(0 ${(1-progress)*100}% 0 0)`;}}
   if(current&&frame.contentDocument)apply(frame.contentDocument,local,durations[i]);
   if(previous&&frame.contentDocument)apply(frame.contentDocument,durations[i]-.001,durations[i]);
  });return {index,time:local};
 }
 globalThis.H3Motion={apply,render,effects,freeze};
})();

/* Trusted timeline interpreter. Generated HTML never supplies JavaScript. */
(()=>{
 const states=new WeakMap(),effects=['fade','slide','zoom','pan','blur','wipe','strobe','typewriter','appear'];
 const clamp=v=>Math.max(0,Math.min(1,v));
 const layouts={full:[1,1],columns2:[2,1],rows2:[1,2],columns3:[3,1],rows3:[1,3],pip:[2,1],grid2x2:[2,2],grid3x2:[3,2],grid2x3:[2,3]};
 const panelCount=layout=>{const [columns,rows]=layouts[layout]||layouts.full;return columns*rows;};
 function number(value,fallback,low=0,high=600){const n=Number(value);return value!==undefined&&value!==''&&Number.isFinite(n)?Math.max(low,Math.min(high,n)):fallback;}
 function freeze(doc){for(const element of doc.querySelectorAll('*')){element.style?.setProperty('animation','none','important');element.style?.setProperty('transition','none','important');}}
 function panelTimes(doc,options,duration){
  const count=panelCount(options.layout);if(count===1)return [];
  const ids='123456'.slice(0,count),order=typeof options.panel_order==='string'&&options.panel_order.split('').sort().join('')===ids?options.panel_order:ids,interval=Math.min(number(options.panel_interval,.8,.2,30),Math.max(0,duration*.9-Math.min(.65,duration*.15))/Math.max(1,count-1));
  const panels=[...doc.querySelectorAll('[data-panel]')].filter(e=>/^[1-6]$/.test(e.dataset.panel)&&Number(e.dataset.panel)<=count);
  for(const panel of panels){const sequence=options.panel_appearance==='sequence',start=sequence?order.indexOf(panel.dataset.panel)*interval:0;panel.dataset.start=String(start);panel.dataset.duration=String(Math.min(.65,duration*.15));delete panel.dataset.out;panel.dataset.motion=sequence&&['fade','slide','zoom','blur','wipe'].includes(panel.dataset.motion)?panel.dataset.motion:sequence?'fade':'appear';for(const child of panel.querySelectorAll('[data-motion]'))if(number(child.dataset.start,0)<start)child.dataset.start=String(start);}
  return panels;
 }
 function timingScale(nodes,duration){const latest=Math.max(0,...nodes.filter(e=>e.dataset.motion!=='pan').map(e=>number(e.dataset.start,0)+number(e.dataset.duration,.65,.05,30)));return latest>duration*.9?duration*.9/latest:1;}
 function animationNodes(doc){const nodes=[...doc.querySelectorAll('[data-motion]')],root=e=>e.dataset.panel!==undefined||e.dataset.overlay!==undefined;return [...nodes.filter(root),...nodes.filter(e=>!root(e))].slice(0,160);}
 function screenOverlays(doc){
  // Older scenes used an animated sibling without an explicit overlay marker.
  const candidates=[...doc.querySelectorAll('[data-overlay],[data-motion]')].filter(e=>e.dataset.panel===undefined&&!e.closest?.('[data-panel]')&&!e.querySelector?.('[data-panel]'));
  return candidates.filter(e=>!candidates.some(parent=>parent!==e&&parent.contains?.(e)));
 }
 function videoTracks(documents,motion){
  const options=motion.options||{},delayed=options.video_start==='panel'&&options.layout&&options.layout!=='full',allowed=new Set((motion.videos||(motion.video?[motion.video]:[])).map(v=>v.asset_id)),tracks=new Map(),targets=[];let offset=0;
  documents.forEach((doc,index)=>{
   const duration=motion.durations[index];if(delayed)for(const panel of panelTimes(doc,options,duration))doc.body.append(panel);
   const scale=timingScale(animationNodes(doc),duration);
   for(const slot of doc.querySelectorAll('div[data-video-asset-id],[data-h3-video]')){
    const id=slot.dataset.videoAssetId||slot.dataset.h3Video;if(!allowed.has(id))continue;const panel=slot.closest('[data-panel]');if(delayed&&!panel)continue;
    const key=delayed?JSON.stringify([id,panel.dataset.panel]):id,start=delayed?offset+number(panel.dataset.start,0)*scale:0;
    if(!tracks.has(key)||tracks.get(key).start>start)tracks.set(key,{key,asset_id:id,start});
    if(slot.dataset.h3Video)targets.push([slot,key]);
   }
   offset+=duration;
  });
  for(const [node,key] of targets){node.dataset.h3VideoChannel=key;node.dataset.h3VideoStart=String(tracks.get(key).start);}
  return [...tracks.values()];
 }
 function screen(doc,options={},duration=30){
  const layout=options.layout||'full',count=panelCount(layout);if(count===1)return;
  const width=doc.defaultView.innerWidth,height=doc.defaultView.innerHeight;
  const overlays=screenOverlays(doc),panels=panelTimes(doc,options,duration);
  doc.body.style.setProperty('position','relative','important');doc.body.style.setProperty('overflow','hidden','important');
  for(const panel of panels){
   const index=Number(panel.dataset.panel)-1;doc.body.append(panel);
   let x=0,y=0,w=width,h=height;
   if(layout!=='pip'){const [columns,rows]=layouts[layout];w=width/columns;h=height/rows;x=(index%columns)*w;y=Math.floor(index/columns)*h;}
   if(layout==='pip'&&index===1){w=width*.32;h=height*.32;x=width-w-width*.03;y=height-h-height*.03;}
   const styles={position:'absolute',left:x+'px',top:y+'px',right:'auto',bottom:'auto',width:w+'px',height:h+'px','min-width':'0','min-height':'0','max-width':'none','max-height':'none',margin:'0','box-sizing':'border-box',overflow:'hidden',transform:'none',translate:'none',rotate:'none',scale:'none',opacity:'1','z-index':String(index+1)};
   for(const [key,value] of Object.entries(styles))panel.style.setProperty(key,value,'important');
  }
  for(const [index,overlay] of overlays.entries()){
   doc.body.append(overlay);overlay.dataset.overlay='global';
   const styles={position:'absolute',left:'0px',top:'0px',right:'auto',bottom:'auto',width:width+'px',height:height+'px','min-width':'0','min-height':'0','max-width':'none','max-height':'none',margin:'0','box-sizing':'border-box',overflow:'hidden','z-index':String(count+1+index)};
   // A shared title is transparent over the clips. An opaque closing card is explicit.
   if(overlay.dataset.overlayBackground!=='opaque')styles.background='transparent';
   for(const [key,value] of Object.entries(styles))overlay.style.setProperty(key,value,'important');
  }
  for(const child of [...doc.body.children])if(!panels.includes(child)&&!overlays.includes(child)&&child.tagName!=='STYLE')child.style.setProperty('display','none','important');
  states.delete(doc);
 }
 function ease(t,kind){t=clamp(t);return kind==='linear'?t:kind==='snap'?1-Math.pow(1-t,4):t*t*(3-2*t);}
 function prepare(doc){
  if(states.has(doc))return states.get(doc);
  const entries=animationNodes(doc).map(element=>{
   const css=doc.defaultView.getComputedStyle(element),base={opacity:css.opacity,transform:css.transform,filter:css.filter,clipPath:css.clipPath};
   return {element,base,effect:effects.includes(element.dataset.motion)?element.dataset.motion:'fade'};
  });states.set(doc,entries);return entries;
 }
 function apply(doc,time,duration){
  const entries=prepare(doc);
  // Compress only overlong choreography; preserve its ordering and layout.
  // The last entrance finishes with a short readable hold before the cut.
  const scale=timingScale(entries.map(e=>e.element),duration);
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
 globalThis.H3Motion={apply,render,effects,freeze,screen,videoTracks,panelCount};
})();

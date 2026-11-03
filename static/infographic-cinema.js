/* One deterministic camera clock; full-frame blends without a covering veil. */
(()=>{
 'use strict';
 const cache=new WeakMap(),stacks=new WeakMap(),clamp=(x,a,b)=>Math.max(a,Math.min(b,x));
 const smooth=x=>{x=clamp(x,0,1);return x*x*x*(10+x*(-15+6*x));};
 function curve(keys,t){
  if(t<=keys[0][0])return keys[0][1];if(t>=keys.at(-1)[0])return keys.at(-1)[1];
  const slopes=keys.slice(1).map((p,i)=>(p[1]-keys[i][1])/(p[0]-keys[i][0]));
  const tangent=i=>i===0?slopes[0]:i===keys.length-1?slopes.at(-1):slopes[i-1]*slopes[i]<=0?0:2/(1/slopes[i-1]+1/slopes[i]);
  const i=keys.findIndex((p,i)=>i&&p[0]>t)-1,a=keys[i],b=keys[i+1],h=b[0]-a[0],u=(t-a[0])/h;
  return (2*u**3-3*u*u+1)*a[1]+(u**3-2*u*u+u)*h*tangent(i)+(-2*u**3+3*u*u)*b[1]+(u**3-u*u)*h*tangent(i+1);
 }
 function cameraAt(durations,time){
  const total=durations.reduce((a,b)=>a+b,0),t=clamp(time,0,total),keys=[[0,-.07]];let end=0;
  for(let i=0;i<durations.length-1;i++){
   end+=durations[i];const span=Math.min(1.15,durations[i]*.24,durations[i+1]*.24);
   keys.push([end-span,i+.12],[end,i+.5],[end+span,i+.88]);
  }
  keys.push([total,durations.length-1+.07]);
  return {x:curve(keys,t),zoom:1.025+.025*Math.sin(Math.PI*t/total)**2,time:t};
 }
 function large(element,frame,ratio=.7){const r=element.getBoundingClientRect();return r.width>=frame.width*ratio&&r.height>=frame.height*ratio;}
 function stack(doc){
  if(stacks.has(doc))return;
  const view=doc.defaultView,planes=[...doc.querySelectorAll('[data-depth]')].filter(e=>!e.parentElement?.closest('[data-depth]')),original=[];
  const scopes=[...doc.querySelectorAll('[data-panel]')];
  for(const scope of scopes.length?scopes:[doc.body]){
   const bounds=scope.getBoundingClientRect(),within=planes.filter(p=>scope.contains(p));
   const imagePlanes=within.filter(p=>p.dataset.layerRole==='background-image'||[...p.querySelectorAll('img[data-asset-id],img[data-h3-asset]')].some(i=>large(i,bounds)));
   if(!imagePlanes.length)continue;
   const backdrop=p=>p.dataset.layerRole==='background-vector'||(!p.querySelector('img,text,foreignObject,h1,h2,h3,p,table')&&[...p.querySelectorAll('svg')].some(svg=>{
    if(!large(svg,bounds))return false;
    const box=svg.viewBox.baseVal;
    return [...svg.querySelectorAll('rect')].some(r=>{const s=view.getComputedStyle(r),b=r.getBBox();return b.width>=box.width*.7&&b.height>=box.height*.7&&s.fill!=='none'&&s.fill!=='transparent'&&Number(s.opacity)*Number(s.fillOpacity)>.85;});
   }));
   for(const p of within){
    original.push({element:p,z:p.style.getPropertyValue('z-index'),priority:p.style.getPropertyPriority('z-index'),position:p.style.getPropertyValue('position')});
    const rank=Number(p.dataset.depth)===0?40:imagePlanes.includes(p)?10:backdrop(p)?0:Math.round(20+Number(p.dataset.depth)*5);
    if(view.getComputedStyle(p).position==='static')p.style.position='relative';
    p.style.setProperty('z-index',String(rank),'important');
   }
  }
  stacks.set(doc,original);
 }
 function depth(doc,travel,zoom){
  stack(doc);
  if(!cache.has(doc))cache.set(doc,[...doc.querySelectorAll('[data-depth]')].slice(0,96).filter(e=>!e.parentElement?.closest('[data-depth]')).map(element=>({element,base:doc.defaultView.getComputedStyle(element).transform,inline:element.style.getPropertyValue('transform'),priority:element.style.getPropertyPriority('transform'),depth:Number(element.dataset.depth)})).filter(e=>Number.isFinite(e.depth)&&e.depth>=0&&e.depth<=2));
  const width=doc.body.clientWidth||1280;
  for(const item of cache.get(doc)){
   // Text HUD stays fixed; only the visual planes drift within their overscan.
   const shift=item.depth===0?0:(1-item.depth)*clamp(travel,-.6,.6)*width*.04,scale=item.depth===0?1:1.06+(zoom-1)*(.6+item.depth*.2);
   item.element.style.setProperty('transform',`translateX(${shift}px) scale(${scale}) ${item.base==='none'?'':item.base}`,'important');
   item.element.style.setProperty('transform-origin','50% 50%','important');
  }
 }
 function restoreDepth(doc){for(const item of cache.get(doc)||[]){if(item.inline)item.element.style.setProperty('transform',item.inline,item.priority);else item.element.style.removeProperty('transform');}}
 function blendAt(durations,time,seconds=.9){
  let end=0,index=durations.length-1;
  for(let i=0;i<durations.length;i++){
   const start=end;end+=durations[i];if(time>=start&&time<end)index=i;
   if(i===durations.length-1)continue;
   const half=Math.min(clamp(Number(seconds)||.9,.1,2)/2,durations[i]*.24,durations[i+1]*.24);
   if(time>=end-half&&time<=end+half)return {from:i,to:i+1,alpha:smooth((time-end+half)/(2*half))};
  }
  return {from:index,to:index,alpha:1};
 }
 function render(host,motion,time){
  const frames=[...host.querySelectorAll('[data-h3-scene]')],durations=motion.durations,camera=cameraAt(durations,time),blend=blendAt(durations,camera.time,motion.options?.transition_seconds);let start=0,index=durations.length-1,local=durations.at(-1);
  for(const old of host.querySelectorAll('[data-h3-camera-occluder]'))old.remove();
  for(let i=0;i<durations.length;i++){
   if(time>=start&&time<start+durations[i]){index=i;local=time-start;}
   const frame=frames[i];if(frame){
    const visible=i===blend.from||i===blend.to;
    frame.style.visibility=visible?'visible':'hidden';
    // Keep the lower frame opaque: fading both would expose the stage color.
    frame.style.opacity=visible?String(i===blend.to&&blend.to!==blend.from?blend.alpha:1):'0';frame.style.zIndex=String(i);frame.style.clipPath='none';frame.style.transformOrigin='center';frame.style.transform='none';frame.style.filter='none';frame.style.boxShadow='none';
    if(visible&&frame.contentDocument){globalThis.H3Motion.apply(frame.contentDocument,clamp(time-start,0,durations[i]),durations[i],motion.options||{});depth(frame.contentDocument,camera.x-i,camera.zoom);}
    else if(frame.contentDocument){stack(frame.contentDocument);restoreDepth(frame.contentDocument);}
   }
   start+=durations[i];
  }
  return {index,time:local,camera,blend};
 }
 function reset(host){
  for(const old of host.querySelectorAll('[data-h3-camera-occluder]'))old.remove();
  for(const frame of host.querySelectorAll('[data-h3-scene]'))if(frame.contentDocument){
   const doc=frame.contentDocument;
   restoreDepth(doc);
   for(const item of stacks.get(doc)||[]){if(item.z)item.element.style.setProperty('z-index',item.z,item.priority);else item.element.style.removeProperty('z-index');if(item.position)item.element.style.position=item.position;else item.element.style.removeProperty('position');}
   stacks.delete(doc);
  }
 }
 globalThis.H3Cinema={render,cameraAt,blendAt,reset};
})();

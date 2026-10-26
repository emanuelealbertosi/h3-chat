// Used only on temporary export documents, never on the live preview.
export function staticSnapshot(doc){
 for(const animation of doc.getAnimations()){
  const timing=animation.effect?.getComputedTiming();if(!timing)continue;
  const end=Number.isFinite(timing.endTime)?timing.endTime:(Number(timing.delay)||0)+(Number(timing.duration)||1000)*.5;
  animation.pause();animation.currentTime=Math.max(0,end-.01);
 }
 for(const svg of doc.querySelectorAll('svg')){
  if(!svg.querySelector('animate,animateTransform,animateMotion,set'))continue;
  const seconds=value=>{const m=/^([\d.]+)(ms|s)?$/.exec(value||'');return m?Number(m[1])/(m[2]==='ms'?1000:1):0;};
  const end=Math.min(60,Math.max(1,...[...svg.querySelectorAll('animate,animateTransform,animateMotion,set')].map(e=>seconds(e.getAttribute('begin'))+seconds(e.getAttribute('dur')))));
  try{svg.pauseAnimations();svg.setCurrentTime(Math.max(0,end-.001));}catch{}
 }
 // Materialize SVG animated geometry before the export sanitizer removes SMIL.
 for(const e of doc.querySelectorAll('svg,svg *'))for(const name of e.getAttributeNames()){
  const property=({'stroke-width':'strokeWidth','stroke-dashoffset':'strokeDashoffset'})[name]||name;
  const animated=e[property];if(!animated||typeof animated!=='object'||!('animVal' in animated))continue;
  const v=animated.animVal;
  if(typeof v==='number'||typeof v==='string')e.setAttribute(name,String(v));
  else if(typeof v?.valueAsString==='string')e.setAttribute(name,v.valueAsString);
  else if(name==='points'&&v?.numberOfItems)e.setAttribute(name,Array.from({length:v.numberOfItems},(_,i)=>{const p=v.getItem(i);return p.x+','+p.y;}).join(' '));
 }
}

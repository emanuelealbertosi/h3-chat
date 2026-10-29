import {parseColor,composite,contrastRatio,readableColor,colorHex} from './color-contrast.js';

function surfaces(element,doc){
 let colors=[[255,255,255,1]],opacity=1,unknown=false;
 const parents=[];for(let p=element;p;p=p.parentElement)parents.unshift(p);
 for(const parent of parents){
  const css=doc.defaultView.getComputedStyle(parent),base=parseColor(css.backgroundColor)||[0,0,0,0];
  colors=colors.map(bg=>composite(base,bg));
  // Evaluate every gradient stop instead of skipping all gradient-backed text.
  // A mixed light/dark surface may need a local text backing for readability.
  if(css.backgroundImage!=='none'&&!css.backgroundClip.includes('text')){
   const stops=[...css.backgroundImage.matchAll(/rgba?\([^)]*\)|#[\da-f]{3,8}\b/gi)].map(m=>parseColor(m[0])).filter(Boolean);
   if(stops.length)colors=stops.flatMap(stop=>colors.map(bg=>composite(stop,bg))).slice(0,32);
   if(css.backgroundImage.includes('url(')||!stops.length)unknown=true;
  }
  if(!parent.getAnimations().length)opacity*=Number(css.opacity);
 }
 if(element.namespaceURI==='http://www.w3.org/2000/svg'){
  const r=element.getBoundingClientRect(),stack=doc.elementsFromPoint(r.x+r.width/2,r.y+r.height/2),index=stack.indexOf(element);
  const shape=stack.slice(index+1).find(e=>e!==element&&e.namespaceURI===element.namespaceURI&&['rect','circle','ellipse','path','polygon'].includes(e.localName));
  const fill=shape&&parseColor(doc.defaultView.getComputedStyle(shape).fill);if(fill)colors=colors.map(bg=>composite(fill,bg));
 }
 return {colors,opacity,unknown};
}

export function readableText(doc,tone=doc.documentElement.dataset.h3TextTone||'auto'){
 const forced=['light','dark'].includes(tone);
 for(const element of doc.body.querySelectorAll('*')){
  if(element.closest('style,math,.katex-mathml')||![...element.childNodes].some(n=>n.nodeType===3&&n.textContent.trim()))continue;
  const svg=element.namespaceURI==='http://www.w3.org/2000/svg';if(svg&&element.localName!=='text'&&element.localName!=='tspan')continue;
  const {colors,opacity,unknown}=surfaces(element,doc),css=doc.defaultView.getComputedStyle(element),property=svg?'fill':'color';
  const original=parseColor(css.getPropertyValue(property));if(!original)continue;
  let gradientInk=null;for(let p=element;p&&p!==doc.body;p=p.parentElement){const s=doc.defaultView.getComputedStyle(p);if(s.backgroundClip.includes('text')&&s.backgroundImage!=='none'){gradientInk=p;break;}}
  // A clipped gradient is the ink, not the paper. Replacing transparent text
  // with a contrast fallback paints over metallic/gradient lettering.
  if(gradientInk&&!forced&&original[3]===0)continue;
  if(gradientInk&&forced)gradientInk.style.setProperty('background-image','none','important');
  let chosen=forced?(tone==='light'?[248,250,252,1]:[23,36,43,1]):original;
  const score=color=>Math.min(...colors.map(bg=>contrastRatio(color,bg,opacity)));
  const bad=score(chosen)<4.5;
  if(!forced&&!bad)continue;
  if(!forced){
   if(unknown)continue;
   if(colors.every(c=>colorHex(c)===colorHex(colors[0])))chosen=readableColor(original,colors[0],opacity);
   else chosen=score([0,0,0,1])>=score([255,255,255,1])?[0,0,0,1]:[255,255,255,1];
  }
  element.style.setProperty(property,colorHex(chosen),'important');element.dataset.contrastAdjusted='true';
  if(score(chosen)<4.5||(forced&&unknown)){
   const backing=contrastRatio(chosen,[0,0,0,1])>contrastRatio(chosen,[255,255,255,1])?'#17242b':'#fffaf0';
   if(svg){element.style.setProperty('stroke',backing,'important');element.style.setProperty('stroke-width','5px','important');element.style.setProperty('paint-order','stroke fill','important');element.style.setProperty('stroke-linejoin','round','important');}
   else{element.style.setProperty('background-color',backing,'important');element.style.setProperty('box-decoration-break','clone');}
   element.dataset.contrastSurface='true';
  }
 }
}

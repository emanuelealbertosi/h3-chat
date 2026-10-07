import {parseColor,composite,contrastRatio,readableColor,colorHex} from './color-contrast.js';

export function readableText(doc){
  for(const element of doc.body.querySelectorAll('*')){
    if(element.closest('svg,style,math,.katex-mathml')||![...element.childNodes].some(n=>n.nodeType===3&&n.textContent.trim()))continue;
    const layers=[];let opacity=1,complex=false;
    for(let parent=element;parent;parent=parent.parentElement){const css=doc.defaultView.getComputedStyle(parent);if(css.backgroundImage!=='none'){complex=true;break;}layers.push(parseColor(css.backgroundColor)||[0,0,0,0]);opacity*=Number(css.opacity);}
    if(complex)continue;
    const background=layers.reverse().reduce((bg,layer)=>composite(layer,bg),[255,255,255,1]),foreground=parseColor(doc.defaultView.getComputedStyle(element).color);
    if(foreground&&contrastRatio(foreground,background,opacity)<4.5){element.style.setProperty('color',colorHex(readableColor(foreground,background,opacity)),'important');element.dataset.contrastAdjusted='true';}
  }
}

import Chart from 'chart.js/auto';
import {parseColor,composite,contrastRatio,readableColor,colorHex} from './color-contrast.js';

export function effectiveBackground(element,frame){
  const layers=[];for(let el=element;el;el=el.parentElement){layers.push(parseColor(getComputedStyle(el).backgroundColor)||[0,0,0,0]);if(el===frame)break;}
  return layers.reverse().reduce((bg,layer)=>composite(layer,bg),[255,255,255,1]);
}
function opacity(element,frame){let value=1;for(let el=element;el;el=el.parentElement){value*=Number(getComputedStyle(el).opacity);if(el===frame)break;}return value;}
function ensureColor(element,background,frame,property='color',minimum=4.5){
  const foreground=parseColor(getComputedStyle(element)[property]);if(!foreground)return false;
  let alpha=opacity(element,frame);if(contrastRatio(foreground,background,alpha)>=minimum)return false;
  let chosen=readableColor(foreground,background,alpha,minimum);
  if(contrastRatio(chosen,background,alpha)<minimum){element.style.opacity='1';alpha=opacity(element,frame);chosen=readableColor(foreground,background,alpha,minimum);}
  element.style.setProperty(property,colorHex(chosen),'important');element.dataset.contrastAdjusted='true';return true;
}
export function repairSlideContrast(frame){
  // Traverse parents first: inherited text and syntax tokens can then keep their
  // colors where they already have enough contrast on their actual surface.
  for(const el of [frame,...frame.querySelectorAll('*')]){
    if(el.closest('.no-export,svg,math,.katex-mathml')||getComputedStyle(el).display==='none')continue;
    ensureColor(el,effectiveBackground(el,frame),frame);
  }
  for(const svg of frame.querySelectorAll('.diagram svg')){
    const background=effectiveBackground(svg,frame);
    for(const text of svg.querySelectorAll('text,tspan')){
      const group=text.closest('g.node,g.cluster,g.edgeLabel'),shape=group?.querySelector('rect,polygon,circle,ellipse');
      const fill=shape&&parseColor(getComputedStyle(shape).fill);
      ensureColor(text,fill?composite(fill,background):background,frame,'fill');
    }
    for(const path of svg.querySelectorAll('path.flowchart-link,marker path')){
      ensureColor(path,background,frame,'stroke',3);
      if(path.closest('marker'))ensureColor(path,background,frame,'fill',3);
    }
  }
  for(const canvas of frame.querySelectorAll('canvas')){
    const chart=Chart.getChart(canvas);if(!chart)continue;
    const bg=effectiveBackground(canvas,frame),raw=parseColor(Chart.defaults.color)||[102,102,102,1],foreground=colorHex(readableColor(raw,bg));
    chart.options.color=foreground;
    if(chart.options.plugins.legend)chart.options.plugins.legend.labels.color=foreground;
    if(chart.options.plugins.title)chart.options.plugins.title.color=foreground;
    for(const axis of Object.values(chart.options.scales||{})){axis.ticks.color=foreground;axis.title.color=foreground;}
    chart.$h3Contrast={foreground,background:colorHex(bg)};chart.update('none');
  }
  frame.dataset.contrastChecked='true';
}

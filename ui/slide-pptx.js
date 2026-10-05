import pptxgen from 'pptxgenjs';
import JSZip from 'jszip';
import Chart from 'chart.js/auto';
import {toPng} from 'html-to-image';
import {saveBlob} from './render.js';
import {chartData} from './pptx-chart-data.js';
import {parseColor,colorHex,composite} from './color-contrast.js';

const NS='http://schemas.openxmlformats.org/drawingml/2006/chart';
function color(raw){
  const values=parseColor(raw);if(!values)return {color:'FFFFFF',transparency:100};
  return {color:colorHex(values).slice(1).toUpperCase(),transparency:Math.round((1-values[3])*100)};
}
function box(element,frame){const r=element.getBoundingClientRect(),f=frame.getBoundingClientRect();return {x:(r.left-f.left)/96,y:(r.top-f.top)/96,w:r.width/96,h:r.height/96};}
function font(style){return /Georgia/i.test(style.fontFamily)?'Georgia':/Segoe UI/i.test(style.fontFamily)?'Segoe UI':/Comic Sans/i.test(style.fontFamily)?'Comic Sans MS':/Consolas|monospace|Courier/i.test(style.fontFamily)?'Courier New':/Cormorant|Cambria|serif/i.test(style.fontFamily)&&!/sans-serif/i.test(style.fontFamily)?'Cambria':'Arial';}
function addTextLines(slide,frame){
  const walker=document.createTreeWalker(frame,NodeFilter.SHOW_TEXT),lines=new Map();let node;
  while(node=walker.nextNode()){
    const parent=node.parentElement;if(parent.closest('.no-export,.katex,svg,canvas')||!node.data.trim())continue;
    const style=getComputedStyle(parent);if(style.display==='none'||style.visibility==='hidden')continue;
    const range=document.createRange();
    for(const part of node.data.matchAll(/\S+\s*|\s+/g)){
      range.setStart(node,part.index);range.setEnd(node,part.index+part[0].length);const rect=range.getBoundingClientRect();if(!rect.width||!rect.height)continue;
      const f=frame.getBoundingClientRect(),x=(rect.left-f.left)/96,y=(rect.top-f.top)/96,w=rect.width/96,h=rect.height/96;
      const block=parent.closest('p,li,pre,h1,h2,h3,th,td,.slide-heading,.slide-continuation-title,.h3-slide-footer,.h3-slide-kicker')||parent;
      let row=[...lines.values()].find(l=>l.block===block&&Math.abs(l.y-y)<.025&&Math.abs(l.x+l.w-x)<.08);
      if(!row){row={block,x,y,w:0,h,runs:[],fontSize:parseFloat(style.fontSize)*.75};lines.set(lines.size,row);}
      row.x=Math.min(row.x,x);row.w=Math.max(row.w,x+w-row.x);row.h=Math.max(row.h,h);
      row.runs.push({text:part[0].replace(/\n/g,' '),options:{fontFace:font(style),fontSize:parseFloat(style.fontSize)*.75,color:color(style.color).color,bold:Number(style.fontWeight)>=600,italic:style.fontStyle==='italic'}});
    }
  }
  const listed=new Set();
  for(const row of lines.values()){
    let bullet;
    if(row.block.tagName==='LI'&&!listed.has(row.block)){
      listed.add(row.block);const list=row.block.parentElement,ordered=list.tagName==='OL',number=Number(list.getAttribute('start')||1)+[...list.children].indexOf(row.block);
      bullet=ordered?{type:'number',numberType:'arabicPeriod',numberStartAt:number,indent:16.56}:{indent:16.56};row.x-=.23;row.w+=.23;
    }
    const right=(row.block.getBoundingClientRect().right-frame.getBoundingClientRect().left)/96;
    slide.addText(row.runs,{x:row.x,y:row.y,w:Math.max(.05,row.w,Math.min(row.w*1.08+.12,right-row.x)),h:Math.max(row.h+.03,.12),margin:0,bullet,wrap:false,breakLine:false,vertAnchor:'top',fit:'shrink',paraSpaceAfterPt:0});
  }
}
function chart(slide,pres,canvas,frame){
  const instance=Chart.getChart(canvas);if(!instance)return false;const cfg=instance.config,series=cfg.data.datasets;
  const type=cfg.type;if(!['line','bar','scatter','pie','doughnut'].includes(type))return false;
  const data=chartData(type,series,cfg.data.labels||[]);
  const contrast=instance.$h3Contrast||{foreground:'#53636a',background:'#ffffff'},foreground=color(contrast.foreground).color,background=color(contrast.background).color;
  const grid=colorHex(composite([...parseColor(contrast.foreground).slice(0,3),.18],parseColor(contrast.background))).slice(1).toUpperCase();
  const options={...box(canvas,frame),showLegend:series.length>1,legendPos:'b',showTitle:!!cfg.options.plugins?.title?.text,title:String(cfg.options.plugins?.title?.text||''),titleFontSize:16,
    chartColors:['087F8C','6850A1','B84944','B5964D','4375A0'],showValue:['pie','doughnut'].includes(type),showPercent:['pie','doughnut'].includes(type),catAxisLabelFontSize:11,valAxisLabelFontSize:11,
    catAxisLabelColor:foreground,valAxisLabelColor:foreground,legendColor:foreground,titleColor:foreground,valGridLine:{color:grid,size:.5},catGridLine:{style:'none'},showBorder:false,showCatName:false,
    chartArea:{fill:{color:background}},plotArea:{fill:{color:background}}};
  if(type==='bar')options.barDir='col';
  if(type==='scatter')Object.assign(options,{lineSize:0,lineDataSymbol:'circle',lineDataSymbolSize:6});
  slide.addChart(pres.ChartType[type],data,options);return true;
}
async function repairChartAxes(blob){
  const zip=await JSZip.loadAsync(blob);let changed=false;
  for(const name of Object.keys(zip.files).filter(n=>/^ppt\/charts\/chart\d+\.xml$/.test(n))){
    const xml=new DOMParser().parseFromString(await zip.file(name).async('string'),'application/xml');
    const declared=new Set();for(const tag of ['catAx','valAx','serAx','dateAx'])for(const axis of xml.getElementsByTagNameNS(NS,tag))for(const id of axis.getElementsByTagNameNS(NS,'axId'))declared.add(id.getAttribute('val'));
    for(const id of [...xml.getElementsByTagNameNS(NS,'axId')])if(id.parentElement.localName.endsWith('Chart')&&!declared.has(id.getAttribute('val'))){id.remove();changed=true;}
    if(changed)zip.file(name,new XMLSerializer().serializeToString(xml));
  }
  return changed?zip.generateAsync({type:'blob',compression:'DEFLATE',mimeType:'application/vnd.openxmlformats-officedocument.presentationml.presentation'}):blob;
}
async function rasterGraphic(element){
  const rect=element.getBoundingClientRect();if(!rect.width||!rect.height)throw Error('Elemento grafico senza dimensioni.');
  // Inline math has zero clientWidth; a root SVG cannot be captured reliably
  // through foreignObject. An HTML wrapper gives both a real raster viewport.
  const wrapper=document.createElement('div');wrapper.style.cssText=`display:inline-block;width:${rect.width}px;height:${rect.height}px;vertical-align:top;`;
  element.before(wrapper);wrapper.append(element);
  try{return await toPng(wrapper,{width:rect.width,height:rect.height,pixelRatio:3,backgroundColor:'transparent',style:{margin:'0',transform:'none'},filter:n=>!n.classList?.contains('no-export')});}
  finally{wrapper.replaceWith(element);}
}
async function rasterDecoration(element){
  const bounds=element.getBoundingClientRect(),paint=element.cloneNode(false),style=getComputedStyle(element);
  paint.removeAttribute('id');paint.removeAttribute('class');
  for(const property of style)paint.style.setProperty(property,style.getPropertyValue(property));
  paint.style.position='relative';paint.style.inset='auto';paint.style.margin='0';paint.style.transform='none';paint.style.translate='none';paint.style.width=bounds.width+'px';paint.style.height=bounds.height+'px';
  const host=document.createElement('div');host.style.cssText='position:fixed;left:-30000px;top:0';host.append(paint);document.body.append(host);
  try{return await toPng(paint,{width:bounds.width,height:bounds.height,pixelRatio:2,backgroundColor:'transparent'});}finally{host.remove();}
}
export async function exportPowerPoint(root,deck,title){
  try{
  const pres=new pptxgen(),height=parseFloat(root.firstElementChild.style.getPropertyValue('--slide-height'));
  pres.defineLayout({name:'H3',width:1280/96,height:height/96});pres.layout='H3';pres.author='H3-Chat';pres.title=title;pres.subject=deck.title;pres.theme={headFontFace:'Cambria',bodyFontFace:'Arial',lang:'it-IT'};
  for(const frame of root.querySelectorAll('.h3-slide-page')){
    const slide=pres.addSlide();slide.background={color:color(getComputedStyle(frame).backgroundColor).color};
    // Preserve every painted HTML surface, including inline code and figure
    // labels: their readable text color depends on that background in the DOM.
    for(const element of frame.querySelectorAll('*')){
      if(element.closest('.no-export,svg,math,.katex')||getComputedStyle(element).display==='none')continue;
      const style=getComputedStyle(element),fill=color(style.backgroundColor),border=parseFloat(style.borderTopWidth)||0;
      if(deck.engine==='llm'&&style.backgroundImage!=='none'){
        const bounds=box(element,frame);if(bounds.w>0&&bounds.h>0)slide.addImage({data:await rasterDecoration(element),...bounds});continue;
      }
      if(fill.transparency===100&&!border)continue;
      const bounds=box(element,frame),line=border?{...color(style.borderTopColor),width:border*.75}:{...fill,transparency:100};if(bounds.w>0&&bounds.h>0)slide.addShape(parseFloat(style.borderRadius)?pres.ShapeType.roundRect:pres.ShapeType.rect,{...bounds,rectRadius:.12,fill:{...fill},line,radius:.12});
    }
    addTextLines(slide,frame);
    for(const element of frame.querySelectorAll('img,svg,.katex-display,.katex:not(.katex-display .katex),canvas')){
      if(element.closest('.no-export')||element.parentElement.closest('.katex,.katex-display'))continue;
      if(element.tagName==='CANVAS'&&chart(slide,pres,element,frame))continue;
      const bounds=box(element,frame),data=await rasterGraphic(element);
      slide.addImage({data,...bounds});
    }
    const page=deck.pages[Number(frame.dataset.page)-1];slide.addNotes([page.notes||'',...(page.sources||[]).map(id=>{const r=deck.references.find(r=>r.id===id);return r?'['+id+'] '+r.label:'';}),'Formule e diagrammi sono elementi grafici; testi, riquadri e grafici dati sono modificabili in PowerPoint.'].filter(Boolean).join('\n'));
  }
  const blob=await repairChartAxes(await pres.write({outputType:'blob',compression:true}));saveBlob(blob,(title||'Presentazione').replace(/[^\p{L}\p{N}\s_-]/gu,'').slice(0,80)+'.pptx');
  }catch(error){console.error('Esportazione PowerPoint:',error.stack);throw error;}
}

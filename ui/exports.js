import {toCanvas,toPng} from 'html-to-image';
import {Document,Packer,Paragraph,TextRun,ImageRun,Table,TableRow,TableCell,WidthType,HeadingLevel,LevelFormat,ShadingType} from 'docx';
import {saveBlob} from './render.js';

const captureOptions={pixelRatio:2,backgroundColor:'#fffefa',filter:n=>!n.classList?.contains('no-export'),style:{margin:'0',maxWidth:'none'}};
const nameOf=title=>(title||'H3-Chat').replace(/[^\p{L}\p{N}\s_-]/gu,'').trim().slice(0,80)||'H3-Chat';
async function waitImages(root){await document.fonts.ready;await Promise.all([...root.querySelectorAll('img')].map(img=>img.decode().catch(()=>{})));}

export async function exportPng(root,title){await waitImages(root);const width=root.clientWidth,height=root.scrollHeight;const c=await toCanvas(root,{...captureOptions,width,height,style:{...captureOptions.style,width:width+'px',height:height+'px',maxHeight:'none',overflow:'visible',flex:'none'}});c.toBlob(b=>saveBlob(b,nameOf(title)+'.png'));}

export async function exportPdf(root,title,token) {
  await waitImages(root);
  const clone=root.cloneNode(true);
  clone.querySelectorAll('.no-export').forEach(n=>n.remove());
  const sourceSvgs=[...root.querySelectorAll('svg')];
  clone.querySelectorAll('svg').forEach((svg,i)=>{
    const sources=[sourceSvgs[i],...sourceSvgs[i].querySelectorAll('*')], targets=[svg,...svg.querySelectorAll('*')];
    targets.forEach((element,j)=>{const style=getComputedStyle(sources[j]);for(const key of ['fill','fill-opacity','stroke','stroke-width','stroke-opacity','stroke-dasharray','color','font-family','font-size','font-weight','text-anchor','dominant-baseline','opacity']){const value=style.getPropertyValue(key);if(value&&!value.includes('url('))element.style.setProperty(key,value);}});
    svg.querySelectorAll('style').forEach(n=>n.remove());
  });
  const sourceCanvases=[...root.querySelectorAll('canvas')];
  clone.querySelectorAll('canvas').forEach((node,i)=>{const img=document.createElement('img');img.src=sourceCanvases[i].toDataURL('image/png');node.replaceWith(img);});
  for(const img of clone.querySelectorAll('img')){if(img.src.startsWith(location.origin+'/media/')){const blob=await fetch(img.src).then(r=>r.blob());img.src=await new Promise(resolve=>{const reader=new FileReader();reader.onload=()=>resolve(reader.result);reader.readAsDataURL(blob);});}}
  const response=await fetch('/api/export/pdf',{method:'POST',headers:{'Content-Type':'application/json','X-H3-Token':token},body:JSON.stringify({title,html:clone.innerHTML})});
  const result=await response.json();if(!response.ok)throw Error(result.error);
  const a=document.createElement('a');a.href=result.url;a.download=nameOf(title)+'.pdf';a.click();return result.url;
}

function inlineRuns(node,inherited={}){
  if(node.nodeType===Node.TEXT_NODE)return [new TextRun({text:node.textContent,...inherited})];
  if(node.nodeType!==Node.ELEMENT_NODE||node.classList.contains('no-export'))return [];
  const style={...inherited};if(['STRONG','B'].includes(node.tagName))style.bold=true;if(['EM','I'].includes(node.tagName))style.italics=true;if(node.tagName==='CODE')style.font='Consolas';
  if(node.tagName==='BR')return [new TextRun({break:1})];
  return [...node.childNodes].flatMap(n=>inlineRuns(n,style));
}

export async function exportDocx(root,title){
  await waitImages(root);
  const children=[];
  async function raster(node){const canvas=await toCanvas(node,captureOptions);const data=await new Promise(r=>canvas.toBlob(r));const width=Math.min(620,canvas.width/2);const height=canvas.height/canvas.width*width;const scale=Math.min(1,850/height);children.push(new Paragraph({children:[new ImageRun({type:'png',data:await data.arrayBuffer(),transformation:{width:width*scale,height:height*scale},altText:{name:title,description:node.textContent.slice(0,300),title}})],spacing:{after:160}}));}
  for(const node of root.children){
    if(node.classList.contains('no-export'))continue;
    if(node.matches('figure,.math-block')||node.querySelector('.katex')){await raster(node);continue;}
    if(node.tagName==='TABLE'){
      const rows=[...node.rows],cols=Math.max(...rows.map(r=>r.cells.length));const widths=Array(cols).fill(Math.floor(9360/cols));widths[cols-1]+=9360-widths.reduce((a,b)=>a+b,0);
      children.push(new Table({width:{size:9360,type:WidthType.DXA},columnWidths:widths,rows:rows.map((r,i)=>new TableRow({tableHeader:i===0,children:[...r.cells].map((c,j)=>new TableCell({width:{size:widths[j],type:WidthType.DXA},shading:i===0?{fill:'EAF0E9',type:ShadingType.CLEAR}:undefined,children:[new Paragraph({children:inlineRuns(c,{bold:i===0}),spacing:{after:80}})]}))}))}));continue;
    }
    if(node.tagName==='PRE'){for(const line of (node.querySelector('code')?.textContent||node.textContent).split('\n'))children.push(new Paragraph({children:[new TextRun({text:line||' ',font:'Consolas',size:18})],spacing:{after:0},shading:{fill:'F1F2ED',type:ShadingType.CLEAR}}));continue;}
    if(['UL','OL'].includes(node.tagName)){for(const li of node.children)children.push(new Paragraph({children:inlineRuns(li),numbering:{reference:node.tagName==='OL'?'numbers':'bullets',level:0},spacing:{after:100}}));continue;}
    const heading=/^H[1-6]$/.test(node.tagName)?HeadingLevel['HEADING_'+node.tagName[1]]:undefined;
    children.push(new Paragraph({children:inlineRuns(node),heading,spacing:{after:160},keepNext:!!heading}));
  }
  const doc=new Document({creator:'H3-Chat',title,styles:{default:{document:{run:{font:'Calibri',size:22},paragraph:{spacing:{line:276}}}}},numbering:{config:[{reference:'bullets',levels:[{level:0,format:LevelFormat.BULLET,text:'\u2022',style:{paragraph:{indent:{left:360,hanging:180}}}}]},{reference:'numbers',levels:[{level:0,format:LevelFormat.DECIMAL,text:'%1.',style:{paragraph:{indent:{left:360,hanging:180}}}}]}]},sections:[{properties:{page:{size:{width:11906,height:16838},margin:{top:1080,bottom:1080,left:1273,right:1273}}},children:children.length?children:[new Paragraph('')]}]});
  const blob=await Packer.toBlob(doc);saveBlob(blob,nameOf(title)+'.docx');return blob;
}

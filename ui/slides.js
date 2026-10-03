import {renderRich,saveBlob} from './render.js';
import hljs from 'highlight.js';
import {exportPdf,exportDocx,exportPng} from './exports.js';
import {layoutSlide} from './slide-layout.js';
import {validateDesign,applyOverride} from './slide-design.js';
import {repairSlideContrast} from './slide-contrast.js';

export const slideFormats={'16:9':720,'4:3':960,'16:10':800,'1:1':1280};
export function readDeck(content){
  if(!content.startsWith('```h3-slides\n'))return null;
  if(content.length>200000||!content.endsWith('\n```'))throw Error('Sorgente slide incompleto o troppo grande.');
  const deck=JSON.parse(content.slice(13,-4));
  if(deck.version!==1||!Object.hasOwn(slideFormats,deck.format)||!Array.isArray(deck.pages)||!deck.pages.length||deck.pages.length>30)throw Error('Presentazione non valida.');
  if(deck.title!==undefined&&(typeof deck.title!=='string'||deck.title.length>150))throw Error('Titolo presentazione non valido.');
  deck.title||='Presentazione';deck.references||=[];
  for(const page of deck.pages){
    if(typeof page.title!=='string'||page.title.length>150||!Array.isArray(page.nodes)||page.nodes.length>40)throw Error('Pagina slide non valida.');
    const groups=new Map([['root',0]]),ids=new Set(['root']);
    for(const node of page.nodes){
      if(typeof node.id!=='string'||! /^[a-zA-Z][a-zA-Z0-9_-]{0,47}$/.test(node.id)||ids.has(node.id)||!groups.has(node.parent)||groups.get(node.parent)>=6||!['group','heading','text','code','image','mermaid','chart'].includes(node.kind)||typeof node.text!=='string'||node.text.length>16000)throw Error('Elemento slide non valido.');
      ids.add(node.id);if(node.kind==='group')groups.set(node.id,groups.get(node.parent)+1);
    }
  }
  validateDesign(deck);return deck;
}
const selections=new Map();
export function transferSlideView(oldId,newId){if(selections.has(oldId))selections.set(newId,selections.get(oldId));}
const observerByTarget=new WeakMap();
function applyStyle(element,style={}){
  element.classList.add('slide-surface-'+(['plain','soft','accent','dark'].includes(style.surface)?style.surface:'plain'));
  if(['columns','row'].includes(style.flow)){
    const weights=Array.isArray(style.columns)&&style.columns.length>0&&style.columns.length<=4&&style.columns.every(x=>typeof x==='number'&&x>=.1&&x<=10)?style.columns:[1,1];
    element.style.display='grid';element.style.gridTemplateColumns=weights.map(x=>x+'fr').join(' ');
  }
  element.style.gap=(Number.isInteger(style.gap)&&style.gap>=0&&style.gap<=48?style.gap:20)+'px';
}

async function pageElement(deck,page,index,media,options,mount){
  const frame=document.createElement('article');frame.className='h3-slide-page slide-theme-'+(deck.theme||'lagoon')+' slide-typography-'+(deck.typography||'modern')+' slide-design-'+(deck.design||'professional');frame.style.setProperty('--slide-height',slideFormats[deck.format]+'px');frame.dataset.page=String(index+1);
  const roots=page.nodes.filter(n=>n.parent==='root');
  if(index===0&&roots.length<=4&&!page.nodes.some(n=>['code','chart','mermaid'].includes(n.kind)))frame.classList.add('slide-cover');
  if(roots.length>=4&&roots[0].kind==='heading'&&roots.slice(1).every(n=>n.kind==='text'&&n.text.length<1800))frame.classList.add('slide-auto-grid');
  const kicker=document.createElement('div');kicker.className='h3-slide-kicker';kicker.textContent=index===0?'Presentazione':`Capitolo ${String(index+1).padStart(2,'0')}`;frame.append(kicker);
  const body=document.createElement('div');body.className='h3-slide-body';frame.append(body);const parents=new Map([['root',body]]);
  mount?.append(frame);
  if(!page.nodes.length){const h=document.createElement('h1');h.textContent=page.title;body.append(h);const p=document.createElement('p');p.className='slide-placeholder';p.textContent=page.status==='writing'?'Il modello sta componendo questa pagina…':'In attesa di composizione…';body.append(p);}
  for(const node of page.nodes){
    const element=document.createElement('div');element.className='h3-slide-node slide-'+node.kind;element.dataset.nodeId=node.id;applyStyle(element,node.style);applyOverride(element,page.overrides?.[node.id]);parents.get(node.parent).append(element);
    if(node.kind==='text'&&node.parent==='root'&&roots.length>=3&&(node.style?.surface||'plain')==='plain')element.classList.add(roots.indexOf(node)%2?'slide-surface-soft':'slide-surface-accent');
    if(node.kind==='group'){parents.set(node.id,element);continue;}
    if(node.kind==='image'){
      const image=media.find(m=>m.id===node.asset_id&&m.mime.startsWith('image/')&&/^(uploads|outputs)\/[\w./-]+\.(png|jpg)$/.test(m.path));
      if(image){const img=document.createElement('img');img.src='/media/'+image.path;img.alt=node.text||image.name;img.decoding='async';element.append(img);}
      else{const placeholder=document.createElement('p');placeholder.className='slide-placeholder';placeholder.textContent=node.asset_id?'Immagine non disponibile':'Immagine in preparazione';element.append(placeholder);}
      if(node.text){const caption=document.createElement('p');caption.className='slide-caption';caption.textContent=node.text;element.append(caption);}
    }else{
      element.classList.add('rich');let text=node.text;
      if(node.kind==='code'){const pre=document.createElement('pre'),code=document.createElement('code');code.textContent=text;code.className='language-'+(/^[\w+-]{1,40}$/.test(node.language)?node.language:'text');if(hljs.getLanguage(node.language))code.innerHTML=hljs.highlight(text,{language:node.language}).value;pre.append(code);element.append(pre);}
      else{if(['chart','mermaid'].includes(node.kind))text='```'+node.kind+'\n'+text+'\n```';await renderRich(element,text,{...options,final:page.status==='ready'});element.querySelectorAll('img').forEach(img=>img.remove());}
      if(node.kind==='heading'&&!element.querySelector('h1,h2,h3'))element.classList.add('slide-title');
    }
  }
  const footer=document.createElement('div');footer.className='h3-slide-footer';
  const sources=(page.sources||[]).map(id=>{const source=(deck.references||[]).find(r=>r.id===id);return source?'['+id+'] '+source.label:'';}).filter(Boolean);
  footer.title=sources.join(' · ');footer.textContent=deck.title.slice(0,80)+((page.sources||[]).length?' · '+page.sources.map(id=>'['+id+']').join(' '):'')+' · '+(index+1)+' / '+deck.pages.length;frame.append(footer);
  repairSlideContrast(frame);return frame;
}
export async function renderSlides(target,value,options={}){
  const deck=readDeck(value.content);if(!deck)return false;
  observerByTarget.get(target)?.disconnect();
  await renderRich(target,'');
  const key=value.id||'draft';let selected=selections.get(key)||{index:deck.active||0,follow:true};
  if(selected.follow)selected.index=deck.active||0;selected.index=Math.max(0,Math.min(deck.pages.length-1,selected.index));selections.set(key,selected);
  target.classList.add('slides-preview');target.innerHTML='';
  const controls=document.createElement('div');controls.className='slides-navigation no-export';
  const prev=document.createElement('button'),next=document.createElement('button'),picker=document.createElement('select'),follow=document.createElement('button');
  prev.textContent='‹';prev.ariaLabel='Slide precedente';next.textContent='›';next.ariaLabel='Slide successiva';picker.ariaLabel='Pagine della presentazione';
  for(const [i,p] of deck.pages.entries()){const option=document.createElement('option');option.value=i;option.textContent=(i+1)+'. '+p.title+(p.status==='ready'?'':' · '+(p.status==='writing'?'in creazione':p.status==='interrupted'?'interrotta':'in attesa'));picker.append(option);}
  picker.value=selected.index;prev.disabled=selected.index===0;next.disabled=selected.index===deck.pages.length-1;follow.textContent=selected.follow?'Segui scrittura ✓':'Segui scrittura';
  const change=index=>{selected.index=index;selected.follow=false;renderSlides(target,value,options);};prev.onclick=()=>change(selected.index-1);next.onclick=()=>change(selected.index+1);picker.onchange=()=>change(Number(picker.value));follow.onclick=()=>{selected.follow=true;renderSlides(target,value,options);};
  controls.append(prev,picker,next,follow);target.append(controls);
  const edit=document.createElement('button');edit.id='slide-edit';edit.textContent=selected.editing?'Termina modifica':'Modifica grafica';edit.disabled=!options.editable||!options.onChange||pageNotReady(deck.pages[selected.index]);
  edit.onclick=()=>{selected.editing=!selected.editing;renderSlides(target,value,options);};controls.append(edit);
  const viewport=document.createElement('div');viewport.className='slides-viewport';target.append(viewport);
  const page=deck.pages[selected.index];const frame=await pageElement(deck,page,selected.index,value.media,options,viewport);
  await document.fonts.ready;await Promise.all([...frame.querySelectorAll('img')].map(img=>img.decode().catch(()=>{})));
  const frames=layoutSlide(frame,page.title);
  for(const f of frames)for(const link of f.querySelectorAll('a.rag-citation')){
    const source=options.sources?.find(s=>'#rag-'+s.citation===link.getAttribute('href'));
    if(source&&options.onCitation)link.onclick=e=>{e.preventDefault();options.onCitation(source,options.sources);};
  }
  const warning=document.createElement('p');warning.className='slide-layout-warning no-export';warning.hidden=frames.length===1;warning.textContent=`Contenuto distribuito in ${frames.length} pagine di continuazione, mantenendo il testo leggibile.`;target.append(warning);
  const resize=()=>{const scale=Math.max(.1,(viewport.clientWidth||600)/1280);let top=0;for(const f of frames){f.style.position='absolute';f.style.top=top+'px';f.style.transform='scale('+scale+')';top+=f.offsetHeight*scale+16;}viewport.style.height=top+'px';};resize();const observer=new ResizeObserver(resize);observer.observe(viewport);observerByTarget.set(target,observer);
  if(selected.editing&&options.editable){const {mountEditor}=await import('./slide-editor.js');mountEditor(target,deck,selected.index,frames,async content=>{await assertLayouts(deck,value.media,options);await options.onChange(content);},selected);}
  const notes=document.createElement('details');notes.className='slide-notes no-export';const summary=document.createElement('summary');summary.textContent='Note e fonti della slide';notes.append(summary);
  const text=document.createElement('p');text.textContent=page.notes||'Nessuna nota.';notes.append(text);
  for(const id of page.sources||[]){const ref=(deck.references||[]).find(r=>r.id===id);if(!ref)continue;const p=document.createElement('p');p.textContent='['+id+'] '+ref.label;const rag=options.sources?.find(s=>s.citation===id);if(rag&&options.onCitation){p.className='rag-citation';p.tabIndex=0;p.onclick=()=>options.onCitation(rag,options.sources);p.onkeydown=e=>{if(e.key==='Enter')p.click();};}notes.append(p);}target.append(notes);
  return true;
}
const pageNotReady=page=>page.status!=='ready';

async function assertLayouts(deck,media,options){
  const root=document.createElement('div');root.style.cssText='position:fixed;left:-20000px;top:0;width:1280px;';document.body.append(root);
  try{
    for(const [index,page] of deck.pages.entries()){
      if(pageNotReady(page))continue;
      const frame=await pageElement(deck,page,index,media,options,root);
      await document.fonts.ready;await Promise.all([...frame.querySelectorAll('img')].map(img=>img.decode().catch(()=>{})));
      layoutSlide(frame,page.title);
    }
  }finally{await renderRich(root,'');root.remove();}
}

export async function exportSlides(value,kind,token){
  const deck=readDeck(value.content),root=document.createElement('div');root.className='slides-export';root.style.cssText='position:fixed;left:-20000px;top:0;width:1280px;background:white;';document.body.append(root);
  try{
    for(const [i,page] of deck.pages.entries()){
      if(page.status!=='ready')throw Error('Completa tutte le pagine prima di esportare le slide.');
      await pageElement(deck,page,i,value.media,{},root);
    }
    await document.fonts.ready;await Promise.all([...root.querySelectorAll('img')].map(img=>img.decode().catch(()=>{})));
    for(const frame of [...root.children])layoutSlide(frame,deck.pages[Number(frame.dataset.page)-1].title);
    if(kind==='pptx')return await (await import('./slide-pptx.js')).exportPowerPoint(root,deck,value.title);
    if(kind==='pdf')return await exportPdf(root,value.title,token,{slide_format:deck.format});
    if(kind==='docx')return await exportDocx(root,value.title);
    if(kind==='png')return await exportPng(root,value.title);
    if(kind==='html'){
      const html=await (await import('./exports.js')).printableHtml(root);
      const response=await fetch('/api/export/html',{method:'POST',headers:{'Content-Type':'application/json','X-H3-Token':token},body:JSON.stringify({title:value.title,html,slide_format:deck.format})});const result=await response.json();if(!response.ok)throw Error(result.error);
      const blob=await fetch(result.url).then(r=>r.blob());saveBlob(blob,value.title+'.html');
    }
  }finally{await renderRich(root,'');root.remove();}
}

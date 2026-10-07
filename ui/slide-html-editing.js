import {imagePicker} from './slide-image-picker.js';

const containerTags='main,section,article,div,aside,header,footer';
const contentChildren=element=>[...element.children].filter(e=>!e.matches('style,script,[data-h3-editor]')&&(e.textContent.trim()||e.matches('img,svg')||e.querySelector('img,svg')));
const automaticParent=element=>{const group=element?.closest('[data-h3-layout]');return group?.dataset.h3Layout==='free'?null:group;};
const resetOffset=element=>{element.style.translate='none';element.style.removeProperty('--h3-dx');element.style.removeProperty('--h3-dy');};

// Automatic layout is an explicit editing choice. Generated HTML keeps its
// original CSS until the user applies a layout to a slide or a group.
function arrange(container,mode,height,normalize=true){
  if(mode==='free'){container.dataset.h3Layout='free';return;}
  const doc=container.ownerDocument,columns=Number(mode.split('-')[1])||1;
  container.dataset.h3Layout=mode;
  Object.assign(container.style,{display:'grid',gridTemplateColumns:`repeat(${columns},minmax(0,1fr))`,alignContent:'start',alignItems:'start',minWidth:'0',minHeight:'0'});
  if(normalize)Object.assign(container.style,{gap:'20px',height:'auto'});
  const children=contentChildren(container);
  for(const child of children){
    if(normalize){
      resetOffset(child);
      Object.assign(child.style,{position:'relative',inset:'auto',width:'auto',height:'auto',minWidth:'0',minHeight:'0',maxWidth:'100%',margin:'0',overflowWrap:'anywhere'});
      child.style.gridColumn=child.matches('h1,h2')?'1 / -1':'auto';
      if(child.matches('img,svg'))Object.assign(child.style,{width:'100%',maxHeight:'220px',objectFit:'contain'});
      // A card's original fixed image widths must not spill into the next
      // column when the user changes its container's layout.
      for(const element of child.querySelectorAll('main,section,article,div,p,pre,ul,ol,li,table,img,svg')){
        if(element.closest('svg')&&element.tagName.toLowerCase()!=='svg')continue;
        resetOffset(element);
        Object.assign(element.style,{width:'auto',height:'auto',minWidth:'0',maxWidth:'100%',overflowWrap:'anywhere'});
        if(element.matches('img,svg'))Object.assign(element.style,{width:'100%',maxHeight:'220px',objectFit:'contain'});
        const css=doc.defaultView.getComputedStyle(element);
        if(['absolute','fixed'].includes(css.position)&&element.textContent.trim()){element.style.position='relative';element.style.inset='auto';resetOffset(element);}
      }
      for(const group of [child,...child.querySelectorAll(containerTags)]){
        const css=doc.defaultView.getComputedStyle(group),tracks=css.gridTemplateColumns.split(/\s+/);
        if(css.display==='grid'&&tracks.length<=4&&tracks.every(t=>/^\d+(\.\d+)?px$/.test(t)))group.style.gridTemplateColumns=`repeat(${tracks.length},minmax(0,1fr))`;
      }
    }
  }
  const bounds=()=>[...container.querySelectorAll('*')].filter(e=>!e.closest('style,[data-h3-editor]')&&(!e.closest('svg')||e.tagName.toLowerCase()==='svg')).map(e=>e.getBoundingClientRect());
  const fits=()=>{const outer=container.getBoundingClientRect(),bottom=Math.min(height-16,outer.bottom+1);return bounds().every(r=>r.left>=-1&&r.right<=1281&&r.bottom<=bottom);};
  // Compact content progressively; never erase text or shrink it indefinitely.
  for(let pass=0;pass<10&&!fits();pass++){
    container.style.gap=Math.max(8,20-pass*2)+'px';
    for(const e of container.querySelectorAll('*')){
      if(e.closest('style,[data-h3-editor],.katex')||e.closest('svg')&&e.tagName.toLowerCase()!=='svg')continue;
      const css=doc.defaultView.getComputedStyle(e);
      if([...e.childNodes].some(n=>n.nodeType===3&&n.textContent.trim())){
        const size=parseFloat(css.fontSize),minimum=e.matches('h1,h2,h3')?24:18;
        if(size>minimum)e.style.fontSize=Math.max(minimum,size*.9)+'px';
      }
      if(e.matches('img,svg'))e.style.maxHeight=Math.max(100,(parseFloat(css.maxHeight)||220)*.9)+'px';
    }
  }
  if(!fits())throw Error('Il gruppo contiene più spazio o testo di quanto entra nella slide. Dividilo in due gruppi o riduci il contenuto.');
}

export function editHtmlSlide(target,deck,index,frame,onChange,options,media,{doc,overflow,encode}){
  const page=deck.pages[index];let selected=null,saving=false,drag=null;
  const toolbar=document.createElement('section');toolbar.className='slide-editor slide-html-editor no-export';toolbar.ariaLabel='Modifica grafica della slide';
  toolbar.innerHTML=`<div class="slide-editor-top"><button id="slide-html-add">+ Testo</button><button id="slide-html-heading">+ Titolo</button><button id="slide-html-block">+ Blocco</button><button id="slide-html-copy">Duplica</button><button id="slide-html-delete">Elimina</button><button id="slide-html-undo">Annulla</button><button id="slide-html-redo">Ripeti</button><button id="slide-html-save">Applica e salva</button></div>
    <p class="slide-editor-help">Seleziona un elemento nella slide. Usa ↕ per spostarlo e ↘ per ridimensionarlo. Con un layout automatico, lo spostamento cambia l’ordine dei blocchi.</p>
    <div class="slide-editor-top"><span id="slide-html-selection">Nessun elemento selezionato</span><button id="slide-html-parent">Seleziona gruppo</button><button id="slide-html-previous">Sposta prima</button><button id="slide-html-next">Sposta dopo</button></div>
    <div class="slide-html-layout"><label>Impaginazione<select id="slide-html-layout"><option value="stack">Una colonna</option><option value="columns-2">Due colonne</option><option value="columns-3">Tre colonne</option><option value="free">Libero · trascinamento</option></select></label><label>Applica a<select id="slide-html-scope"><option value="slide">Intera slide</option><option value="group">Gruppo selezionato</option></select></label><button id="slide-html-arrange">Applica impaginazione</button></div>
    <details id="slide-html-properties"><summary>Testo e dimensioni</summary><div class="slide-html-properties"><label class="slide-editor-text">Testo<textarea id="slide-html-text" rows="3"></textarea></label><label>Carattere<select id="slide-html-font"><option>Segoe UI</option><option>Arial</option><option>Georgia</option><option>Manrope</option><option>Cormorant</option><option>Consolas</option><option>Comic Sans MS</option></select></label><label>Dimensione carattere<input id="slide-html-size" type="number" min="8" max="160"></label><label>Colore testo<input id="slide-html-color" type="color"></label><label>Sfondo<input id="slide-html-bg" type="color"></label><label>Larghezza<input id="slide-html-width" type="number" min="10" max="1280"></label><label>Altezza<input id="slide-html-height" type="number" min="10" max="1280"></label></div></details><p id="slide-html-status" role="status" aria-live="polite"></p>`;
  target.querySelector('.slides-navigation').after(toolbar);
  const q=s=>toolbar.querySelector(s),status=q('#slide-html-status');
  q('#slide-html-height').max=String(Math.ceil(frame.offsetHeight));
  const overlay=doc.createElement('div');overlay.dataset.h3Editor='';
  overlay.style.cssText='all:initial;position:fixed;z-index:2147483647;pointer-events:none;border:2px dashed #138a92;box-sizing:border-box;display:none;';
  for(const [action,symbol,label] of [['move','↕','Sposta elemento'],['resize','↘','Ridimensiona elemento']]){
    const handle=doc.createElement('button');handle.type='button';handle.dataset.action=action;handle.textContent=symbol;handle.ariaLabel=label;
    handle.style.cssText=`all:initial;position:absolute;${action==='move'?'left:0;top:0':'right:0;bottom:0'};background:#153d40;color:#fff;border:1px solid #fff;border-radius:6px;text-align:center;pointer-events:auto;cursor:${action==='move'?'move':'nwse-resize'};touch-action:none;user-select:none;`;overlay.append(handle);
  }
  doc.body.append(overlay);
  const cleanBody=()=>{const body=doc.body.cloneNode(true);body.querySelectorAll('[data-h3-editor]').forEach(e=>e.remove());return body;};
  const imageSources=new Map([...doc.images].map(img=>[img.dataset.assetId,img.src]));
  const snapshot=()=>{const body=cleanBody();body.querySelectorAll('img').forEach(img=>img.removeAttribute('src'));return body.innerHTML;},past=[],future=[];
  const updateHistory=()=>{q('#slide-html-undo').disabled=!past.length;q('#slide-html-redo').disabled=!future.length;};
  const remember=before=>{past.push(before);if(past.length>30)past.shift();future.length=0;updateHistory();};
  const updateOverlay=()=>{
    if(!selected?.isConnected){overlay.style.display='none';return;}
    const r=selected.getBoundingClientRect(),scale=frame.getBoundingClientRect().width/1280,size=Math.min(120,30/Math.max(.1,scale));
    Object.assign(overlay.style,{display:'block',left:r.left+'px',top:r.top+'px',width:r.width+'px',height:r.height+'px'});
    for(const handle of overlay.children)Object.assign(handle.style,{width:size+'px',height:size+'px',font:`${size*.65}px/${size}px sans-serif`});
  };
  const rgbHex=value=>{const m=value.match(/\d+/g);return m?'#'+m.slice(0,3).map(x=>Math.min(255,Number(x)).toString(16).padStart(2,'0')).join(''):'#ffffff';};
  const select=element=>{
    selected=element;
    if(!element){q('#slide-html-selection').textContent='Nessun elemento selezionato';updateOverlay();return;}
    const css=doc.defaultView.getComputedStyle(element),r=element.getBoundingClientRect();
    q('#slide-html-selection').textContent=(element.matches(containerTags)?'Blocco / gruppo':element.tagName==='IMG'?'Immagine':'Elemento')+' · '+(element.textContent.trim().slice(0,55)||element.getAttribute('alt')||element.tagName.toLowerCase());
    q('#slide-html-text').value=element.textContent;q('#slide-html-text').disabled=element.matches('img,svg')||!!element.querySelector('img,svg,div,section,article,h1,h2,p,ul,ol');
    q('#slide-html-size').value=Math.round(parseFloat(css.fontSize));q('#slide-html-color').value=rgbHex(css.color);q('#slide-html-bg').value=rgbHex(css.backgroundColor);
    q('#slide-html-width').value=Math.round(r.width);q('#slide-html-height').value=Math.round(r.height);
    q('#slide-html-font').value=[...q('#slide-html-font').options].map(x=>x.value).find(x=>css.fontFamily.includes(x))||'Arial';updateOverlay();
    const layout=element.closest('[data-h3-layout]')?.dataset.h3Layout;if(layout)q('#slide-html-layout').value=layout;
  };
  const root=()=>{
    const children=[...doc.body.children].filter(e=>!e.matches('style,script,[data-h3-editor]'));
    if(children.length===1&&children[0].matches(containerTags))return children[0];
    const group=doc.createElement('div');group.dataset.h3Root='';group.style.width='100%';
    doc.body.insertBefore(group,children[0]||overlay);for(const child of children)group.append(child);return group;
  };
  const insertionParent=()=>selected?.matches(containerTags)?selected:selected?.parentElement||root();
  const refreshLayout=element=>{let parent=automaticParent(element);while(parent){arrange(parent,parent.dataset.h3Layout,frame.offsetHeight,false);parent=automaticParent(parent.parentElement);}};
  const change=fn=>{
    const before=snapshot();
    try{fn();readjust();remember(before);status.textContent='Modifiche da salvare';return true;}
    catch(e){restore(before);status.textContent=e.message;return false;}
  };
  const readjust=()=>{if(selected)refreshLayout(selected);updateOverlay();};
  const restore=html=>{doc.body.innerHTML=html;for(const img of doc.images)if(imageSources.has(img.dataset.assetId))img.src=imageSources.get(img.dataset.assetId);doc.body.append(overlay);select(null);};
  q('#slide-html-undo').onclick=()=>{if(!past.length)return;future.push(snapshot());restore(past.pop());updateHistory();status.textContent='Modifica annullata · premi Applica e salva';};
  q('#slide-html-redo').onclick=()=>{if(!future.length)return;past.push(snapshot());restore(future.pop());updateHistory();status.textContent='Modifica ripristinata · premi Applica e salva';};updateHistory();
  doc.addEventListener('click',e=>{
    e.preventDefault();if(e.target.closest('[data-h3-editor]'))return;
    const element=e.target.closest('svg')||e.target.closest('.katex')?.closest('p,h1,h2,h3,li,div')||e.target.closest('h1,h2,h3,h4,p,pre,li,img,span,div,section,article,main');
    if(element&&element!==doc.body)select(element);
  });
  q('#slide-html-parent').onclick=()=>{const parent=selected?.parentElement;if(parent&&parent!==doc.body)select(parent);else status.textContent='Seleziona prima un elemento contenuto nel gruppo.';};
  const reorder=direction=>change(()=>{
    if(!selected)return;const other=direction<0?selected.previousElementSibling:selected.nextElementSibling;
    if(other&&!other.matches('style,[data-h3-editor]')){if(direction<0)other.before(selected);else other.after(selected);resetOffset(selected);}
  });
  q('#slide-html-previous').onclick=()=>reorder(-1);q('#slide-html-next').onclick=()=>reorder(1);
  q('#slide-html-arrange').onclick=()=>change(()=>{
    const group=q('#slide-html-scope').value==='slide'?root():selected?.matches(containerTags)?selected:selected?.parentElement;
    if(!group||group===doc.body&&q('#slide-html-scope').value==='group')throw Error('Seleziona un blocco o usa Seleziona gruppo.');
    arrange(group,q('#slide-html-layout').value,frame.offsetHeight);select(group===doc.body?contentChildren(group)[0]:group);
  });
  const add=kind=>change(()=>{
    const element=doc.createElement(kind==='block'?'section':kind==='heading'?'h2':'p'),parent=insertionParent();
    if(kind==='block'){
      const title=doc.createElement('h3'),text=doc.createElement('p');title.textContent='Titolo del blocco';text.textContent='Scrivi qui il contenuto.';element.append(title,text);
      element.dataset.h3Layout='stack';element.style.cssText='display:grid;gap:16px;padding:24px;border:1px solid currentColor;border-radius:16px;font-size:28px;';
    }else{element.textContent=kind==='heading'?'Nuovo titolo':'Nuovo testo';element.style.cssText=`font-size:${kind==='heading'?40:28}px;line-height:1.3;`;}
    if(!automaticParent(parent))element.style.cssText+=`position:absolute;left:80px;top:140px;width:${kind==='block'?480:600}px;max-width:100%;`;
    parent.append(element);select(element);
  });
  q('#slide-html-add').onclick=()=>add('text');q('#slide-html-heading').onclick=()=>add('heading');q('#slide-html-block').onclick=()=>add('block');
  q('#slide-html-copy').onclick=()=>change(()=>{
    if(!selected)return;const copy=selected.cloneNode(true);copy.removeAttribute('id');copy.querySelectorAll('[id]').forEach(n=>n.removeAttribute('id'));
    if(automaticParent(selected.parentElement))resetOffset(copy);else copy.style.translate='20px 20px';selected.after(copy);select(copy);
  });
  q('#slide-html-delete').onclick=()=>change(()=>{if(!selected)return;const parent=selected.parentElement;selected.remove();select(null);refreshLayout(parent);});
  q('#slide-html-text').oninput=()=>{if(selected&&!q('#slide-html-text').disabled)change(()=>selected.textContent=q('#slide-html-text').value);};
  for(const [id,property,unit] of [['size','font-size','px'],['color','color',''],['bg','background-color',''],['width','width','px'],['height','height','px'],['font','font-family','']])q('#slide-html-'+id).oninput=()=>{
    const input=q('#slide-html-'+id);if(!selected||unit&&!input.checkValidity())return;change(()=>selected.style.setProperty(property,input.value+unit));
  };
  doc.addEventListener('pointerdown',e=>{
    const handle=e.target.closest('[data-h3-editor] button');if(e.button!==0||!selected||!handle)return;e.preventDefault();
    const r=selected.getBoundingClientRect(),css=doc.defaultView.getComputedStyle(selected);
    drag={action:handle.dataset.action,x:e.clientX,y:e.clientY,rect:r,dx:parseFloat(css.getPropertyValue('--h3-dx'))||0,dy:parseFloat(css.getPropertyValue('--h3-dy'))||0,before:snapshot(),moved:false};
    handle.setPointerCapture(e.pointerId);
  });
  doc.addEventListener('pointermove',e=>{
    if(!drag||!selected)return;const dx=e.clientX-drag.x,dy=e.clientY-drag.y;drag.moved||=Math.abs(dx)+Math.abs(dy)>3;
    if(drag.action==='resize'){
      selected.style.width=Math.max(20,Math.min(1280-drag.rect.left,drag.rect.width+dx))+'px';
      selected.style.height=Math.max(20,Math.min(frame.offsetHeight-drag.rect.top,drag.rect.height+dy))+'px';
    }else if(automaticParent(selected.parentElement)){
      const parent=selected.parentElement,hit=doc.elementFromPoint(e.clientX,e.clientY);let other=hit;
      while(other&&other.parentElement!==parent)other=other.parentElement;
      if(other&&other!==selected&&!other.matches('[data-h3-editor],style')){const r=other.getBoundingClientRect();if(e.clientY>r.top+r.height/2||e.clientX>r.left+r.width/2)other.after(selected);else other.before(selected);}
    }else{
      selected.style.setProperty('--h3-dx',drag.dx+Math.max(-drag.rect.left,Math.min(1280-drag.rect.right,dx))+'px');
      selected.style.setProperty('--h3-dy',drag.dy+Math.max(-drag.rect.top,Math.min(frame.offsetHeight-drag.rect.bottom,dy))+'px');
      selected.style.translate='var(--h3-dx) var(--h3-dy)';
    }
    updateOverlay();
  });
  const finish=cancel=>{if(!drag)return;const action=drag;drag=null;if(cancel){restore(action.before);return;}if(action.moved){try{readjust();remember(action.before);select(selected);status.textContent='Modifiche da salvare';}catch(e){restore(action.before);status.textContent=e.message;}}};
  doc.addEventListener('pointerup',()=>finish(false));doc.addEventListener('pointercancel',()=>finish(true));
  const images=document.createElement('details');images.id='slide-html-images';images.innerHTML='<summary>Immagini · PC, allegati, RAG, Internet</summary>';toolbar.append(images);
  if(options.api)imagePicker(images,{api:options.api,chatId:options.chatId,media,onSelect:async asset=>{
    if(!media.some(m=>m.id===asset.id)&&media.length>=64)throw Error('Massimo 64 immagini per presentazione.');
    const blob=await fetch('/media/'+asset.path).then(r=>{if(!r.ok)throw Error('Immagine non disponibile.');return r.blob();}),src=await new Promise(resolve=>{const reader=new FileReader();reader.onload=()=>resolve(reader.result);reader.readAsDataURL(blob);});
    const preload=doc.createElement('img');preload.src=src;await preload.decode();
    const replacing=selected?.tagName==='IMG';
    imageSources.set(asset.id,src);
    const changed=change(()=>{const image=replacing?selected:doc.createElement('img');image.dataset.assetId=asset.id;image.src=src;image.alt=asset.name;
      if(!replacing){const parent=insertionParent();image.style.cssText='display:block;width:400px;max-width:100%;height:240px;object-fit:contain;';if(!automaticParent(parent))image.style.cssText+='position:absolute;left:80px;top:140px;';parent.append(image);}select(image);
    });
    if(!changed)return;
    if(!media.some(m=>m.id===asset.id))media.push(asset);
    if(asset.provenance){const id='I'+asset.id.slice(0,8),label=[asset.name,asset.provenance.credit,asset.provenance.license].filter(Boolean).join(' · ');deck.references||=[];if(!deck.references.some(r=>r.id===id))deck.references.push({id,label:label.slice(0,1000),...(asset.provenance.url?{url:asset.provenance.url}:{})});page.sources||=[];if(!page.sources.includes(id))page.sources.push(id);}
    if(selected?.isConnected)status.textContent='Immagine inserita · premi Applica e salva';
  }});
  q('#slide-html-save').onclick=async()=>{
    if(saving)return;saving=true;const old=page.html;
    try{
      readable();if(overflow(frame))throw Error('Un elemento supera i bordi: usa Impagina automaticamente oppure spostalo o ridimensionalo.');
      const editable=cleanBody();
      for(const formula of editable.querySelectorAll('.katex-display,.katex:not(.katex-display .katex)')){const tex=formula.querySelector('annotation')?.textContent;if(tex){const delimiter=formula.classList.contains('katex-display')?'$$':'$';formula.replaceWith(delimiter+tex+delimiter);}}
      editable.querySelectorAll('img').forEach(img=>img.removeAttribute('src'));
      page.html='<style>'+[...doc.querySelectorAll('style:not([data-h3-trusted])')].map(x=>x.textContent).join('\n')+'</style>'+editable.innerHTML.replace(/<style[\s\S]*?<\/style>/gi,'');
      if(page.html.length>80000)throw Error('La slide contiene troppo HTML. Riduci i blocchi o dividila in più pagine.');
      await onChange(encode(deck),media);status.textContent='Salvato';
    }catch(e){page.html=old;status.textContent=e.message;}finally{saving=false;}
  };
  const readable=()=>options.repairContrast?.(doc);
}

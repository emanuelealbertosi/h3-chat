let viewerApi;
export function initImageViewer({api}){viewerApi=api;}
const mediaSource=src=>{try{const u=new URL(src,location.href);return u.origin===location.origin&&u.pathname.startsWith('/media/')?u.pathname+u.search:null;}catch{return null;}};
const item=v=>({src:mediaSource(v.src||v.url||('/media/'+v.path)),name:v.name||'Immagine'});
// Only Fit enables automatic fitting. Manual zoom survives viewport resize.
function zoomControls(dialog,viewport,dimensions,paint){
 let zoom=1,fitting=true,drag=null,ready=false;
 const q=s=>dialog.querySelector(s),output=q('output[data-zoom]');
 function set(value,anchor){
  if(!ready)return;
  const old=zoom,x=anchor?.x??viewport.clientWidth/2,y=anchor?.y??viewport.clientHeight/2,left=(viewport.scrollLeft+x)/old,top=(viewport.scrollTop+y)/old;
  zoom=Math.max(.005,Math.min(8,value));paint(zoom);output.value=Math.round(zoom*1000)/10+'%';viewport.scrollLeft=left*zoom-x;viewport.scrollTop=top*zoom-y;
 }
 function fit(){if(!ready)return;fitting=true;const [w,h]=dimensions();set(Math.min(1,(viewport.clientWidth-24)/w,(viewport.clientHeight-24)/h));viewport.scrollTo(0,0);}
 const manual=(value,anchor)=>{fitting=false;set(value,anchor);};
 q('[data-fit]').onclick=fit;q('[data-actual]').onclick=()=>manual(1);q('[data-in]').onclick=()=>manual(zoom*1.25);q('[data-out]').onclick=()=>manual(zoom/1.25);
 viewport.addEventListener('wheel',e=>{e.preventDefault();const r=viewport.getBoundingClientRect();manual(zoom*(e.deltaY<0?1.15:1/1.15),{x:e.clientX-r.left,y:e.clientY-r.top});},{passive:false});
 viewport.onpointerdown=e=>{if(e.button!==0||e.target.closest('button,input,a'))return;drag={x:e.clientX,y:e.clientY,left:viewport.scrollLeft,top:viewport.scrollTop};viewport.setPointerCapture(e.pointerId);};
 viewport.onpointermove=e=>{if(drag){viewport.scrollLeft=drag.left+drag.x-e.clientX;viewport.scrollTop=drag.top+drag.y-e.clientY;}};viewport.onpointerup=viewport.onpointercancel=()=>drag=null;
 dialog.addEventListener('keydown',e=>{if(e.target.matches('input,select,textarea'))return;if(['+','=','-','0','f','F'].includes(e.key)){e.preventDefault();if(e.key==='0')manual(1);else if(e.key.toLowerCase()==='f')fit();else manual(zoom*(e.key==='-'?.8:1.25));}});
 const observer=new ResizeObserver(()=>{if(fitting)fit();});observer.observe(viewport);dialog.addEventListener('close',()=>observer.disconnect(),{once:true});
 return {loaded(){ready=true;dialog.querySelectorAll('[data-zoom-control]').forEach(b=>b.disabled=false);fit();},layout(){if(fitting)fit();else set(zoom);}};
}
const toolbar='<button type="button" class="btn small" data-out data-zoom-control disabled aria-label="Riduci zoom">−</button><output data-zoom aria-live="polite">Caricamento…</output><button type="button" class="btn small" data-in data-zoom-control disabled aria-label="Aumenta zoom">＋</button><button type="button" class="btn small" data-fit data-zoom-control disabled>Adatta</button><button type="button" class="btn small" data-actual data-zoom-control disabled>100%</button>';
function shell(name,opener){
 document.querySelectorAll('.image-zoom-dialog').forEach(d=>d.close());
 const d=document.createElement('dialog');d.className='image-zoom-dialog';d.ariaLabel=name;
 d.innerHTML='<header><strong></strong><button type="button" class="icon-button" data-close aria-label="Chiudi zoom immagine">×</button></header><div class="image-zoom-toolbar">'+toolbar+'</div><p class="image-viewer-status" role="status" hidden></p><div class="image-zoom-viewport"></div>';
 d.querySelector('strong').textContent=name;d.querySelector('[data-close]').onclick=()=>d.close();
 d.addEventListener('click',e=>{if(e.target===d){const r=d.getBoundingClientRect();if(e.clientX<r.left||e.clientX>r.right||e.clientY<r.top||e.clientY>r.bottom)d.close();}});
 d.addEventListener('close',()=>{d.remove();if(opener?.isConnected)opener.focus();},{once:true});document.body.append(d);d.showModal();return d;
}
function error(d){const s=d.querySelector('[role=status]');s.hidden=false;s.textContent='Immagine non disponibile. Chiudi e riprova oppure scegli un altro file.';d.querySelector('output').value='Non disponibile';}
export function openImageZoom(src,name='Immagine',opener=document.activeElement){
 src=mediaSource(src);if(!src)return;
 const d=shell(name,opener),viewport=d.querySelector('.image-zoom-viewport'),image=document.createElement('img');image.draggable=false;image.alt=name;viewport.append(image);
 const controls=zoomControls(d,viewport,()=>[image.naturalWidth,image.naturalHeight],z=>{image.style.width=image.naturalWidth*z+'px';image.style.height=image.naturalHeight*z+'px';});
 const download=document.createElement('a');download.className='btn small';download.download=name;download.href=src;download.textContent='Scarica';d.querySelector('.image-zoom-toolbar').append(download);
 const compare=document.createElement('button');compare.type='button';compare.className='btn small';compare.textContent='Confronta con…';compare.disabled=!viewerApi;d.querySelector('.image-zoom-toolbar').append(compare);
 compare.onclick=async()=>{const {openGallery}=await import('./gallery.js');openGallery({api:viewerApi,kind:'image',multiple:false,onSelect:images=>{const second=images.find(m=>m.mime?.startsWith('image/'));if(second)openImageCompare([{src,name},second],opener);}});};
 image.onload=()=>controls.loaded();image.onerror=()=>error(d);image.src=src;return d;
}
export function openImageCompare(values,opener=document.activeElement){
 const images=values.slice(0,2).map(item);if(images.length!==2||images.some(i=>!i.src))return;
 const d=shell('Confronto immagini',opener);d.classList.add('image-compare-dialog');const q=s=>d.querySelector(s),viewport=q('.image-zoom-viewport'),stage=document.createElement('div');stage.className='image-compare-stage';viewport.append(stage);
 const bar=document.createElement('div');bar.className='image-compare-modes';bar.innerHTML='<button type="button" class="btn small" data-side aria-pressed="true">Affiancate</button><button type="button" class="btn small" data-slider aria-pressed="false">Cursore</button><button type="button" class="btn small" data-swap>Scambia A / B</button>';q('.image-zoom-toolbar').append(bar);
 const captions=document.createElement('div');captions.className='image-compare-captions';const labels=images.map(()=>{const s=document.createElement('span');captions.append(s);return s;});viewport.before(captions);
 const slider=document.createElement('label');slider.className='image-compare-slider';slider.hidden=true;slider.innerHTML='<span>Posizione del confronto</span><input type="range" min="0" max="100" value="50" step="0.1" aria-label="Posizione del confronto"><output>50%</output>';viewport.after(slider);
 const note=document.createElement('small');note.className='image-compare-note';note.textContent='Proporzioni conservate. Se i formati differiscono, gli spazi vuoti restano visibili. Rotella per zoomare, trascina per spostarti.';d.append(note);
 let mode='side',width=1,height=1,loaded=0,panes=[];
 const divider=document.createElement('button');divider.type='button';divider.className='image-compare-divider';divider.ariaLabel='Trascina il cursore del confronto';divider.hidden=true;stage.append(divider);
 function clip(){const v=Number(slider.querySelector('input').value);if(panes[1])panes[1].style.clipPath=mode==='slider'?`inset(0 0 0 ${v}%)`:'';divider.style.left=v+'%';slider.querySelector('output').value=Math.round(v)+'%';}
 function paint(z){stage.dataset.mode=mode;stage.style.width=(mode==='side'?width*2+24:width)*z+'px';stage.style.height=height*z+'px';panes.forEach((p,i)=>{p.style.width=width*z+'px';p.style.height=height*z+'px';p.style.left=(mode==='side'?i*(width+24)*z:0)+'px';p.style.zIndex=String(i);});clip();}
 const controls=zoomControls(d,viewport,()=>[mode==='side'?width*2+24:width,height],paint);
 panes=images.map((data,i)=>{const pane=document.createElement('div');pane.className='image-compare-pane';const image=document.createElement('img');image.draggable=false;image.alt=data.name;pane.append(image);stage.insertBefore(pane,divider);image.onload=()=>{if(++loaded===2){width=Math.max(...panes.map(p=>p.firstChild.naturalWidth));height=Math.max(...panes.map(p=>p.firstChild.naturalHeight));controls.loaded();}};image.onerror=()=>error(d);image.src=data.src;labels[i].textContent=(i?'B · ':'A · ')+data.name;return pane;});
 function setMode(v){mode=v;slider.hidden=divider.hidden=mode!=='slider';q('[data-side]').setAttribute('aria-pressed',String(mode==='side'));q('[data-slider]').setAttribute('aria-pressed',String(mode==='slider'));controls.layout();}
 q('[data-side]').onclick=()=>setMode('side');q('[data-slider]').onclick=()=>setMode('slider');slider.querySelector('input').oninput=clip;
 q('[data-swap]').onclick=()=>{panes.reverse();panes.forEach((p,i)=>{labels[i].textContent=(i?'B · ':'A · ')+p.firstChild.alt;p.style.clipPath='';});controls.layout();};
 const move=e=>{const r=stage.getBoundingClientRect();slider.querySelector('input').value=String(Math.max(0,Math.min(100,(e.clientX-r.left)/r.width*100)));clip();};
 divider.onpointerdown=e=>{e.stopPropagation();divider.setPointerCapture(e.pointerId);move(e);};divider.onpointermove=e=>{if(divider.hasPointerCapture(e.pointerId))move(e);};
 divider.onkeydown=e=>{if(['ArrowLeft','ArrowRight','Home','End'].includes(e.key)){e.preventDefault();const input=slider.querySelector('input');input.value=e.key==='Home'?'0':e.key==='End'?'100':String(Number(input.value)+(e.key==='ArrowLeft'?-1:1));clip();}};return d;
}
export function bindImageZoom(target){
 for(const image of target.querySelectorAll('img[src^="/media/"]')){
  // Binding both the image and its enclosing button opens two modal dialogs.
  const trigger=image.closest('a,button')||image;trigger.classList.add('image-zoom-trigger');trigger.removeAttribute('target');trigger.setAttribute('aria-label','Ingrandisci '+(image.alt||'immagine'));
  if(trigger===image){trigger.tabIndex=0;trigger.setAttribute('role','button');trigger.onkeydown=e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();openImageZoom(image.getAttribute('src'),image.alt,trigger);}};}
  trigger.onclick=e=>{e.preventDefault();e.stopPropagation();openImageZoom(image.getAttribute('src'),image.alt,trigger);};
 }
}

export function openImageZoom(src,name='Immagine',opener=document.activeElement){
 if(!src?.startsWith('/media/'))return;
 document.querySelector('.image-zoom-dialog')?.close();
 const dialog=document.createElement('dialog');dialog.className='image-zoom-dialog';dialog.setAttribute('aria-label','Zoom immagine');
 dialog.innerHTML='<header><strong></strong><button type="button" class="icon-button" data-close aria-label="Chiudi zoom immagine">×</button></header><div class="image-zoom-toolbar"><button type="button" class="btn small" data-out aria-label="Riduci zoom">−</button><output aria-live="polite"></output><button type="button" class="btn small" data-in aria-label="Aumenta zoom">＋</button><button type="button" class="btn small" data-fit>Adatta</button><button type="button" class="btn small" data-actual>100%</button><a class="btn small" download>Scarica</a></div><div class="image-zoom-viewport"><img draggable="false"></div>';
 const image=dialog.querySelector('img'),viewport=dialog.querySelector('.image-zoom-viewport'),output=dialog.querySelector('output');let zoom=1;
 dialog.querySelector('strong').textContent=name;image.alt=name;dialog.querySelector('a').href=src;dialog.querySelector('a').download=name;
 function setZoom(value){zoom=Math.max(.05,Math.min(8,value));image.style.width=Math.round(image.naturalWidth*zoom)+'px';output.value=Math.round(zoom*100)+'%';}
 const fit=()=>{if(image.naturalWidth)setZoom(Math.min(1,(viewport.clientWidth-24)/image.naturalWidth,(viewport.clientHeight-24)/image.naturalHeight));};
 dialog.querySelector('[data-close]').onclick=()=>dialog.close();dialog.querySelector('[data-fit]').onclick=fit;dialog.querySelector('[data-actual]').onclick=()=>setZoom(1);dialog.querySelector('[data-in]').onclick=()=>setZoom(zoom*1.25);dialog.querySelector('[data-out]').onclick=()=>setZoom(zoom/1.25);
 viewport.addEventListener('wheel',event=>{event.preventDefault();setZoom(zoom*(event.deltaY<0?1.15:1/1.15));},{passive:false});
 let drag=null;viewport.onpointerdown=e=>{if(e.pointerType!=='mouse'||e.button!==0)return;drag={x:e.clientX,y:e.clientY,left:viewport.scrollLeft,top:viewport.scrollTop};viewport.setPointerCapture(e.pointerId);};
 viewport.onpointermove=e=>{if(drag){viewport.scrollLeft=drag.left+drag.x-e.clientX;viewport.scrollTop=drag.top+drag.y-e.clientY;}};viewport.onpointerup=viewport.onpointercancel=()=>{drag=null;};
 dialog.addEventListener('click',event=>{if(event.target===dialog){const r=dialog.getBoundingClientRect();if(event.clientX<r.left||event.clientX>r.right||event.clientY<r.top||event.clientY>r.bottom)dialog.close();}});
 const resize=new ResizeObserver(()=>{if(dialog.open&&image.naturalWidth&&image.getBoundingClientRect().width<viewport.clientWidth)fit();});
 dialog.addEventListener('close',()=>{resize.disconnect();dialog.remove();if(opener?.isConnected)opener.focus();},{once:true});image.onload=fit;
 document.body.append(dialog);dialog.showModal();resize.observe(viewport);image.src=src;
 return dialog;
}

export function bindImageZoom(target){
 for(const image of target.querySelectorAll('img[src^="/media/"]')){
  const trigger=image.closest('a')||image;trigger.classList.add('image-zoom-trigger');
  trigger.removeAttribute('target');trigger.setAttribute('aria-label','Ingrandisci '+(image.alt||'immagine'));
  if(trigger===image){trigger.tabIndex=0;trigger.setAttribute('role','button');trigger.onkeydown=e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();openImageZoom(image.getAttribute('src'),image.alt,trigger);}};}
  trigger.onclick=e=>{e.preventDefault();openImageZoom(image.getAttribute('src'),image.alt,trigger);};
 }
}

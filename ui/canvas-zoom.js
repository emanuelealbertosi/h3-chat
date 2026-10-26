// Zoom the preview surface, keeping its layout width and export size unchanged.
export function initCanvasZoom(){
 const panel=document.querySelector('#canvas-panel'),preview=document.querySelector('#canvas-preview');
 const viewport=document.createElement('div');viewport.className='canvas-zoom-viewport';preview.before(viewport);viewport.append(preview);
 const controls=document.createElement('div');controls.className='canvas-zoom-controls';controls.setAttribute('role','group');controls.ariaLabel='Zoom artefatto';
 controls.innerHTML='<button type="button" class="btn small" data-out aria-label="Riduci artefatto">−</button><select aria-label="Zoom artefatto">'+Array.from({length:11},(_,i)=>50+i*25).map(n=>`<option value="${n}">${n}%</option>`).join('')+'</select><button type="button" class="btn small" data-in aria-label="Ingrandisci artefatto">+</button><button type="button" class="text-button" data-fit>Adatta</button><button type="button" class="text-button" data-expand aria-pressed="false">Espandi canvas</button>';
 document.querySelector('.canvas-toolbar').append(controls);
 const select=controls.querySelector('select'),expand=controls.querySelector('[data-expand]');let factor=1,expanded=false;
 function layout(){
  preview.style.width=viewport.clientWidth+'px';preview.style.zoom=String(factor);preview.style.minHeight=viewport.clientHeight/factor+'px';
  select.value=String(Math.round(factor*100));controls.querySelector('[data-out]').disabled=factor<=.5;controls.querySelector('[data-in]').disabled=factor>=3;
 }
 function zoom(value){factor=Math.max(.5,Math.min(3,value));layout();}
 function enlarge(value){expanded=value;panel.classList.toggle('canvas-expanded',value);expand.textContent=value?'Riduci canvas':'Espandi canvas';expand.setAttribute('aria-pressed',String(value));layout();}
 controls.querySelector('[data-out]').onclick=()=>zoom(factor-.25);controls.querySelector('[data-in]').onclick=()=>zoom(factor+.25);select.onchange=()=>zoom(Number(select.value)/100);
 controls.querySelector('[data-fit]').onclick=()=>{zoom(1);viewport.scrollTo(0,0);};expand.onclick=()=>enlarge(!expanded);
 document.addEventListener('keydown',event=>{if(event.key==='Escape'&&expanded){enlarge(false);expand.focus();}});
 new ResizeObserver(layout).observe(viewport);
 new MutationObserver(()=>{viewport.hidden=preview.hidden;controls.hidden=preview.hidden;layout();}).observe(preview,{attributes:true,attributeFilter:['hidden']});
 new MutationObserver(()=>{if(panel.hidden&&expanded)enlarge(false);}).observe(panel,{attributes:true,attributeFilter:['hidden']});
 viewport.hidden=preview.hidden;layout();
 return {suspend(){const previous=factor;zoom(1);return ()=>zoom(previous);}};
}

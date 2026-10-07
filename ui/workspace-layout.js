const KEY='h3.workspace-layout.v1';
export function initWorkspaceLayout(){
 const sidebar=document.querySelector('#sidebar'),toggle=document.querySelector('#mobile-nav'),workspace=document.querySelector('#workspace'),canvas=document.querySelector('#canvas-panel');
 let saved={};try{saved=JSON.parse(localStorage.getItem(KEY)||'{}');}catch{}
 let collapsed=!!saved.collapsed,ratio=Number.isFinite(saved.canvasRatio)?saved.canvasRatio:.47;
 const persist=()=>{try{localStorage.setItem(KEY,JSON.stringify({collapsed,canvasRatio:ratio}));}catch{}};
 const mobile=()=>matchMedia('(max-width:640px)').matches;
 const close=document.createElement('button');close.type='button';close.id='sidebar-close';close.className='icon-button';close.textContent='‹';close.ariaLabel='Chiudi barra laterale';sidebar.prepend(close);
 function navigation(){
  const hidden=mobile()?!sidebar.classList.contains('visible'):collapsed;
  document.body.classList.toggle('sidebar-collapsed',!mobile()&&collapsed);sidebar.inert=hidden;
  toggle.setAttribute('aria-expanded',String(!hidden));toggle.setAttribute('aria-controls','sidebar');toggle.ariaLabel=hidden?'Apri barra laterale':'Chiudi barra laterale';toggle.title=toggle.ariaLabel;
 }
 toggle.onclick=()=>{if(mobile())sidebar.classList.toggle('visible');else{collapsed=!collapsed;persist();}navigation();};
 close.onclick=()=>{if(mobile())sidebar.classList.remove('visible');else{collapsed=true;persist();}navigation();toggle.focus();};
 const split=document.createElement('div');split.id='canvas-splitter';split.tabIndex=0;split.setAttribute('role','separator');split.setAttribute('aria-orientation','vertical');split.setAttribute('aria-label','Larghezza del canvas');split.setAttribute('aria-controls','canvas-panel');split.title='Trascina per ridimensionare · frecce per regolare · doppio clic per ripristinare';canvas.before(split);
 const limits=()=>{const width=workspace.clientWidth;return width>=720?[Math.max(.2,300/width),Math.min(.8,1-348/width)]:[.25,.75];};
 function resize(next=ratio){
  const [min,max]=limits();ratio=Math.max(min,Math.min(max,next));workspace.style.setProperty('--canvas-width',ratio*100+'%');
  split.setAttribute('aria-valuemin',String(Math.round(min*100)));split.setAttribute('aria-valuemax',String(Math.round(max*100)));split.setAttribute('aria-valuenow',String(Math.round(ratio*100)));split.setAttribute('aria-valuetext',Math.round(ratio*100)+'% del pannello');
 }
 let pointer=null;
 split.onpointerdown=event=>{if(event.button!==0)return;event.preventDefault();pointer=event.pointerId;split.setPointerCapture(pointer);split.focus();document.body.classList.add('resizing-canvas');};
 split.onpointermove=event=>{if(pointer!==event.pointerId)return;const rect=workspace.getBoundingClientRect();resize((rect.right-event.clientX)/rect.width);};
 const finish=()=>{if(pointer===null)return;pointer=null;document.body.classList.remove('resizing-canvas');persist();};split.onpointerup=finish;split.onpointercancel=finish;split.onlostpointercapture=finish;
 split.ondblclick=()=>{resize(.47);persist();};
 split.onkeydown=event=>{const [min,max]=limits();let next;if(event.key==='ArrowLeft')next=ratio+.025;if(event.key==='ArrowRight')next=ratio-.025;if(event.key==='Home')next=min;if(event.key==='End')next=max;if(next===undefined)return;event.preventDefault();resize(next);persist();};
 new ResizeObserver(()=>resize()).observe(workspace);
 new MutationObserver(()=>{split.hidden=canvas.hidden;}).observe(canvas,{attributes:true,attributeFilter:['hidden']});split.hidden=canvas.hidden;
 window.addEventListener('resize',()=>{navigation();resize();});
 document.addEventListener('keydown',event=>{if(event.key==='Escape'&&mobile()){sidebar.classList.remove('visible');navigation();}});
 navigation();resize();
}

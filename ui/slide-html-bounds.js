// Repair intrinsic sizing and clipped SVG coordinates without selecting a new layout.
export function contentOverflows(doc,height){
 const content=doc.querySelector('[data-h3-background-content]'),bounds=content?.getBoundingClientRect();
 return [...doc.body.querySelectorAll('*')].some(element=>{
  if(element.closest('style,[data-h3-editor],[data-h3-trusted]')||element.closest('svg')&&element.tagName.toLowerCase()!=='svg')return false;
  if(!element.getClientRects().length)return false;
  const box=element.getBoundingClientRect();return bounds?box.right>bounds.right+2||box.bottom>bounds.bottom+2||box.left<bounds.left-2||box.top<bounds.top-2:box.right>1282||box.bottom>height+2||box.left< -2||box.top< -2;
 });
}

export function fitMediaBounds(doc,height,wholeImages=false){
 let changed=false;
 const css=element=>doc.defaultView.getComputedStyle(element);
 // Repair a common authored-layout error: a wrapped title/subtitle extends
 // below the fixed top of its sibling content panel. Reserve actual space,
 // keeping the panel's lower edge and all text; never cover it with z-index.
 if(wholeImages){
  for(const header of doc.body.querySelectorAll('header,.header,[data-slide-header]')){
   if(!header.querySelector('h1,h2')||header.closest('svg'))continue;
   const head=header.getBoundingClientRect();if(head.top<0||head.top>height*.35)continue;
   const end=Math.max(head.bottom,...[...header.querySelectorAll('*')].filter(e=>!e.closest('style,svg')).map(e=>e.getBoundingClientRect().bottom));
   for(const panel of header.parentElement.children){
    if(panel===header||!panel.matches('main,.main,[data-slide-content]')||css(panel).position!=='absolute')continue;
    const box=panel.getBoundingClientRect(),gap=end+16-box.top;
    if(gap<=0||box.top<head.top||box.right<=head.left||box.left>=head.right||box.height-gap<80)continue;
    panel.style.setProperty('top',(panel.offsetTop+gap)+'px','important');
    panel.style.setProperty('height',(box.height-gap)+'px','important');changed=true;
   }
  }
 }
 // The root body's first child margin can shift an absolute background. Give
 // block bodies their own formatting context; preserve authored flex/grid.
 if(doc.querySelector('[data-h3-video]')&&css(doc.body).display==='block')doc.body.style.setProperty('display','flow-root','important');
 function relax(){
  for(const parent of doc.body.querySelectorAll('*')){
   if(!['grid','inline-grid','flex','inline-flex'].includes(css(parent).display))continue;
   const outer=parent.getBoundingClientRect();if(outer.bottom>height+2||outer.right>1282||outer.height<=0)continue;
   for(const child of parent.children){
    if(!child.style)continue;const style=css(child);
    if(style.minHeight==='auto'){child.style.setProperty('min-height','0','important');changed=true;}
    if(style.minWidth==='auto'){child.style.setProperty('min-width','0','important');changed=true;}
   }
  }
 }
 // Do not alter correctly fitted free HTML, including deliberate flex alignment.
 if(contentOverflows(doc,height)){relax();relax();}
 for(const element of doc.body.querySelectorAll('img,svg')){
  if(element.closest('[data-h3-trusted]'))continue;
  const parent=element.parentElement;if(!parent)continue;
  // Preserve complete source figures by default. Explicit image-fit choices
  // may fill the box with a proportional crop, also after saving and reloading.
  const imageFit=element.dataset.imageFit==='cover'?'cover':'contain';
  if(wholeImages&&element.tagName.toLowerCase()==='img'&&css(element).objectFit!==imageFit){
   element.style.setProperty('object-fit',imageFit,'important');changed=true;
  }
  const box=element.getBoundingClientRect(),outer=parent.getBoundingClientRect(),style=css(parent);
  if(outer.width>0&&outer.height>0&&(box.right>1282||box.bottom>height+2||box.width>outer.width+2||box.height>outer.height+2)){
   const width=Math.max(1,Math.min(1280,outer.right)-Math.max(0,outer.left)-parseFloat(style.paddingLeft||0)-parseFloat(style.paddingRight||0));
   const room=Math.max(1,Math.min(height,outer.bottom)-Math.max(0,outer.top)-parseFloat(style.paddingTop||0)-parseFloat(style.paddingBottom||0));
   element.style.setProperty('max-width',width+'px','important');element.style.setProperty('max-height',room+'px','important');
   if(element.tagName.toLowerCase()==='img')element.style.setProperty('object-fit',imageFit,'important');changed=true;
  }
  if(element.tagName.toLowerCase()!=='svg'||!element.querySelector('text'))continue;
  // getBBox includes labels outside viewBox, which would otherwise be silently cropped.
  try{
   const bounds=element.getBBox(),view=element.viewBox.baseVal;
   if(view.width<=0||view.height<=0||bounds.width<=0||bounds.height<=0)continue;
   if(bounds.x<view.x-1||bounds.y<view.y-1||bounds.x+bounds.width>view.x+view.width+1||bounds.y+bounds.height>view.y+view.height+1){
    const x=Math.min(view.x,bounds.x-6),y=Math.min(view.y,bounds.y-6),right=Math.max(view.x+view.width,bounds.x+bounds.width+6),bottom=Math.max(view.y+view.height,bounds.y+bounds.height+6);
    element.setAttribute('viewBox',`${x} ${y} ${right-x} ${bottom-y}`);element.setAttribute('preserveAspectRatio','xMidYMid meet');changed=true;
   }
  }catch{}
 }
 if(contentOverflows(doc,height)){relax();relax();}
 return changed;
}

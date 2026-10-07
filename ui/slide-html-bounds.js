// Repair intrinsic sizing and clipped SVG coordinates without selecting a new layout.
export function contentOverflows(doc,height){
 return [...doc.body.querySelectorAll('*')].some(element=>{
  if(element.closest('style,[data-h3-editor],[data-h3-trusted]')||element.closest('svg')&&element.tagName.toLowerCase()!=='svg')return false;
  const box=element.getBoundingClientRect();return box.right>1282||box.bottom>height+2||box.left< -2||box.top< -2;
 });
}

export function fitMediaBounds(doc,height){
 let changed=false;
 const css=element=>doc.defaultView.getComputedStyle(element);
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
  const parent=element.parentElement;if(!parent)continue;
  const box=element.getBoundingClientRect(),outer=parent.getBoundingClientRect(),style=css(parent);
  if(outer.width>0&&outer.height>0&&(box.right>1282||box.bottom>height+2||box.width>outer.width+2||box.height>outer.height+2)){
   const width=Math.max(1,Math.min(1280,outer.right)-Math.max(0,outer.left)-parseFloat(style.paddingLeft||0)-parseFloat(style.paddingRight||0));
   const room=Math.max(1,Math.min(height,outer.bottom)-Math.max(0,outer.top)-parseFloat(style.paddingTop||0)-parseFloat(style.paddingBottom||0));
   element.style.setProperty('max-width',width+'px','important');element.style.setProperty('max-height',room+'px','important');
   if(element.tagName.toLowerCase()==='img')element.style.setProperty('object-fit','contain','important');changed=true;
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

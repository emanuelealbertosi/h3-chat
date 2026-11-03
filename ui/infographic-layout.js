// Measure authored content, excluding flat backgrounds and empty containers.
// The LLM decides how to recompose a sparse portrait scene.
export function portraitLayout(doc,height,options={}){
 const width=doc.defaultView.innerWidth;
 if(height<=width*1.25||options.layout&&options.layout!=='full')return {issue:false};
 const body=doc.body.getBoundingClientRect(),intervals=[];
 const add=box=>{if(box.width<8||box.height<6||box.right<=0||box.left>=width)return;const start=Math.max(0,box.top),end=Math.min(height,box.bottom);if(end>start)intervals.push([start,end]);};
 const visible=node=>{for(let e=node;e&&e!==doc.documentElement;e=e.parentElement){const s=doc.defaultView.getComputedStyle(e);if(s.display==='none'||s.visibility==='hidden'||Number(s.opacity)<.02)return false;}return true;};
 const walker=doc.createTreeWalker(doc.body,4);let node,seen=0;
 while((node=walker.nextNode())&&seen++<1800){const parent=node.parentElement;if(!node.textContent.trim()||!parent||parent.closest('style,script,svg,[data-h3-editor]')||!visible(parent))continue;const range=doc.createRange();range.selectNodeContents(node);for(const box of range.getClientRects())add(box);}
 for(const element of doc.querySelectorAll('img,svg,video'))if(visible(element))add(element.getBoundingClientRect());
 intervals.sort((a,b)=>a[0]-b[0]);let bottom=0,gap=0;
 for(const [start,end] of intervals){gap=Math.max(gap,start-bottom);bottom=Math.max(bottom,end);}gap=Math.max(gap,height-bottom);
 const wrongSize=Math.abs(body.width-width)>3||Math.abs(body.height-height)>3;
 const ratio=intervals.length?gap/height:0;
 return {issue:wrongSize||ratio>.34,wrong_size:wrongSize,width,height,body_width:body.width,body_height:body.height,largest_gap:Math.round(gap),gap_ratio:Math.round(ratio*1000)/1000};
}

// Tight line-height inherited by two stacked labels can make their actual
// glyphs collide even when their flex item boxes do not. Reserve only the
// measured missing gap; do not shrink the type or alter single-panel scenes.
export function fitPanelText(doc,options={}){
 if(!options.layout||options.layout==='full')return false;
 let changed=false;
 const bounds=e=>{const walker=doc.createTreeWalker(e,NodeFilter.SHOW_TEXT),rects=[];let node;while(node=walker.nextNode()){if(!node.textContent.trim()||node.parentElement.closest('style,script,svg'))continue;const range=doc.createRange();range.selectNodeContents(node);rects.push(...range.getClientRects());}return rects.length?{left:Math.min(...rects.map(r=>r.left)),right:Math.max(...rects.map(r=>r.right)),top:Math.min(...rects.map(r=>r.top)),bottom:Math.max(...rects.map(r=>r.bottom))}:null;};
 for(const element of doc.querySelectorAll('[data-panel] *,[data-overlay] *')){
  const style=doc.defaultView.getComputedStyle(element);if(style.display!=='flex'||style.flexDirection!=='column')continue;
  const children=[...element.children].filter(e=>{const s=doc.defaultView.getComputedStyle(e);return s.display!=='none'&&s.visibility!=='hidden'&&!['absolute','fixed'].includes(s.position)&&!e.matches('svg,img,video');});
  let missing=0;for(let i=1;i<children.length;i++){const a=bounds(children[i-1]),b=bounds(children[i]);if(a&&b&&a.left<b.right&&a.right>b.left)missing=Math.max(missing,a.bottom-b.top);}
  if(missing>.5&&missing<24){element.style.setProperty('row-gap',((parseFloat(style.rowGap)||0)+missing+2)+'px','important');changed=true;}
 }
 for(const overlay of doc.querySelectorAll('[data-overlay]'))if(overlay.scrollHeight>overlay.clientHeight+1&&overlay.scrollHeight<doc.defaultView.innerHeight*.35){overlay.style.setProperty('height',overlay.scrollHeight+'px','important');changed=true;}
 return changed;
}

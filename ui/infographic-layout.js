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

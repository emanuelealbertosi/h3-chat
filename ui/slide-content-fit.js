function important(element,values){for(const [key,value] of Object.entries(values))element.style.setProperty(key,String(value),'important');}

export function contentRects(area){
 const doc=area.ownerDocument,rects=[];
 for(const element of area.querySelectorAll('main,section,article,header,footer,aside,div,p,li,table,img,svg,canvas,h1,h2,h3,h4')){
  if(element.closest('[data-h3-trusted],[data-h3-editor],[aria-hidden="true"],style,script')||element.closest('svg')&&element.tagName.toLowerCase()!=='svg')continue;
  if(!element.textContent.trim()&&!element.matches('img,svg,canvas')&&!element.querySelector('img,svg,canvas'))continue;
  const style=doc.defaultView.getComputedStyle(element);if(style.display==='none'||style.visibility==='hidden'||!element.getClientRects().length)continue;
  const r=element.getBoundingClientRect();if(r.width&&r.height)rects.push(r);
 }
 const walker=doc.createTreeWalker(area,NodeFilter.SHOW_TEXT);let text;
 while(text=walker.nextNode()){
  if(!text.data.trim()||text.parentElement.closest('style,script,[data-h3-trusted],[data-h3-editor],[aria-hidden="true"]'))continue;
  const style=doc.defaultView.getComputedStyle(text.parentElement);if(style.display==='none'||style.visibility==='hidden')continue;
  const range=doc.createRange();range.selectNodeContents(text);for(const r of range.getClientRects())if(r.width&&r.height)rects.push(r);
 }
 return rects;
}

export function fitHtmlBackground(doc){
 const area=doc.querySelector('[data-h3-background-content]'),canvas=area?.querySelector(':scope > [data-h3-content-canvas]');if(!canvas)return false;
 const width=Number(canvas.dataset.h3ViewportWidth),height=Number(canvas.dataset.h3ViewportHeight);
 important(canvas,{left:'0',top:'0',width:width+'px',height:height+'px',transform:'scale(1)','transform-origin':'0 0'});
 const origin=canvas.getBoundingClientRect();let left=0,top=0,right=width,bottom=height;
 for(const r of contentRects(canvas)){left=Math.min(left,r.left-origin.left);top=Math.min(top,r.top-origin.top);right=Math.max(right,r.right-origin.left);bottom=Math.max(bottom,r.bottom-origin.top);}
 const safe=area.getBoundingClientRect(),scale=Math.min(1,safe.width/(right-left),safe.height/(bottom-top));
 important(canvas,{left:Math.max(0,(safe.width-(right-left)*scale)/2)+'px',top:Math.max(0,(safe.height-(bottom-top)*scale)/2)+'px',transform:`scale(${scale}) translate(${-left}px, ${-top}px)`});
 canvas.dataset.h3ContentScale=String(scale);area.dataset.h3ContentFit=scale<.999?'proportional':'native';return scale<.999;
}

export function contentScale(element){return Number(element.closest('[data-h3-content-canvas]')?.dataset.h3ContentScale)||1;}

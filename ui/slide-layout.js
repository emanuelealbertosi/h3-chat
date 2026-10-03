// Measure the actual browser layout. Pagination preserves DOM content (including
// highlighted code, charts and citations); it never asks an LLM to omit facts.
function fits(frame){
  const body=frame.querySelector('.h3-slide-body'),style=getComputedStyle(frame);
  const height=parseFloat(frame.style.getPropertyValue('--slide-height'))||720;
  const available=height-parseFloat(style.paddingTop)-parseFloat(style.paddingBottom);
  return body.scrollHeight<=available+2&&body.scrollWidth<=body.clientWidth+2;
}
export function fitSlide(frame){
  for(const factor of [1,.94,.88]){
    frame.style.setProperty('--slide-fit',factor);
    if(fits(frame))return true;
  }
  return false;
}
function shell(node,children){const copy=node.cloneNode(false);copy.append(...children);return copy;}
function divideText(node){
  const walker=document.createTreeWalker(node,NodeFilter.SHOW_TEXT),texts=[];let text;
  while(text=walker.nextNode())if(!text.parentElement.closest('.katex,svg,canvas,a'))texts.push(text);
  const length=texts.reduce((sum,n)=>sum+n.length,0);if(length<2)return null;
  let target=Math.floor(length/2),point;
  for(const n of texts){if(target>n.length){target-=n.length;continue;}point={node:n,offset:target};break;}
  if(!point)return null;
  // Prefer line boundaries in code, and word boundaries in prose. Range keeps
  // inline emphasis/highlight spans on both sides of the continuation.
  const data=point.node.data,boundaries=[...data.matchAll(node.querySelector('pre')?/\n/g:/\s+/g)].map(m=>m.index+m[0].length);
  const valid=boundaries.filter(n=>n>0&&n<data.length);
  if(valid.length)point.offset=valid.reduce((best,n)=>Math.abs(n-point.offset)<Math.abs(best-point.offset)?n:best,valid[0]);
  const left=document.createRange(),right=document.createRange();
  left.setStart(node,0);left.setEnd(point.node,point.offset);right.setStart(point.node,point.offset);right.setEnd(node,node.childNodes.length);
  const a=shell(node,[left.cloneContents()]),b=shell(node,[right.cloneContents()]);
  if(!a.textContent||!b.textContent)return null;
  return [a,b];
}
function divide(node){
  const children=[...node.children];
  if(node.classList.contains('slide-group')&&children.length>1){
    return children.map(child=>{const piece=shell(node,[child]);piece.style.display='flex';piece.style.removeProperty('grid-template-columns');return piece;});
  }
  if(node.classList.contains('rich')&&children.length>1)return children.map(child=>shell(node,[child]));
  if(children.length===1){
    const child=children[0];
    if(child.matches('ul,ol')&&child.children.length>1){
      const start=Number(child.getAttribute('start')||1);
      return [...child.children].map((item,i)=>{const list=shell(child,[item]);if(child.tagName==='OL')list.start=start+i;return shell(node,[list]);});
    }
    if(child.matches('table')&&child.tBodies[0]?.rows.length>1){
      return [...child.tBodies[0].rows].map(row=>{const table=shell(child,[]);if(child.tHead)table.append(child.tHead.cloneNode(true));const body=document.createElement('tbody');body.append(row);table.append(body);return shell(node,[table]);});
    }
    if(child.classList.contains('slide-group')){
      const pieces=divide(child);if(pieces)return pieces.map(piece=>shell(node,[piece]));
    }
  }
  return divideText(node);
}
function heading(node){return node.classList.contains('slide-heading')||node.classList.contains('slide-continuation-title');}
export function layoutSlide(frame,title){
  if(fitSlide(frame))return [frame];
  // A dense auto-grid becomes a flowing document before pagination. Explicit
  // model columns remain together whenever they fit as one block.
  frame.classList.remove('slide-auto-grid');frame.style.setProperty('--slide-fit','1');
  if(fitSlide(frame))return [frame];
  const original=frame.querySelector('.h3-slide-body'),queue=[...original.children];original.replaceChildren();
  const footer=frame.querySelector('.h3-slide-footer'),frames=[frame];let body=original,current=frame,operations=0;
  const next=carried=>{
    if(frames.length>=100)throw Error('Questa slide richiede troppe continuazioni. Usa una presentazione più breve.');
    current=frame.cloneNode(false);current.classList.add('slide-continuation');current.style.setProperty('--slide-fit','1');
    body=original.cloneNode(false);current.append(body,footer.cloneNode(true));
    const label=carried||document.createElement('div');
    if(!carried){label.className='slide-continuation-title';label.textContent=title+' · seguito';}body.append(label);
    frames.at(-1).after(current);frames.push(current);
  };
  while(queue.length){
    if(++operations>2000)throw Error('Contenuto troppo complesso da impaginare.');
    const unit=queue.shift();body.append(unit);
    if(fitSlide(current))continue;
    unit.remove();
    if([...body.children].some(n=>!heading(n))){
      let carried=null;if(heading(body.lastElementChild)){carried=body.lastElementChild;carried.remove();}
      next(carried);queue.unshift(unit);continue;
    }
    const pieces=divide(unit);
    if(pieces?.length>1){queue.unshift(...pieces);continue;}
    // Images, SVG and math are indivisible: resize their visual area as a whole.
    // No text is clipped, and prose/code use the readable pagination path above.
    body.append(unit);const visual=unit.querySelector('img,svg,.katex-display,canvas');
    if(visual){
      const height=parseFloat(current.style.getPropertyValue('--slide-height'))||720;
      const scale=Math.min(1,(height-220)/Math.max(1,unit.scrollHeight),body.clientWidth/Math.max(1,unit.scrollWidth));
      const inner=document.createElement('div');inner.append(...unit.childNodes);inner.style.transformOrigin='top left';inner.style.transform='scale('+scale+')';
      inner.style.width=100/scale+'%';unit.append(inner);unit.style.height=inner.scrollHeight*scale+'px';
      if(fitSlide(current))continue;
    }
    throw Error('Un elemento della slide non è suddivisibile nel formato scelto.');
  }
  for(const [index,page] of frames.entries()){
    page.dataset.continuation=String(index+1);page.dataset.continuations=String(frames.length);
    page.querySelector('.h3-slide-footer').textContent+=` · ${index+1}/${frames.length} parti`;
  }
  return frames;
}

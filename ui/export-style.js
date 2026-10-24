// Computed styles contain hundreds of browser defaults. Reset to those defaults
// explicitly and copy only differences, preserving the painted static page.
export function initialExportStyles(doc){
 const probe=doc.createElement('span');probe.style.setProperty('all','initial','important');doc.body.append(probe);
 try{const css=doc.defaultView.getComputedStyle(probe);return new Map([...css].map(property=>[property,css.getPropertyValue(property)]));}
 finally{probe.remove();}
}

export function applyExportStyles(target,css,initial,{pseudo=false}={}){
 const declarations=['all:initial'];
 for(const property of css){
  if(property.startsWith('--')||property==='all'||pseudo&&property==='content')continue;
  const value=css.getPropertyValue(property);
  if(value&&value!==initial.get(property)&&!/url\(/i.test(value))declarations.push(property+':'+value);
 }
 declarations.push('animation:none','transition:none');
 // Keep the shorthand literal: mutating CSSStyleDeclaration expands `all`
 // into hundreds of initial declarations when any longhand is changed.
 target.setAttribute('style',declarations.join(';'));
}

// Computed styles contain hundreds of browser defaults. Reset to those defaults
// explicitly and copy only differences, preserving the painted static page.
export function initialExportStyles(doc){
 const probe=doc.createElement('span');probe.style.setProperty('all','initial','important');doc.body.append(probe);
 try{const css=doc.defaultView.getComputedStyle(probe);return new Map([...css].map(property=>[property,css.getPropertyValue(property)]));}
 finally{probe.remove();}
}

export function exportStyleValue(value){
 return value.replace(/url\(["']?([^\)"']+)["']?\)/gi,(whole,url)=>{
  const hash=url.indexOf('#');return hash>=0&&/^[\w:.-]+$/.test(url.slice(hash+1))?'url(#'+url.slice(hash+1)+')':whole;
 });
}
export function applyExportStyles(target,css,initial,{pseudo=false}={}){
 const declarations=['all:initial'];
 for(const property of css){
  if(property.startsWith('--')||property==='all'||pseudo&&property==='content')continue;
  const value=exportStyleValue(css.getPropertyValue(property));
  if(value&&value!==initial.get(property)&&!value.replace(/url\(#[\w:.-]+\)/g,'').match(/url\(/i))declarations.push(property+':'+value);
 }
 declarations.push('animation:none','transition:none');
 // SVG's transform origin differs from an HTML probe after `all:initial`.
 // Preserve it explicitly so mirrored corner motifs and authored SVG groups
 // do not move outside the page in flattened HTML/PDF/PowerPoint exports.
 if(css.getPropertyValue('transform')!=='none')declarations.push('transform-origin:'+css.getPropertyValue('transform-origin'),'transform-box:'+css.getPropertyValue('transform-box'));
 // Keep the shorthand literal: mutating CSSStyleDeclaration expands `all`
 // into hundreds of initial declarations when any longhand is changed.
 target.setAttribute('style',declarations.join(';'));
}

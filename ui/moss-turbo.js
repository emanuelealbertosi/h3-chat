export const MOSS_TURBO_RECIPE={steps:8,cfg:1,sampler:'euler',scheduler:'sgm_uniform'};
export function toggleMossTurbo(values,enabled){
 const next={...values};
 if(enabled&&!values.moss_turbo){
  next.moss_turbo_previous=Object.fromEntries(Object.keys(MOSS_TURBO_RECIPE).map(k=>[k,values[k]]));
  Object.assign(next,MOSS_TURBO_RECIPE,{moss_turbo:true});
 }else if(!enabled){
  Object.assign(next,values.moss_turbo_previous||{});next.moss_turbo=false;delete next.moss_turbo_previous;
 }
 return next;
}
export function mossTurboValues(values){return values.moss_turbo?{...values,...MOSS_TURBO_RECIPE}:values;}
export function mountMossTurbo(host,values,capability,onChange,getValues){
 const section=document.createElement('section');section.className='moss-turbo-controls';
 section.innerHTML='<label class="check"><input type="checkbox" data-moss-turbo> Turbo DMD2 · 8 passi</label><p class="small-note">8 passi, CFG 1, Euler / SGM Uniform. Disattivando recuperi i parametri precedenti; formato e seed restano invariati. Su MOSS SFT è sperimentale. Con CFG 1 il negativo non viene usato. Il prompt ha priorità.</p>';
 const flag=section.querySelector('input');flag.checked=!!values.moss_turbo;
 flag.disabled=!capability?.ready&&!values.moss_turbo;
 if(flag.disabled)section.querySelector('p').textContent='Componente DMD2 non ancora installato.';
 flag.oninput=event=>event.stopPropagation();
 flag.onclick=event=>{
  event.preventDefault();event.stopPropagation();
  const current=getValues?.()||values;
  onChange(toggleMossTurbo(current,!current.moss_turbo));
 };
 host.append(section);return section;
}

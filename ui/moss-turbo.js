export const MOSS_TURBO_RECIPE={steps:8,cfg:1,sampler:'euler',scheduler:'simple'};
export const MOSS_STANDARD_RECIPE={steps:50,cfg:3,sampler:'euler',scheduler:'sgm_uniform'};
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
export function refreshMossRecipe(host,values){
 const note=host.querySelector('[data-moss-current]');if(!note)return;
 note.textContent=values.moss_turbo?'Attuale: Turbo DMD2 attivo · 8 passi / CFG 1.':values.steps===8&&values.cfg===1?'Attenzione: Turbo disattivato. Impostare 8 passi / CFG 1 non carica il LoRA: attiva il flag Turbo oppure applica la ricetta standard.':values.steps===50&&values.cfg===3?'Attuale: 50 passi / CFG 3 · Turbo disattivato.':`Attuale: ${values.steps} passi / CFG ${values.cfg} personalizzati · Turbo disattivato.`;
}
export function mountMossTurbo(host,values,capability,onChange,getValues){
 const section=document.createElement('section');section.className='moss-turbo-controls';
 section.innerHTML='<p class="small-note">MOSS / Kromoss standard: <strong>50 passi · CFG 3</strong> · Euler / SGM Uniform. Gli 8 passi richiedono il LoRA Turbo attivo.</p><button type="button" class="btn small" data-moss-standard>Applica ricetta standard · 50 passi / CFG 3</button><label class="check"><input type="checkbox" data-moss-turbo> Turbo DMD2 · 8 passi / CFG 1</label><p class="small-note" data-turbo-help>Il flag carica il LoRA e imposta automaticamente 8 passi, CFG 1, Euler / Simple. Disattivando recuperi i parametri precedenti; formato e seed restano invariati. Su MOSS SFT è sperimentale. Con CFG 1 il negativo non viene usato. Il prompt ha priorità.</p>';
 const flag=section.querySelector('input');flag.checked=!!values.moss_turbo;
 flag.disabled=!capability?.ready&&!values.moss_turbo;
 if(flag.disabled)section.querySelector('[data-turbo-help]').textContent='Componente DMD2 non ancora installato. La ricetta standard resta disponibile.';
 section.querySelector('[data-moss-standard]').onclick=()=>{const next={...(getValues?.()||values),...MOSS_STANDARD_RECIPE,moss_turbo:false};delete next.moss_turbo_previous;onChange(next);};
 flag.oninput=event=>event.stopPropagation();
 flag.onclick=event=>{
  event.preventDefault();event.stopPropagation();
  const current=getValues?.()||values;
  onChange(toggleMossTurbo(current,!current.moss_turbo));
 };
 const current=document.createElement('p');current.className='small-note';current.dataset.mossCurrent='';current.setAttribute('role','status');section.append(current);refreshMossRecipe(section,values);host.append(section);return section;
}

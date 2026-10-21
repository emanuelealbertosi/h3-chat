import {escape as esc} from './render.js';
import {mossNegativeDefault} from './image-negative-defaults.js';

export function initMossPresets({holder,getState,getParameters,applyParameters,savePresets,notify}){
 holder.innerHTML='<label class="field"><span>Preset MOSS</span><select data-moss-preset aria-label="Preset MOSS"></select></label><p class="small-note" data-moss-preset-note></p><div class="settings-grid"><label class="field"><span>Nome del preset</span><input type="text" maxlength="80" data-moss-preset-name placeholder="Es. Ritratto · 2 MP"></label><div class="visual-model-actions"><button type="button" class="btn small" data-moss-preset-save>Salva preset</button><button type="button" class="text-button" data-moss-preset-delete>Elimina preset</button></div></div><p class="small-note">I preset personali salvano tutti i parametri qui sotto e sono disponibili nelle altre chat di questo spazio di lavoro. Il prompt mantiene la priorità.</p>';
 const select=holder.querySelector('[data-moss-preset]'),name=holder.querySelector('[data-moss-preset-name]'),save=holder.querySelector('[data-moss-preset-save]'),remove=holder.querySelector('[data-moss-preset-delete]'),note=holder.querySelector('[data-moss-preset-note]');
 let signature='',selected='',busy=false;
 const library=()=>[...(getState().image_options.moss_presets||[]).map(p=>({...p,builtin:true,
  // Also works while an older backend finishes an already-running generation.
  ...(p.parameters.negative_prompt===''?{parameters:{...p.parameters,negative_prompt:mossNegativeDefault(getState())},description:p.description.replace('Prompt negativo vuoto','Negativo generale modificabile')}:{}),
 })),...(getState().settings.moss_presets||[])];
 const same=(preset,current)=>Object.entries(preset.parameters).every(([k,v])=>current[k]===v);
 function render(){
  const presets=library(),next=JSON.stringify(presets);let current;
  try{current=getParameters();}catch{current=null;}
  if(next!==signature){signature=next;select.innerHTML='<option value="">Personalizzato · parametri attuali</option>'+['Ricette incluse','I tuoi preset'].map((label,i)=>`<optgroup label="${label}">${presets.filter(p=>Boolean(p.builtin)===(i===0)).map(p=>`<option value="${esc(p.id)}">${esc(p.name)}</option>`).join('')}</optgroup>`).join('');}
  let chosen=current&&presets.find(p=>p.id===selected&&same(p,current));
  if(!chosen)chosen=current&&presets.find(p=>same(p,current));
  selected=chosen?.id||'';select.value=selected;
  note.textContent=chosen?.description||(chosen?'Preset personale · include megapixel, formato, seed e parametri di generazione.':'Parametri personalizzati: puoi salvarli con un nome.');
  select.disabled=busy;save.disabled=busy;remove.disabled=busy||!chosen||!!chosen.builtin;
 }
 select.oninput=()=>{const chosen=library().find(p=>p.id===select.value);selected=chosen?.id||'';if(!chosen)return;name.value=chosen.builtin?'':chosen.name;applyParameters(chosen.parameters);render();};
 async function change(action){
  if(busy)return;busy=true;render();
  try{await action();}catch(e){notify(e.message,true);}finally{busy=false;render();}
 }
 save.onclick=()=>change(async()=>{
  const title=name.value.trim();if(!title||title.length>80||/[\x00-\x1f]/.test(title))throw Error('Scrivi un nome di massimo 80 caratteri per il preset.');
  const presets=library();if(presets.some(p=>p.builtin&&p.name.toLocaleLowerCase()===title.toLocaleLowerCase()))throw Error('Ufficiale e Fizgig restano disponibili: scegli un altro nome per la tua versione.');
  const previous=presets.find(p=>!p.builtin&&p.name.toLocaleLowerCase()===title.toLocaleLowerCase()),parameters=getParameters();
  const item={id:previous?.id||crypto.randomUUID().replaceAll('-',''),name:title,parameters};
  const custom=presets.filter(p=>!p.builtin).map(({id,name,parameters})=>({id,name,parameters}));
  if(previous)custom[custom.findIndex(p=>p.id===previous.id)]=item;else custom.push(item);
  if(custom.length>50)throw Error('Puoi salvare al massimo 50 preset MOSS.');
  await savePresets(custom);selected=item.id;name.value=title;notify(previous?'Preset aggiornato.':'Preset salvato.');
 });
 remove.onclick=()=>change(async()=>{
  const chosen=library().find(p=>p.id===selected&&!p.builtin);if(!chosen)return;
  await savePresets((getState().settings.moss_presets||[]).filter(p=>p.id!==chosen.id));selected='';name.value='';notify('Preset eliminato. I parametri attuali restano impostati.');
 });
 return {render};
}

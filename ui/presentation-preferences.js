const copy=value=>structuredClone(value);
const signature=value=>JSON.stringify(value&&typeof value==='object'?Array.isArray(value)?value.map(v=>JSON.parse(signature(v))):Object.fromEntries(Object.keys(value).sort().map(k=>[k,JSON.parse(signature(value[k]))])):value);

// The form controls remain owned by the existing composer, not duplicated.
export function slidePreferencesAdapter(picker,onChange,images){
 const ids={count_mode:'slides-count-mode',count:'slides-count',format:'slides-format',duration_minutes:'slides-duration',llm_timeout:'slides-timeout',engine:'slides-engine',design:'slides-design',detail:'slides-detail',composition:'slides-composition',motion:'slides-motion',vision_scope:'slides-vision',generate_images:'slides-generate-images',image_model:'slides-image-model',background:'slides-background',background_color:'slides-background-color',text_tone:'slides-text-tone',palette:'slides-palette'};
 const numbers=new Set(['count','duration_minutes','llm_timeout']),field=k=>document.getElementById(ids[k]);
 return {holder:document.getElementById('slides-options'),matches:event=>Object.values(ids).includes(event.target.id)||!!event.target.closest('#slides-options .slide-background-controls')||!!images?.lots.matches(event),read(){
  const config={};for(const key of Object.keys(ids)){const e=field(key);if(!e.checkValidity())throw Error('Controlla il campo «'+(e.getAttribute('aria-label')||e.closest('label')?.textContent.trim()||key)+'».');config[key]=e.type==='checkbox'?e.checked:numbers.has(key)?Number(e.value):e.value;}
  return {...config,...images?.lots.read(),background_style:picker.read().background_style||null};
 },apply(config){
  for(const [key,value] of Object.entries(config))if(ids[key]){const e=field(key);if(e.tagName==='SELECT'&&value&&![...e.options].some(o=>o.value===value)){const missing=document.createElement('option');missing.value=value;missing.textContent='Modello del preset non disponibile · scegli un altro';e.append(missing);}if(e.type==='checkbox')e.checked=value;else e.value=value;}
  picker.apply(config.background_style);
  images?.lots.apply(config);
  for(const key of Object.keys(ids))field(key).dispatchEvent(new Event('change',{bubbles:true}));
  onChange?.();
 }};
}

export function initPresentationPreferences({api,getState,notify,adapters}){
 const slots=new Map();let loaded=false,loading=false,applying=false;
 for(const [kind,adapter] of Object.entries(adapters)){
  const label=kind==='slides'?'slide':'sfondi',bar=document.createElement('div');bar.className='presentation-preset-toolbar';bar.dataset.presentationPresets=kind;
  bar.innerHTML=`<label>Preset ${label}<select aria-label="Preset ${label}"><option value="">Ultime impostazioni · personalizzate</option></select></label><div><button type="button" class="btn small" data-save>Salva preset</button><button type="button" class="text-button" data-delete>Elimina preset</button></div><small role="status">Caricamento delle impostazioni salvate…</small>`;
  adapter.holder.prepend(bar);
  const dialog=document.createElement('dialog');dialog.className='prompt-options-dialog presentation-preset-dialog';dialog.dataset.presetDialog=kind;
  dialog.innerHTML='<header><h2></h2><button type="button" class="icon-button" data-close aria-label="Chiudi preset">×</button></header><form novalidate><div class="prompt-options-body"><label>Nome del preset<input type="text" maxlength="80" required aria-label="Nome del preset" autocomplete="off"></label><p data-note></p><p class="message-error" data-error hidden></p></div><footer><button type="button" data-cancel>Annulla</button><button type="submit" class="btn primary">Salva preset</button></footer></form>';
  document.body.append(dialog);
  const slot={kind,label,adapter,bar,select:bar.querySelector('select'),status:bar.querySelector('small'),dialog,group:{last:null,presets:[]},dirty:false,timer:null,pending:null,saving:null,saved:'',busy:false,mode:'save'};slots.set(kind,slot);
  const input=dialog.querySelector('input'),note=dialog.querySelector('[data-note]'),error=dialog.querySelector('[data-error]'),submit=dialog.querySelector('[type=submit]');
  function explain(){const exists=slot.group.presets.some(p=>p.name.toLocaleLowerCase()===input.value.trim().toLocaleLowerCase());submit.textContent=slot.mode==='delete'?'Elimina preset':exists?'Aggiorna preset':'Salva preset';note.textContent=slot.mode==='delete'?'Elimina il preset selezionato. Le impostazioni attuali restano disponibili.':exists?'Un preset con questo nome esiste già: salvando ne aggiorni le impostazioni.':'Il preset conserva tutte le impostazioni di questo pannello. Il prompt della richiesta mantiene la priorità.';}
  function open(mode){
   try{if(mode==='save')adapter.read();}catch(e){notify(e.message,true);return;}
   slot.mode=mode;const chosen=slot.group.presets.find(p=>p.id===slot.select.value);if(mode==='delete'&&!chosen)return;
   dialog.querySelector('h2').textContent=(mode==='delete'?'Elimina preset ':'Salva preset ')+label;input.value=chosen?.name||'';input.closest('label').hidden=mode==='delete';error.hidden=true;explain();dialog.showModal();if(mode==='save')input.focus();
  }
  bar.querySelector('[data-save]').onclick=()=>open('save');bar.querySelector('[data-delete]').onclick=()=>open('delete');input.oninput=explain;
  dialog.querySelector('[data-close]').onclick=dialog.querySelector('[data-cancel]').onclick=()=>dialog.close();
  dialog.querySelector('form').onsubmit=async event=>{
   event.preventDefault();if(slot.busy)return;slot.busy=true;submit.disabled=true;error.hidden=true;
   try{
    await flush(slot);
    const body=slot.mode==='delete'?{kind,action:'delete',id:slot.select.value}:{kind,action:'save',name:input.value.trim(),config:adapter.read()};
    const result=await api('/presentation-preferences',body);slot.group=result[kind];if(slot.mode==='save')slot.saved=signature(body.config);draw(slot);if(slot.mode==='save')slot.select.value=slot.group.presets.find(p=>p.name.toLocaleLowerCase()===body.name.toLocaleLowerCase())?.id||'';dialog.close();notify(slot.mode==='delete'?'Preset eliminato.':'Preset salvato.');
   }catch(e){error.textContent=e.message;error.hidden=false;}finally{slot.busy=false;submit.disabled=false;}
  };
  slot.select.onchange=()=>{
   const preset=slot.group.presets.find(p=>p.id===slot.select.value);if(!preset)return;
   applying=true;try{adapter.apply(copy(preset.config));}finally{applying=false;}
   changed(slot);notify('Preset «'+preset.name+'» caricato.');
  };
  document.addEventListener('input',event=>{if(!applying&&adapter.matches(event))changed(slot);});
  document.addEventListener('change',event=>{if(!applying&&adapter.matches(event))changed(slot,true);});
 }
 function draw(slot){
  const value=slot.select.value,items=slot.group.presets;slot.select.replaceChildren(new Option('Ultime impostazioni · personalizzate',''));
  for(const p of items)slot.select.append(new Option(p.name,p.id));
  let current;try{current=signature(slot.adapter.read());}catch{}
  const chosen=items.find(p=>p.id===value&&signature(p.config)===current)||items.find(p=>signature(p.config)===current);slot.select.value=chosen?.id||'';
  const enabled=loaded&&!!getState()?.slide_options?.settings_presets;
  slot.select.disabled=slot.bar.querySelector('[data-save]').disabled=!enabled;slot.bar.querySelector('[data-delete]').disabled=!enabled||!chosen;
 }
 function changed(slot,immediate=false){
  slot.dirty=true;clearTimeout(slot.timer);
  try{slot.pending=copy(slot.adapter.read());slot.status.textContent='Salvataggio automatico…';}catch{slot.pending=null;slot.status.textContent='Completa i campi non validi per salvare le impostazioni.';}
  draw(slot);if(loaded&&slot.pending)slot.timer=setTimeout(()=>flush(slot).catch(()=>{}),immediate?0:350);
 }
 async function flush(slot){
  clearTimeout(slot.timer);if(!loaded)return;
  if(slot.saving){await slot.saving;return flush(slot);}
  const value=slot.pending;if(!value||signature(value)===slot.saved){if(value)slot.status.textContent='Ultime impostazioni salvate automaticamente.';return;}
  slot.pending=null;
  slot.saving=(async()=>{try{
   const result=await api('/presentation-preferences',{kind:slot.kind,action:'last',config:value});slot.group=result[slot.kind];slot.saved=signature(value);slot.status.textContent='Ultime impostazioni salvate automaticamente.';draw(slot);
  }catch(e){if(!slot.pending)slot.pending=value;slot.status.textContent='Impostazioni non salvate: '+e.message;throw e;}finally{slot.saving=null;}})();
  await slot.saving;if(slot.pending&&signature(slot.pending)!==slot.saved)return flush(slot);
 }
 async function restore(){
  if(loaded||loading||!getState()?.slide_options?.settings_presets)return;loading=true;
  try{
   const data=await api('/presentation-preferences');
   applying=true;try{for(const slot of slots.values()){slot.group=data[slot.kind];if(slot.group.last&&!slot.dirty){slot.adapter.apply(copy(slot.group.last));slot.saved=signature(slot.group.last);}slot.status.textContent=slot.group.last?'Ultime impostazioni recuperate.':'Le modifiche vengono salvate automaticamente.';}}finally{applying=false;}
   loaded=true;for(const slot of slots.values()){draw(slot);if(slot.dirty&&slot.pending)flush(slot).catch(()=>{});}
  }catch(e){for(const slot of slots.values())slot.status.textContent='Impostazioni non recuperate: '+e.message;}finally{loading=false;}
 }
 // Browsers may close before the debounce expires. Keep the small settings
 // write alive; never restore the background-only sending mode or chat prompt.
 addEventListener('pagehide',()=>{if(!loaded)return;for(const slot of slots.values()){
  if(!slot.dirty)continue;let config;try{config=slot.adapter.read();}catch{continue;}
  if(signature(config)===slot.saved&&!slot.saving)continue;
  fetch('/api/presentation-preferences',{method:'POST',keepalive:true,headers:{'Content-Type':'application/json','X-H3-Token':getState()?.token||''},body:JSON.stringify({kind:slot.kind,action:'last',config})}).catch(()=>{});
 }});
 return {render(){for(const slot of slots.values()){draw(slot);if(!getState()?.slide_options?.settings_presets)slot.status.textContent='Riavvia H3-Chat a lavori terminati per attivare impostazioni salvate e preset.';}restore();},flush:()=>Promise.all([...slots.values()].map(flush))};
}

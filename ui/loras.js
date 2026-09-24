import {escape as esc} from './render.js';

export function initLoras({api,getState,getChatId,pickDirectory,openPreferences,notify,onChange}){
 const $=s=>document.querySelector(s);let library={items:[],warnings:[]},target='',search='',ticket=0;
 document.body.insertAdjacentHTML('beforeend',`<dialog id="lora-dialog" class="lora-dialog"><header><div class="eyebrow">ADAPTER PER LE IMMAGINI</div><h2>LoRA della chat</h2><p>Seleziona fino a 8 LoRA e regola il peso. Si applicano soltanto alle immagini del modello destinatario e restano in questa chat finché li rimuovi.</p></header><div class="lora-dialog-body"><div class="settings-grid"><label class="field"><span>Modello destinatario</span><select id="lora-target"></select></label><label class="field"><span>Cerca LoRA</span><input id="lora-search" type="search" placeholder="Nome o sottocartella"></label></div><div class="lora-toolbar"><button type="button" id="lora-rescan" class="text-button">Aggiorna elenco</button><button type="button" id="lora-folders" class="text-button">Gestisci cartelle</button></div><p id="lora-status" class="small-note" role="status"></p><div id="lora-list"></div></div><footer><span id="lora-count"></span><button type="button" id="lora-close" class="btn primary">Fine</button></footer></dialog>`);
 const key=id=>'h3.image-loras.'+(id||'new');
 const read=()=>{try{const value=JSON.parse(localStorage.getItem(key(getChatId()))||'[]');return Array.isArray(value)?value.slice(0,8):[];}catch{return [];}};
 const save=items=>{localStorage.setItem(key(getChatId()),JSON.stringify(items));render();onChange?.();};
 const getSelections=()=>read().map(({id,weight,model_id})=>({id,weight,model_id}));
 const modelFamily=m=>m?.id==='sd15'?'sd15':m?.external_config?.profile==='sdxl'?'sdxl':m?.architecture==='qwen-edit'?'qwen-image':m?.architecture;
 const compatible=(l,m)=>!l.family||(modelFamily(m)==='sd'?['sd15','sdxl','sd2'].includes(l.family):l.family===modelFamily(m));
 const safe=fn=>async(...args)=>{try{await fn(...args);}catch(e){notify(e.message,true);}};
 function render(){
  const selected=read(),container=$('#lora-attachments');if(!container||(container.contains(document.activeElement)&&document.activeElement.matches('[data-lora-weight]')))return;
  container.innerHTML=selected.map((l,i)=>`<div class="lora-chip" title="${esc(l.model_name||l.model_id)}"><span class="lora-chip-name">◇ ${esc(l.name||l.id)}</span><label><span class="sr-only">Peso ${esc(l.name||l.id)}</span><input type="number" data-lora-weight="${i}" min="-2" max="2" step="0.1" value="${Number(l.weight)}"></label><small>${esc(l.model_name||'Modello immagini')}</small><button type="button" data-lora-remove="${i}" aria-label="Rimuovi ${esc(l.name||l.id)}">×</button></div>`).join('');
  container.querySelectorAll('[data-lora-remove]').forEach(b=>b.onclick=()=>{const items=read();items.splice(Number(b.dataset.loraRemove),1);save(items);});
  container.querySelectorAll('[data-lora-weight]').forEach(input=>input.onchange=()=>{
   const weight=Number(input.value);if(!input.value||!Number.isFinite(weight)||weight < -2||weight > 2){notify('Peso LoRA tra -2 e 2; 0 lo disattiva.',true);input.blur();render();return;}
   const items=read();items[Number(input.dataset.loraWeight)].weight=weight;input.blur();save(items);
  });
  $('#lora-open').textContent='LoRA'+(selected.length?' · '+selected.length:'');
  $('#lora-count').textContent=selected.length+' / 8 selezionati';
 }
 function renderList(){
  const model=getState()?.models.find(m=>m.id===target),selected=read();
  const items=library.items.filter(l=>(l.name+' '+l.relative).toLowerCase().includes(search.toLowerCase()));
  $('#lora-list').innerHTML=items.map(l=>{const checked=selected.some(s=>s.id===l.id&&s.model_id===target),ok=!!model&&compatible(l,model);return `<label class="lora-item ${ok?'':'incompatible'}"><input type="checkbox" data-lora-id="${esc(l.id)}" ${checked?'checked':''} ${!ok&&!checked?'disabled':''}><span><strong>${esc(l.name)}</strong><small title="${esc(l.path)}">${esc(l.relative)} · ${(l.size/1024**2).toFixed(1)} MiB</small><small>${esc(!ok?'Famiglia incompatibile con questo modello.':l.family?'Famiglia: '+l.family:l.note)}</small></span></label>`;}).join('')||'<p>Nessun LoRA trovato. Collega le cartelle dalle Preferenze e usa file LoRA safetensors.</p>';
  $('#lora-status').textContent=library.warnings.join(' ')||'La famiglia è rilevata dai metadati quando presenti; la compatibilità dei tensori viene verificata dal motore al caricamento.';
  $('#lora-list').querySelectorAll('[data-lora-id]').forEach(box=>box.onchange=()=>{
   let values=read();const id=box.dataset.loraId;
   if(box.checked){if(values.length>=8){box.checked=false;notify('Puoi selezionare fino a 8 LoRA.',true);return;}const item=library.items.find(l=>l.id===id);values.push({id,weight:1,model_id:target,model_name:model.name,name:item.name});}
   else values=values.filter(l=>!(l.id===id&&l.model_id===target));
   save(values);
  });
 }
 async function load(refresh=false){const current=++ticket;$('#lora-status').textContent='Scansione delle cartelle LoRA…';const result=await api('/loras',{refresh});if(current!==ticket||!$('#lora-dialog').open)return;library=result;renderList();}
 async function open(){
  const state=getState(),ids=state.models.filter(m=>m.ready&&m.capabilities.some(c=>['create','edit'].includes(c))).map(m=>m.id);
  const models=ids.map(id=>state.models.find(m=>m.id===id)).filter(Boolean);
  if(!models.length){notify('Scegli prima un modello immagini nel Setup.',true);return;}
  if(!models.some(m=>m.id===target))target=models[0].id;
  $('#lora-target').innerHTML=models.map(m=>`<option value="${esc(m.id)}">${esc(m.name)} · ${[state.settings.create_model===m.id?'creazione':'',state.settings.edit_model===m.id?'editing':''].filter(Boolean).join(' / ')}</option>`).join('');
  $('#lora-target').value=target;search='';$('#lora-search').value='';$('#lora-list').innerHTML='';$('#lora-dialog').showModal();render();await load();
 }
 $('#lora-open').onclick=safe(open);$('#lora-target').onchange=e=>{target=e.target.value;renderList();};$('#lora-search').oninput=e=>{search=e.target.value;renderList();};
 $('#lora-rescan').onclick=safe(()=>load(true));$('#lora-close').onclick=()=>{$('#lora-dialog').close();ticket++;};
 $('#lora-folders').onclick=()=>{$('#lora-dialog').close();ticket++;openPreferences();};
 function renderFolders(container,draft){
  container.innerHTML=`<h3>Cartelle LoRA</h3><p>Collega una o più cartelle, anche su unità diverse. La ricerca include le sottocartelle senza copiare i file. In chat, il pulsante LoRA permette di scegliere adapter e modello destinatario.</p><div id="lora-directory-list"></div><button type="button" id="lora-add-directory" class="btn small">＋ Aggiungi cartella</button><p class="small-note">Salva le Preferenze, poi apri LoRA in chat. Formato: safetensors con coppie LoRA standard. Per i file privi di metadati scegli il modello per cui sono stati addestrati.</p>`;
  const rows=()=>{
   $('#lora-directory-list').innerHTML=(draft.lora_dirs||[]).map((path,i)=>`<div class="lora-directory"><input data-lora-dir="${i}" aria-label="Cartella LoRA ${i+1}" value="${esc(path)}" placeholder="Percorso completo della cartella"><button type="button" class="btn small" data-lora-browse="${i}">Sfoglia</button><button type="button" class="text-button" data-lora-delete="${i}" aria-label="Rimuovi cartella LoRA ${i+1}">×</button></div>`).join('');
   $('#lora-directory-list').querySelectorAll('[data-lora-dir]').forEach(input=>input.oninput=()=>{draft.lora_dirs[Number(input.dataset.loraDir)]=input.value;});
   $('#lora-directory-list').querySelectorAll('[data-lora-browse]').forEach(b=>b.onclick=()=>pickDirectory(draft.lora_dirs[Number(b.dataset.loraBrowse)],path=>{draft.lora_dirs[Number(b.dataset.loraBrowse)]=path;rows();}));
   $('#lora-directory-list').querySelectorAll('[data-lora-delete]').forEach(b=>b.onclick=()=>{draft.lora_dirs.splice(Number(b.dataset.loraDelete),1);rows();});
  };
  rows();$('#lora-add-directory').onclick=()=>{if((draft.lora_dirs||[]).length>=20){notify('Massimo 20 cartelle.',true);return;}pickDirectory('',path=>{draft.lora_dirs=[...new Set([...(draft.lora_dirs||[]),path])];rows();});};
 }
 return {render,getSelections,renderFolders,setSelections:items=>save(items),migrateNew:id=>{const items=read();localStorage.setItem(key(id),JSON.stringify(items));localStorage.removeItem(key(null));}};
}

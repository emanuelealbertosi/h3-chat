import {renderRich,appendMedia,escape as esc,saveBlob} from './render.js';
import {exportPdf,exportDocx,exportPng} from './exports.js';

const $=s=>document.querySelector(s);
let state=null,current=null,chat=null,filter='all',collection=null,attachments=[],settingsTab='setup',settingsDraft=null;
let canvasOpen=false,canvas={title:'Canvas',content:'',media:[]},canvasEditing=false,canvasSaveTimer,canvasDirty=false;
let loading=false,pollTimer,lastSidebar='',lastCanvas='',renderQueue=Promise.resolve();
const drafts=new Map();
const api=async(path,body,method='POST')=>{
  const response=await fetch('/api'+path,{method:body===undefined?'GET':method,headers:body===undefined?{}:{'Content-Type':'application/json','X-H3-Token':state?.token||''},body:body===undefined?undefined:JSON.stringify(body)});
  const data=await response.json();if(!response.ok)throw Error(data.error||'Operazione non riuscita.');return data;
};
function toast(text,error=false){$('#toast').textContent=text;$('#toast').className='show'+(error?' error':'');clearTimeout(toast.timer);toast.timer=setTimeout(()=>$('#toast').className='',5000);}
const act=fn=>(...args)=>{try{return Promise.resolve(fn(...args)).catch(e=>toast(e.message,true));}catch(e){toast(e.message,true);}};
const gb=n=>(n/1e9).toLocaleString('it-IT',{maximumFractionDigits:2})+' GB';
function activeJob(){return state?.jobs.find(j=>j.chat_id===current&&['queued','running'].includes(j.status));}
function modelName(id){return state?.models.find(m=>m.id===id)?.name||'Scegli un modello';}

async function refresh(){
  if(loading)return;loading=true;
  try{
    state=await api('/state');renderSidebar();renderStatus();
    if(current){const id=current;const fresh=await api('/chats/'+id);if(current===id){chat=fresh;await renderChat();}
      if(canvasOpen&&!canvasDirty&&!canvasEditing){const c=await api('/canvas/'+id);if(current===id)await setCanvas(c,false);}}
    updateDownloads();
  }catch(e){if(state)toast(e.message,true);else $('#job-status').textContent='Impossibile connettersi. Avvia H3-Chat.';}
  finally{loading=false;clearTimeout(pollTimer);pollTimer=setTimeout(refresh,state?.jobs.some(j=>['queued','running'].includes(j.status))||state?.downloads.some(d=>d.status==='running')?850:3500);}
}
function renderSidebar(){
  const search=$('#search').value.toLocaleLowerCase();
  const signature=JSON.stringify([state.chats,state.collections,filter,collection,current,search]);if(signature===lastSidebar)return;lastSidebar=signature;
  $('#chat-count').textContent=state.chats.filter(c=>!c.archived).length;
  document.querySelectorAll('[data-filter]').forEach(b=>b.classList.toggle('active',b.dataset.filter===filter&&!collection));
  $('#collections').innerHTML=state.collections.map(c=>`<div class="collection-row"><button data-collection="${c.id}" class="${collection===c.id?'active':''}">▱ ${esc(c.name)}</button><button data-collection-menu="${c.id}" aria-label="Opzioni ${esc(c.name)}">⋯</button></div>`).join('');
  const chats=state.chats.filter(c=>(filter==='archived'?c.archived:!c.archived)&&(filter!=='pinned'||c.pinned)&&(!collection||c.collection_id===collection)&&c.title.toLocaleLowerCase().includes(search));
  $('#list-label').textContent=collection?state.collections.find(c=>c.id===collection)?.name:'CONVERSAZIONI';
  $('#chat-list').innerHTML=chats.map(c=>`<div class="chat-row ${current===c.id?'active':''}"><button class="chat-link" data-chat="${c.id}">${c.pinned?'<span class="pin-mark">⌖</span>':''}${esc(c.title)}</button><button class="chat-options" data-chat-menu="${c.id}" aria-label="Opzioni ${esc(c.title)}">⋯</button></div>`).join('')||'<div class="side-empty">Le tue conversazioni appariranno qui.</div>';
}
function renderStatus(){
  const job=activeJob(),any=state.jobs.some(j=>j.status==='running');
  $('#engine-badge').classList.toggle('busy',any);$('#engine-badge').innerHTML=`<i></i> ${any?'Motore al lavoro':'Motore locale'}`;
  $('#model-name').textContent=modelName(state.settings.chat_model);
  $('#job-status').textContent=job?job.stage:chat?.archived?'Conversazione archiviata. Ripristinala per continuare.':canvasOpen?'Destinazione: canvas · nella chat solo il messaggio di accompagnamento.':'';
  $('#send').hidden=!!job;$('#stop').hidden=!job;$('#prompt').disabled=!!chat?.archived;
  $('#setup-nudge').hidden=state.settings.setup_done&&!!state.models.find(m=>m.id===state.settings.chat_model)?.ready;
  $('#chat-title').textContent=chat?.title||'Una nuova conversazione';
  $('#canvas-source').readOnly=!!job?.canvas;
  $('#canvas-title').readOnly=!!job?.canvas;
}
async function newChat(){if(current)await persistCanvas();const fresh=await api('/chats',{collection_id:collection});await openChat(fresh.id);await refresh();$('#prompt').focus();}
async function openChat(id){
  if(current){drafts.set(current,{prompt:$('#prompt').value,attachments:[...attachments]});await persistCanvas();}
  current=id;chat=await api('/chats/'+id);$('#messages').innerHTML='';
  const draft=drafts.get(id)||{prompt:'',attachments:[]};$('#prompt').value=draft.prompt;attachments=draft.attachments;renderAttachments();
  canvasDirty=false;lastCanvas='';canvasEditing=false;await setCanvas(await api('/canvas/'+id));
  renderSidebar();renderStatus();await renderChat();$('#sidebar').classList.remove('visible');
  $('#scroll-area').scrollTop=$('#scroll-area').scrollHeight;
}
async function renderChat(){
  $('#welcome').hidden=!!chat?.messages.length;
  if(!chat)return;
  const scroll=$('#scroll-area'),atBottom=scroll.scrollHeight-scroll.scrollTop-scroll.clientHeight<130;
  for(const message of chat.messages){
    let article=document.getElementById('msg-'+message.id);const signature=JSON.stringify([message.content,message.status,message.media,message.meta]);
    if(article?.dataset.signature===signature)continue;
    if(!article){article=document.createElement('article');article.id='msg-'+message.id;article.className='message '+message.role;$('#messages').append(article);}
    article.dataset.signature=signature;
    article.innerHTML=`<div class="message-head">${message.role==='user'?'<span class="user-avatar">TU</span>':'<img src="/static/icon.svg" alt="">'}<strong>${message.role==='user'?'Tu':'H3 Chat'}</strong><span>${message.meta.model?esc(message.meta.model):''}</span>${message.meta.canvas?'<span class="badge">Canvas</span>':''}</div><div class="message-content ${message.role==='assistant'?'rich':''}"></div><div class="message-actions"></div>`;
    const content=article.querySelector('.message-content');
    if(message.role==='user')content.textContent=message.content;
    else if(message.content)await renderRich(content,message.content,{final:message.status==='done'});
    else if(['queued','running'].includes(message.status))content.innerHTML='<div class="thinking" aria-label="Elaborazione in corso"><i></i><i></i><i></i></div>';
    appendMedia(content,message.media);
    if(['failed','interrupted','cancelled'].includes(message.status)){const err=document.createElement('div');err.className='message-error';err.textContent=message.meta.error||'Risposta interrotta. Puoi riprovare.';content.append(err);}
    const actions=article.querySelector('.message-actions');
    if(message.content){const copy=document.createElement('button');copy.className='text-button';copy.textContent='Copia';copy.onclick=act(async()=>{await navigator.clipboard.writeText(message.content);toast('Copiato.');});actions.append(copy);}
    if(message.role==='assistant'&&message.status==='done'){
      const toCanvas=document.createElement('button');toCanvas.className='text-button';toCanvas.textContent=message.meta.canvas?'Apri canvas':'Apri nel canvas';toCanvas.onclick=act(async()=>{if(!message.meta.canvas||message.meta.artifact){if(canvas.content||canvas.media.length){if(!await ask('Sostituire il canvas?',{description:'Il contenuto attuale verrà sostituito da questa risposta.',confirm:true}))return;}await setCanvas(message.meta.artifact||{title:chat.title,content:message.content,media:message.media});canvasDirty=true;await persistCanvas();}await toggleCanvas(true);});actions.append(toCanvas);
      if(message.meta.finish_reason==='length'){const note=document.createElement('span');note.textContent='Limite di risposta raggiunto';actions.append(note);}
    }
    if(message.role==='user'){const repeat=document.createElement('button');repeat.className='text-button';repeat.textContent='Riutilizza';repeat.onclick=()=>{$('#prompt').value=message.content;attachments=[...message.media];renderAttachments();$('#prompt').focus();};actions.append(repeat);}
  }
  if(atBottom)scroll.scrollTop=scroll.scrollHeight;
}
function renderAttachments(){$('#attachments').innerHTML=attachments.map((m,i)=>`<div class="attachment"><img src="/media/${esc(m.path)}" alt="${esc(m.name)}"><small>Riferimento ${i+1}</small><button data-remove-attachment="${i}" aria-label="Rimuovi riferimento ${i+1}">×</button></div>`).join('');}
async function uploadFiles(files){
  if(attachments.length+files.length>4)throw Error('Puoi allegare fino a quattro immagini.');
  for(const file of files){
    if(!['image/png','image/jpeg','image/webp'].includes(file.type))throw Error('Scegli immagini PNG, JPEG o WebP.');
    if(file.size>12*1024*1024)throw Error('Ogni immagine può occupare fino a 12 MB.');
    const bitmap=await createImageBitmap(file);if(Math.max(bitmap.width,bitmap.height)>8192){bitmap.close();throw Error('Immagine troppo grande: massimo 8192 pixel.');}
    let source=file;
    if(file.type==='image/webp'){const c=document.createElement('canvas');c.width=bitmap.width;c.height=bitmap.height;c.getContext('2d').drawImage(bitmap,0,0);source=await new Promise(r=>c.toBlob(r,'image/png'));}
    bitmap.close();
    const data=await new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(reader.result.split(',')[1]);reader.onerror=reject;reader.readAsDataURL(source);});
    attachments.push(await api('/uploads',{name:file.name,data}));renderAttachments();
  }
}
async function send(event){event.preventDefault();if(activeJob())return;const prompt=$('#prompt').value.trim();if(!prompt)return;
  $('#send').disabled=true;
  try{if(!current){const fresh=await api('/chats',{collection_id:collection});current=fresh.id;chat=fresh;}
    await persistCanvas();await api('/chats/'+current+'/messages',{prompt,media:attachments,canvas:canvasOpen});
    $('#prompt').value='';attachments=[];renderAttachments();drafts.delete(current);await refresh();
  }finally{$('#send').disabled=false;}
}

async function ask(title,{value='',description='',confirm=false,options=null}={}){
  const dialog=$('#entry-dialog');$('#entry-title').textContent=title;$('#entry-description').textContent=description;
  $('#entry-input').hidden=confirm||!!options;$('#entry-input').value=value;$('#entry-select').hidden=!options;
  if(options){$('#entry-select').innerHTML=options.map(o=>`<option value="${esc(o.value)}">${esc(o.label)}</option>`).join('');$('#entry-select').value=value;}
  dialog.returnValue='';dialog.showModal();if(!confirm&&!options)$('#entry-input').focus();
  return new Promise(resolve=>dialog.addEventListener('close',()=>resolve(dialog.returnValue==='ok'?(confirm?true:options?$('#entry-select').value:$('#entry-input').value.trim()):null),{once:true}));
}
function menuAt(button,items){const menu=$('#context-menu');menu.innerHTML='';for(const item of items){const b=document.createElement('button');b.textContent=item.label;if(item.danger)b.className='danger';b.onclick=act(async()=>{menu.hidden=true;await item.action();});menu.append(b);}menu.hidden=false;const rect=button.getBoundingClientRect();menu.style.left=Math.min(rect.left,window.innerWidth-205)+'px';menu.style.top=Math.min(rect.bottom+5,window.innerHeight-menu.offsetHeight-12)+'px';}
function chatMenu(id,button){const c=state.chats.find(c=>c.id===id);if(!c)return;
  const patch=async body=>{await api('/chats/'+id,body,'PATCH');await refresh();};
  menuAt(button,[{label:'Rinomina',action:async()=>{const title=await ask('Rinomina chat',{value:c.title});if(title)await patch({title});}},
    {label:c.pinned?'Rimuovi dai pin':'Metti in evidenza',action:()=>patch({pinned:!c.pinned})},
    {label:'Sposta in una raccolta',action:async()=>{const dest=await ask('Scegli raccolta',{value:c.collection_id||'',options:[{value:'',label:'Nessuna raccolta'},...state.collections.map(x=>({value:x.id,label:x.name}))]});if(dest!==null)await patch({collection_id:dest||null});}},
    {label:c.archived?'Ripristina chat':'Archivia chat',action:()=>patch({archived:!c.archived})},
    {label:'Esporta conversazione',action:async()=>{const data=await api('/chats/'+id);saveBlob(new Blob([JSON.stringify(data,null,2)],{type:'application/json'}),'chat.json');}},
    {label:'Elimina chat',danger:true,action:async()=>{if(await ask('Eliminare questa chat?',{description:'Messaggi e canvas saranno eliminati. Gli allegati restano sul disco se usati in altre conversazioni.',confirm:true})){await api('/chats/'+id,{},'DELETE');if(current===id){current=null;chat=null;$('#messages').innerHTML='';$('#welcome').hidden=false;await setCanvas({title:'Canvas',content:'',media:[]});}await refresh();}}}]);
}
function collectionMenu(id,button){const c=state.collections.find(c=>c.id===id);menuAt(button,[{label:'Rinomina raccolta',action:async()=>{const name=await ask('Rinomina raccolta',{value:c.name});if(name){await api('/collections/'+id,{name},'PATCH');await refresh();}}},{label:'Elimina raccolta',danger:true,action:async()=>{if(await ask('Eliminare la raccolta?',{description:'Le conversazioni restano disponibili in Tutte le chat.',confirm:true})){await api('/collections/'+id,{},'DELETE');if(collection===id)collection=null;await refresh();}}}]);}

async function toggleCanvas(value=!canvasOpen){canvasOpen=value;$('#canvas-panel').hidden=!value;$('#workspace').classList.toggle('has-canvas',value);$('#canvas-toggle').setAttribute('aria-pressed',value);$('#canvas-follow').checked=value;
  if(value&&current&&!canvasDirty)await setCanvas(await api('/canvas/'+current),true);if(value)await renderCanvas();renderStatus();}
async function setCanvas(value,force=true){const signature=JSON.stringify([value.title,value.content,value.media]);if(!force&&signature===lastCanvas)return;canvas={title:value.title||'Canvas',content:value.content||'',media:value.media||[]};lastCanvas=signature;$('#canvas-title').value=canvas.title;$('#canvas-source').value=canvas.content;await renderCanvas();}
async function renderCanvas(){
  const empty=!canvas.content&&!canvas.media.length;$('#canvas-empty').hidden=!empty||canvasEditing;$('#canvas-preview').hidden=canvasEditing||empty;$('#canvas-source').hidden=!canvasEditing;
  $('#canvas-preview-tab').classList.toggle('active',!canvasEditing);$('#canvas-source-tab').classList.toggle('active',canvasEditing);
  if(!canvasEditing){const value={...canvas,media:[...canvas.media]};renderQueue=renderQueue.then(async()=>{await renderRich($('#canvas-preview'),value.content,{final:!activeJob()?.canvas});appendMedia($('#canvas-preview'),value.media);});await renderQueue;}
}
async function persistCanvas(){clearTimeout(canvasSaveTimer);if(!canvasDirty)return;if(!current){const fresh=await api('/chats',{});current=fresh.id;chat=fresh;}
  const id=current,value={...canvas};await api('/canvas/'+id,value,'PUT');canvasDirty=false;$('#canvas-save-status').textContent='Salvato sul computer';}
function canvasChanged(){canvas.title=$('#canvas-title').value;canvas.content=$('#canvas-source').value;canvasDirty=true;$('#canvas-save-status').textContent='Modifiche da salvare';clearTimeout(canvasSaveTimer);canvasSaveTimer=setTimeout(act(persistCanvas),800);}

function collectSettings(){for(const field of $('#settings-body').querySelectorAll('[data-setting]')){const key=field.dataset.setting;settingsDraft[key]=field.type==='number'?Number(field.value):field.type==='checkbox'?field.checked:field.value;}}
function options(items,value){return items.map(([id,label])=>`<option value="${id}" ${id===value?'selected':''}>${esc(label)}</option>`).join('');}
function settingSelect(key,label,items,hint=''){return `<label class="field"><span>${label}</span><select data-setting="${key}">${options(items,settingsDraft[key])}</select>${hint?`<small>${hint}</small>`:''}</label>`;}
function numberField(key,label,min,max,step=1){return `<label class="field"><span>${label}</span><input type="number" data-setting="${key}" value="${settingsDraft[key]}" min="${min}" max="${max}" step="${step}"></label>`;}
async function openSettings(tab='setup'){settingsDraft={...state.settings};settingsTab=tab;$('#settings').showModal();renderSettings();
  try{const h=await api('/hardware');const note=$('#hardware-info');if(note)note.textContent=h.gpu.length?h.gpu.map(g=>`${g.name} · ${(g.total_mb/1024).toFixed(1)} GB VRAM · ${(g.free_mb/1024).toFixed(1)} GB liberi`).join(' / '):`${h.cpu_threads} thread CPU · Vulkan per NVIDIA, AMD e Intel con driver compatibili.`;}catch{}
}
function renderSettings(){
  document.querySelectorAll('[data-tab]').forEach(b=>b.classList.toggle('active',b.dataset.tab===settingsTab));
  const body=$('#settings-body');
  if(settingsTab==='setup'){
    const modelSelect=(key,label,cap)=>settingSelect(key,label,[['','Scegli dal catalogo…'],...state.models.filter(m=>m.capabilities.includes(cap)).map(m=>[m.id,m.name+(m.ready?'':' · da scaricare')])]);
    body.innerHTML=`<div class="hardware-note" id="hardware-info">Scegli l'hardware. CPU, NVIDIA, AMD e Intel condividono la stessa interfaccia.</div><div class="settings-grid"><section class="card"><h3>01 · Il tuo computer</h3>${settingSelect('profile','Profilo memoria',[['cpu','Solo CPU / nessuna GPU'],['low','GPU · 4–8 GB VRAM'],['balanced','GPU · 12–24 GB VRAM']],'Il profilo imposta valori iniziali modificabili nelle Preferenze.')}${settingSelect('backend','Motore di calcolo',[['cpu','CPU · massima compatibilità'],['vulkan','Vulkan · NVIDIA / AMD / Intel'],['cuda','CUDA · NVIDIA']],'Il profilo Solo CPU usa sempre il backend CPU.')}<div class="runtime-actions"><button id="install-runtime" class="btn">Installa motori</button><span class="small-note" id="runtime-ready"></span></div><div id="runtime-downloads"></div></section><section class="card"><h3>02 · I tuoi modelli</h3>${modelSelect('chat_model','Chat, router e visione','chat')}${modelSelect('create_model','Creazione immagini','create')}${modelSelect('edit_model','Modifica e riferimenti','edit')}<p>Un'unica chat. Il router sceglie cosa fare dal prompt; viene caricato un solo motore alla volta.</p><button id="go-catalog" class="text-button">Apri il catalogo e scarica i componenti →</button></section></div><div class="note">Con 4–8 GB scegli modelli quantizzati e pochi riferimenti. FLUX usa anche la RAM di sistema; CPU e offload riducono la VRAM ma aumentano i tempi. Il video sarà aggiunto in una versione futura.</div>`;
    $('#install-runtime').onclick=act(async()=>{collectSettings();const backend=settingsDraft.profile==='cpu'?'cpu':settingsDraft.backend;await api('/downloads',{id:backend,kind:'runtime'});await refresh();});
    $('#go-catalog').onclick=()=>{collectSettings();settingsTab='models';renderSettings();};
    body.querySelector('[data-setting="profile"]').onchange=e=>{collectSettings();Object.assign(settingsDraft,state.profiles[e.target.value]);if(e.target.value==='cpu')settingsDraft.backend='cpu';renderSettings();};
    body.querySelector('[data-setting="backend"]').onchange=()=>{collectSettings();updateDownloads();};
  }else if(settingsTab==='models'){
    body.innerHTML='<p class="small-note">I download includono pesi, encoder, proiettori e VAE richiesti. Ogni file viene verificato con SHA-256; un download interrotto può essere ripreso.</p>'+state.models.map(m=>`<article class="model-card"><div class="model-top"><h3>${esc(m.name)}</h3><button class="btn small" data-download="${m.id}">${m.ready?'Verificato':'Scarica · '+gb(m.size)}</button></div><p>${esc(m.description)}</p><div class="model-meta">${m.capabilities.map(c=>`<span class="badge">${({chat:'CHAT',vision:'VISION',create:'CREA',edit:'MODIFICA'})[c]}</span>`).join('')}<span class="badge">${m.max_refs?m.max_refs+' riferimenti':'Testo'}</span><span class="badge">RAM indicativa ≥ ${m.ram_gb} GB</span><span class="badge ${m.ready?'ready':''}" id="ready-${m.id}">${m.ready?'Installato':'Non installato'}</span></div><details><summary>Componenti e licenza</summary><p>${esc(m.license)}</p>${m.files.map(f=>`<div class="component"><span>${esc(f.role)} · <a href="https://huggingface.co/${esc(f.repo)}/blob/${f.revision}/${esc(f.filename)}" target="_blank" rel="noopener noreferrer">${esc(f.filename)}</a></span><span>${gb(f.size)}</span></div>`).join('')}</details><div data-download-status="${m.id}"></div></article>`).join('');
    body.querySelectorAll('[data-download]').forEach(b=>{const model=state.models.find(m=>m.id===b.dataset.download);b.disabled=model.ready;b.onclick=act(async()=>{await api('/downloads',{id:model.id,kind:'model'});await refresh();});});
  }else{
    body.innerHTML=`<div class="settings-grid"><section class="card"><h3>Chat e memoria</h3><div class="settings-grid">${numberField('context','Contesto (token)',1024,32768,1024)}${numberField('max_tokens','Risposta massima',64,8192,64)}${numberField('gpu_layers','Layer su GPU',0,999)}${numberField('threads','Thread CPU',1,64)}${numberField('temperature','Temperatura',0,2,0.1)}</div></section><section class="card"><h3>Immagini</h3><div class="settings-grid">${numberField('width','Larghezza (px)',256,1536,64)}${numberField('height','Altezza (px)',256,1536,64)}${numberField('steps','Passi (modelli standard)',1,100)}${numberField('strength','Intensità img2img',0.05,1,0.05)}</div><p>FLUX.2 klein usa i suoi 4 passi. Batch singolo, VAE a tasselli e rilascio dei processi dopo ogni richiesta.</p></section><section class="card full"><h3>Come vuoi che risponda</h3><label class="field"><span>Istruzioni personali</span><textarea data-setting="system_prompt">${esc(settingsDraft.system_prompt)}</textarea></label><p>Codice evidenziato, Markdown, LaTeX, diagrammi Mermaid e grafici numerici sono già abilitati. Il canvas esporta Word modificabile e PDF/PNG fedeli all'anteprima; formule e figure nel Word sono immagini.</p></section></div>`;
  }
  updateDownloads();
}
function updateDownloads(){
  if(!$('#settings').open)return;
  const progress=task=>`<div class="download-status ${task.status==='failed'?'error':''}"><span>${task.status==='running'?esc(task.file.split('/').pop()):({done:'Download completato e verificato',failed:esc(task.error),cancelled:'Interrotto · premi Scarica per riprendere'})[task.status]}</span>${task.status==='running'?`<progress max="${task.total||1}" value="${task.received}"></progress><span>${gb(task.received)} / ${gb(task.total)}</span> <button class="text-button" data-cancel-download="${task.id}">Interrompi</button>`:''}</div>`;
  for(const div of document.querySelectorAll('[data-download-status]')){const task=state.downloads.find(t=>t.id===div.dataset.downloadStatus);div.innerHTML=task?progress(task):'';}
  for(const m of state.models){const ready=document.getElementById('ready-'+m.id);if(ready){ready.textContent=m.ready?'Installato':'Non installato';ready.classList.toggle('ready',m.ready);}const b=document.querySelector(`[data-download="${m.id}"]`);if(b){b.disabled=m.ready||state.downloads.some(t=>t.status==='running');b.textContent=m.ready?'Verificato':'Scarica · '+gb(m.size);}}
  const backend=settingsDraft?.profile==='cpu'?'cpu':settingsDraft?.backend;
  if($('#runtime-ready')){$('#runtime-ready').textContent=state.runtimes[backend]?.ready?'Motori installati':gb(state.runtimes[backend]?.size||0);$('#install-runtime').disabled=state.downloads.some(t=>t.status==='running');}
  if($('#runtime-downloads'))$('#runtime-downloads').innerHTML=state.downloads.filter(d=>d.kind==='runtime').map(progress).join('');
  document.querySelectorAll('[data-cancel-download]').forEach(b=>b.onclick=act(async()=>{await api('/downloads/'+b.dataset.cancelDownload+'/cancel',{});await refresh();}));
}

$('#composer').onsubmit=act(send);
$('#prompt').onkeydown=act(async e=>{if(e.key==='Enter'&&!e.shiftKey&&!e.isComposing){e.preventDefault();await send(e);}});
$('#prompt').oninput=()=>{$('#prompt').style.height='auto';$('#prompt').style.height=Math.min(180,$('#prompt').scrollHeight)+'px';};
$('#stop').onclick=act(async()=>{const j=activeJob();if(j){await api('/jobs/'+j.id+'/cancel',{});await refresh();}});
$('#new-chat').onclick=act(newChat);$('#home').onclick=act(async e=>{e.preventDefault();await newChat();});
$('#search').oninput=renderSidebar;
document.querySelectorAll('[data-filter]').forEach(b=>b.onclick=()=>{filter=b.dataset.filter;collection=null;renderSidebar();});
$('#new-collection').onclick=act(async()=>{const name=await ask('Nuova raccolta');if(name){await api('/collections',{name});await refresh();}});
$('#chat-list').onclick=act(async e=>{const open=e.target.closest('[data-chat]'),menu=e.target.closest('[data-chat-menu]');if(open)await openChat(open.dataset.chat);if(menu)chatMenu(menu.dataset.chatMenu,menu);});
$('#collections').onclick=act(async e=>{const open=e.target.closest('[data-collection]'),menu=e.target.closest('[data-collection-menu]');if(open){collection=open.dataset.collection;filter='all';renderSidebar();}if(menu)collectionMenu(menu.dataset.collectionMenu,menu);});
$('#chat-menu').onclick=()=>{if(current)chatMenu(current,$('#chat-menu'));};
document.addEventListener('click',e=>{if(!e.target.closest('#context-menu,[data-chat-menu],[data-collection-menu],#chat-menu'))$('#context-menu').hidden=true;});
document.addEventListener('keydown',e=>{if((e.ctrlKey||e.metaKey)&&e.key.toLowerCase()==='k'){e.preventDefault();act(newChat)();}if(e.key==='Escape'){$('#context-menu').hidden=true;$('#sidebar').classList.remove('visible');}});
$('#mobile-nav').onclick=()=>$('#sidebar').classList.toggle('visible');
$('#attach').onclick=()=>$('#file-input').click();$('#file-input').onchange=act(async e=>{await uploadFiles([...e.target.files]);e.target.value='';});
$('#attachments').onclick=e=>{const b=e.target.closest('[data-remove-attachment]');if(b){attachments.splice(Number(b.dataset.removeAttachment),1);renderAttachments();}};
$('#composer').ondragover=e=>{e.preventDefault();$('#composer').classList.add('dragging');};$('#composer').ondragleave=()=>$('#composer').classList.remove('dragging');
$('#composer').ondrop=act(async e=>{e.preventDefault();$('#composer').classList.remove('dragging');await uploadFiles([...e.dataTransfer.files]);});
$('#prompt').addEventListener('paste',act(async e=>{const files=[...e.clipboardData.files];if(files.length){e.preventDefault();await uploadFiles(files);}}));
document.querySelectorAll('[data-prompt]').forEach(b=>b.onclick=()=>{$('#prompt').value=b.dataset.prompt;$('#prompt').focus();});
$('#settings-open').onclick=()=>openSettings();$('#setup-nudge').onclick=()=>openSettings();$('#settings-close').onclick=()=>$('#settings').close();
document.querySelectorAll('[data-tab]').forEach(b=>b.onclick=()=>{collectSettings();settingsTab=b.dataset.tab;renderSettings();});
$('#settings-save').onclick=act(async()=>{collectSettings();settingsDraft.setup_done=true;await api('/settings',settingsDraft);toast('Impostazioni salvate.');$('#settings').close();await refresh();});
$('#canvas-toggle').onclick=act(()=>toggleCanvas());$('#canvas-close').onclick=act(()=>toggleCanvas(false));
$('#canvas-follow').onchange=act(()=>toggleCanvas($('#canvas-follow').checked));
$('#canvas-preview-tab').onclick=act(async()=>{canvasEditing=false;await persistCanvas();await renderCanvas();});
$('#canvas-source-tab').onclick=act(async()=>{if(activeJob()?.canvas)throw Error('Attendi la scrittura del motore prima di modificare.');canvasEditing=true;await renderCanvas();$('#canvas-source').focus();});
$('#canvas-write').onclick=$('#canvas-source-tab').onclick;
$('#canvas-title').oninput=canvasChanged;$('#canvas-source').oninput=canvasChanged;$('#canvas-save').onclick=act(async()=>{await persistCanvas();toast('Canvas salvato.');});
document.querySelectorAll('[data-export]').forEach(b=>b.onclick=act(async()=>{if(activeJob()?.canvas)throw Error('Attendi che il documento sia completo prima di esportare.');await persistCanvas();if(!canvas.content&&!canvas.media.length)throw Error('Il canvas è vuoto.');canvasEditing=false;await renderCanvas();const root=$('#canvas-preview');$('#canvas-panel').classList.add('exporting');try{if(b.dataset.export==='md')saveBlob(new Blob([canvas.content],{type:'text/markdown;charset=utf-8'}),canvas.title+'.md');if(b.dataset.export==='pdf')await exportPdf(root,canvas.title,state.token);if(b.dataset.export==='docx')await exportDocx(root,canvas.title);if(b.dataset.export==='png')await exportPng(root,canvas.title);toast('Esportazione pronta.');}finally{$('#canvas-panel').classList.remove('exporting');}}));
await refresh();
window.addEventListener('beforeunload',e=>{if(canvasDirty){e.preventDefault();e.returnValue='';}});

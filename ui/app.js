import {renderToolsSettings,appendToolsDetails} from './tools-settings.js';
import {renderProviders} from './api-providers.js';
import {renderLlmPreferences,selectLlmPreferencesModel,syncLlmDraft,llmOptions} from './llm-settings.js';
import {renderVideoSettings,appendVideoDetails,selectVideoPreferencesModel} from './video-settings.js';
import {chatActivities,chatActivityIcon} from './chat-activity.js';
import {renderMusicSettings,appendMusicDetails,selectMusicPreferencesModel} from './music-settings.js';
import {renderRich,appendMedia,escape as esc,saveBlob} from './render.js';
import {exportPdf,exportDocx,exportPng} from './exports.js';
import {initLocalModels} from './local-models.js';
import {initLoras} from './loras.js';
import {initVisualControls,renderVisualSetup} from './visual-controls.js';
import {renderImagePreferences,selectImagePreferencesModel} from './image-settings.js';
import {initProjects} from './projects.js';
import {renderWorkspaceSettings} from './workspace-settings.js';
import {renderMediaProviders,renderServer} from './media-providers.js';
import {modelLabel,modelIdentityHtml,initModelIdentity} from './model-identity.js';
import {initChatModels} from './chat-models.js';
import {renderVoiceSettings} from './voice.js';
import {readDeck,renderSlides,exportSlides,transferSlideView} from './slides.js';
import {initSlideImages} from './slide-ai.js';
import {initComposerPanel} from './composer-panel.js';
import {initManimPresentation} from './manim-presentation.js';
import {initWorkspaceLayout} from './workspace-layout.js';

const $=s=>document.querySelector(s);
let composerUI=null,manimPresentation=null;
let state=null,current=null,chat=null,filter='all',collection=null,project=null,attachments=[],settingsTab='setup',settingsDraft=null;
let canvasOpen=false,canvas={title:'Canvas',content:'',media:[]},canvasEditing=false,canvasSaveTimer,canvasDirty=false;
let canvasHistory={items:[],active_id:null},canvasFollow=true,canvasSaving=null,canvasSelection=0,canvasHistoryRequest=0;
let loading=false,pollTimer,lastSidebar='',lastCanvas='',renderQueue=Promise.resolve();
const drafts=new Map();
let assessmentTimer,assessmentRequest=0,lastAssessment=0,thinkSaving=false;
let chatModels;
const api=async(path,body,method='POST')=>{
  const modelRevision=chatModels?.revision();
  const response=await fetch('/api'+path,{cache:'no-store',method:body===undefined?'GET':method,headers:body===undefined?{}:{'Content-Type':'application/json','X-H3-Token':state?.token||''},body:body===undefined?undefined:JSON.stringify(body)});
  const data=await response.json();if(!response.ok)throw Error(data.error||'Operazione non riuscita.');return path==='/state'&&chatModels?chatModels.reconcile(data,modelRevision):data;
};
function toast(text,error=false){
  const notice=$('#toast');
  const host=document.activeElement?.closest('dialog[open]')||[...document.querySelectorAll('dialog:modal')].at(-1)||document.body;
  host.append(notice);notice.textContent=text;notice.className='show'+(error?' error':'');
  clearTimeout(toast.timer);toast.timer=setTimeout(()=>notice.className='',5000);
}
// Native modal dialogs live above body content, including any z-index.
document.addEventListener('close',e=>{if(e.target.contains?.($('#toast'))){
  const host=[...document.querySelectorAll('dialog:modal')].at(-1)||document.body;host.append($('#toast'));
}},true);
function settingsError(message=''){
  const box=$('#settings-error');box.textContent=message?'Impostazioni non salvate. '+message:'';box.hidden=!message;
  if(message)box.focus();
}
const act=fn=>(...args)=>{try{return Promise.resolve(fn(...args)).catch(e=>toast(e.message,true));}catch(e){toast(e.message,true);}};
initModelIdentity({getModel:()=>state?.models.find(m=>m.id===state.settings.chat_model),act,notify:toast});
const gb=n=>(n/1e9).toLocaleString('it-IT',{maximumFractionDigits:2})+' GB';
const visualControls=initVisualControls({getState:()=>state,getChatId:()=>current});
const localModels=initLocalModels({api,getState:()=>state,notify:toast,onChange:async(model,removed)=>{
  collectSettings();state=await api('/state');
  if(model)for(const [key,cap] of [['chat_model','chat'],['create_model','create'],['edit_model','edit'],['diagram_model','create'],['music_model','music'],['video_model','video']])if(settingsDraft[key]===model.id&&!model.capabilities.includes(cap))settingsDraft[key]='';
  if(removed)for(const key of ['chat_model','create_model','edit_model','diagram_model','music_model','video_model'])if(settingsDraft[key]===removed)settingsDraft[key]='';
  if(model&&settingsDraft.diagram_model===model.id&&model.architecture!=='ming')settingsDraft.diagram_model='';
  if(model?.architecture==='minimax-h3'&&!settingsDraft.video_model)settingsDraft.video_model=model.id;
  if(model?.architecture==='yue2')settingsDraft.music_model=model.id;
  if(model?.architecture==='ming'&&!settingsDraft.diagram_model)settingsDraft.diagram_model=model.id;
  renderSettings();renderStatus();
}});
const loraUI=initLoras({api,getState:()=>state,getChatId:()=>current,pickDirectory:(path,callback)=>localModels.pickDirectory(path,callback),openPreferences:()=>openSettings('advanced'),notify:toast,onChange:()=>scheduleAssessment()});
const projects=initProjects({api,getState:()=>state,getChat:()=>chat,refresh,notify:toast,act,select:act(async id=>{project=id;collection=null;filter='all';lastSidebar='';renderSidebar();if(id&&chat?.project_id!==id){const existing=state.chats.find(c=>c.project_id===id&&!c.archived);if(existing)await openChat(existing.id);else await newChat();}}),showCanvas:value=>value===null?($('#canvas-panel').hidden=!canvasOpen,$('#workspace').classList.toggle('has-canvas',canvasOpen)):toggleCanvas(value),pickDirectory:(path,callback)=>localModels.pickDirectory(path,callback)});
chatModels=initChatModels({api,getState:()=>state,notify:toast,onChange:settings=>{if(settings)state.settings=settings;renderStatus();}});
$('#rag-enabled').closest('label').insertAdjacentHTML('afterend','<label class="think-control">Strumenti <select id="lab-tool" aria-label="Strumenti della chat"><option value="auto">Automatico · dal prompt</option><option value="calculate">Interprete numerico</option><option value="manim">Animazione Manim</option><option value="slides">Slide · HTML in tempo reale</option></select></label><span id="slides-options" hidden><label>Slide <input id="slides-count" aria-label="Numero di slide" type="number" min="1" max="30" value="8" style="width:65px"></label> <label>Formato <select id="slides-format" aria-label="Formato slide"><option>16:9</option><option>4:3</option><option>16:10</option><option>1:1</option></select></label></span>');
$('#lab-tool').onchange=()=>{manimPresentation?.render();$('#slides-options').hidden=$('#lab-tool').value!=='slides';visualControls.render();};
$('#slides-options').insertAdjacentHTML('beforeend',' <label>Motore <select id="slides-engine" aria-label="Motore slide"><option value="llm">LLM · HTML libero</option><option value="deterministic">Deterministico</option></select></label> <label>Stile <select id="slides-design"><option value="professional">Serio / professionale</option><option value="playful">Giocoso / colorato</option><option value="comic">Fumettoso</option></select></label> <label>Contenuto <select id="slides-detail"><option value="concise">Sintesi</option><option value="full">Testi completi</option></select></label>');
$('#slides-options').insertAdjacentHTML('beforeend',' <label title="Rapida analizza fino a 8 figure nuove, dando precedenza alle fonti della richiesta. Le descrizioni già disponibili vengono riutilizzate; tutte le figure restano inseribili.">Figure Vision <select id="slides-vision" aria-label="Analisi figure slide"><option value="relevant">Rapida · max 8 nuove</option><option value="all">Completa · tutte</option></select></label>');
const slideImages=initSlideImages();
async function executeArtifact(lang,source){if(activeJob())throw Error('Attendi o interrompi il lavoro corrente.');if(!current)await newChat();await api('/chats/'+current+'/messages',{prompt:lang.startsWith('manim')?'Renderizza questa scena Manim':'Esegui questo calcolo con l’interprete',lab:lang.startsWith('manim')?'manim':'calculate',lab_source:source,canvas:canvasOpen,...projects.read()});await refresh();}
function localCard(model){
  const m=model;
  return `<article class="model-card" data-external-card="${m.id}"><div class="model-top"><h3>${esc(modelLabel(m))}</h3><div class="model-link-actions"><button type="button" class="btn small" data-model-parameters="${m.id}">Parametri del modello</button><button type="button" class="btn small" data-edit-external="${m.id}">Modifica collegamento</button><button type="button" class="text-button" data-remove-external="${m.id}">Scollega</button></div></div><p>${esc(m.description)}</p>${modelIdentityHtml(m)}<div class="model-meta"><span class="badge">PERCORSO ESTERNO</span><span class="badge ${m.ready?'ready':'warning'}">${m.ready?'Disponibile':'Non disponibile'}</span>${m.vision?`<span class="badge ${m.vision.enabled?'ready':'warning'}">${m.vision.enabled?'Vision attiva':'Non vision'}</span>`:''}${m.thinking?.supported?'<span class="badge">THINK</span>':''}${m.mtp?.supported?'<span class="badge">MTP</span>':''}${m.capabilities.map(c=>`<span class="badge">${({chat:'CHAT',create:'CREA',edit:'MODIFICA',music:'MUSICA',video:'VIDEO'})[c]||esc(c)}</span>`).join('')}</div>${m.external_problems?.length?`<p class="local-error">${esc(m.external_problems.join(' '))}</p>`:''}${m.vision?.warning?`<p class="small-note">${esc(m.vision.warning)}</p>`:''}<details><summary>Percorsi collegati e componenti</summary>${m.files.map(f=>`<div class="external-path"><strong>${esc(state.model_role_labels[f.role]||f.role)}</strong><span>${esc(f.path)}</span><small>${gb(f.size)}</small></div>`).join('')}${m.vision?.projector&&!m.files.some(f=>f.role==='mmproj')?`<div class="external-path"><strong>mmproj automatico</strong><span>${esc(m.vision.projector)}</span></div>`:''}<p class="small-note">${esc(m.license)}</p></details></article>`;
}
function activeJob(){return state?.jobs.find(j=>j.chat_id===current&&['queued','running'].includes(j.status));}
function userJob(){return state?.jobs.find(j=>['queued','running'].includes(j.status));}
function modelName(id){return modelLabel(state?.models.find(m=>m.id===id));}

async function refresh(){
  if(loading)return;loading=true;
  try{
    state=await api('/state');renderSidebar();renderStatus();
    if(current){const id=current;const fresh=await api('/chats/'+id);if(current===id){chat=fresh;await renderChat();}
      if(canvasOpen){await loadCanvasHistory(id);
        if(canvasFollow&&!canvasDirty&&!canvasEditing){const selection=canvasSelection,c=await api('/canvas/'+id);if(current===id&&canvasFollow&&selection===canvasSelection)await setCanvas(c,false);}}}
    updateDownloads();
    await projects.poll();
    if($('#settings').open&&Date.now()-lastAssessment>10000)scheduleAssessment();
  }catch(e){if(state)toast(e.message,true);else $('#job-status').textContent='Impossibile connettersi. Avvia H3-Chat.';}
  finally{loading=false;clearTimeout(pollTimer);pollTimer=setTimeout(refresh,state?.jobs.some(j=>['queued','running'].includes(j.status))||state?.downloads.some(d=>d.status==='running')?850:3500);}
}
function renderSidebar(){
  const search=$('#search').value.toLocaleLowerCase();
  const activities=chatActivities(state.jobs);
  const signature=JSON.stringify([state.chats,state.collections,state.projects,[...activities],filter,collection,project,current,search]);if(signature===lastSidebar)return;lastSidebar=signature;
  projects.sidebar(project);
  $('#chat-count').textContent=state.chats.filter(c=>!c.archived).length;
  document.querySelectorAll('[data-filter]').forEach(b=>b.classList.toggle('active',b.dataset.filter===filter&&!collection&&!project));
  $('#collections').innerHTML=state.collections.map(c=>`<div class="collection-row"><button data-collection="${c.id}" class="${collection===c.id?'active':''}">▱ ${esc(c.name)}</button><button data-collection-menu="${c.id}" aria-label="Opzioni ${esc(c.name)}">⋯</button></div>`).join('');
  const chats=state.chats.filter(c=>(filter==='archived'?c.archived:!c.archived)&&(filter!=='pinned'||c.pinned)&&(!collection||c.collection_id===collection)&&(!project||c.project_id===project)&&c.title.toLocaleLowerCase().includes(search));
  $('#list-label').textContent=project?state.projects.find(p=>p.id===project)?.name:collection?state.collections.find(c=>c.id===collection)?.name:'CONVERSAZIONI';
  $('#chat-list').innerHTML=chats.map(c=>`<div class="chat-row ${current===c.id?'active':''}"><button class="chat-link" data-chat="${c.id}" aria-busy="${activities.get(c.id)==='running'}">${c.pinned?'<span class="pin-mark">⌖</span>':''}<span class="chat-title">${esc(c.title)}</span>${chatActivityIcon(activities.get(c.id))}</button><button class="chat-options" data-chat-menu="${c.id}" aria-label="Opzioni ${esc(c.title)}">⋯</button></div>`).join('')||'<div class="side-empty">Le tue conversazioni appariranno qui.</div>';
}
function renderStatus(){
  if(!state)return;
  chatModels.render();
  projects.controls();
  let mode=document.getElementById('execution-hint');if(!mode){mode=document.createElement('p');mode.id='execution-hint';mode.className='mode-hint';$('#composer').after(mode);}const activeModels=[['LLM','chat_model','llm_device'],['Immagini','create_model','image_device'],['Musica','music_model','music_backend'],['Video','video_model','video_device']];let slow=false;mode.textContent=activeModels.map(([label,key,deviceKey])=>{const m=state.models.find(m=>m.id===state.settings[key]);if(!m)return null;if(m.api||m.remote_media){const p=state.media_providers?.find(p=>p.id===m.id);if(p?.device==='cpu'&&p.adapter==='h3'&&label!=='LLM')slow=true;return label+': server esterno';}const choice=state.settings[deviceKey];const cpu=label==='Video'?false:choice==='cpu'||(choice==='inherit'||choice==='auto')&&(state.settings.profile==='cpu'||state.settings.backend==='cpu'||label==='Musica'&&state.settings.backend!=='cuda');if(cpu&&['Immagini','Musica'].includes(label))slow=true;return label+': '+(cpu?'CPU':'GPU');}).filter(Boolean).join(' · ')+(slow?' · Su CPU immagini e musica possono richiedere molto tempo.':'');
  loraUI.render();visualControls.render();
  $('#chat-advanced').checked=!!state.settings.chat_advanced;
  const job=userJob(),canvasJob=activeJob(),any=state.jobs.some(j=>j.status==='running');
  slideImages.render(state);
  $('#engine-badge').classList.toggle('busy',any);
  const loaded=state.memory?.models||[];
  $('#memory-status').textContent=(state.settings.memory_policy==='resident'?'Residenti':'A richiesta')+' · '+loaded.length+' caricati'+(state.memory?.warm_image_engine?' · motore immagini pronto':'');
  $('#memory-status').title=loaded.map(m=>m.name+' · '+m.location+(m.ready?'':' · caricamento')).join('\n')||'Apri la gestione della memoria';
  const live=$('#resident-models');if(live)live.textContent=loaded.map(m=>m.name+' · '+m.location+(m.ready?'':' · caricamento')).join(' / ')||'Nessun modello caricato';
  const release=$('#release-memory');if(release)release.disabled=state.jobs.some(j=>['running','queued'].includes(j.status));
  $('#model-name').textContent=modelName(state.settings.chat_model);
  const model=state.models.find(m=>m.id===state.settings.chat_model),vision=model?.vision,thinking=model?.thinking;
  $('#model-name').title=model?.identity?.path||'Mostra i dettagli del modello LLM';$('#model-name').disabled=!model;
  $('.local-badge').innerHTML='<i></i> '+(model?.api?'LLM tramite API':'Sul tuo computer');
  $('#engine-badge').innerHTML='<i></i> '+(any?'Lavoro in corso':model?.api?'LLM tramite API':'Motore locale');
  $('#vision-enabled').checked=state.settings.vision_enabled;$('#vision-toggle-label').textContent='Vision '+(state.settings.vision_enabled?'On':'Off');
  $('#vision-badge').textContent=vision?.enabled?(state.settings.vision_enabled?(model.api?'Vision · API':'Vision · '+(state.settings.vision_device==='gpu'?'GPU':'CPU')):'Vision disattivata'):model?'Non vision':'Vision da configurare';
  $('#vision-badge').className='badge '+(vision?.enabled?'ready':'warning');
  $('#vision-badge').title=vision?.projector?'Proiettore automatico: '+vision.projector:vision?.warning||'Scegli un modello nelle impostazioni.';
  $('#vision-warning').hidden=!model||!!vision?.enabled;
  $('#vision-warning').textContent=vision?.warning||'';
  $('#think-level').disabled=!thinking?.supported||thinkSaving||chatModels.busy();
  $('#vision-enabled').disabled=chatModels.busy();
  $('#send').disabled=chatModels.busy();
  if(!thinkSaving)$('#think-level').value=thinking?.supported?state.settings.think_level:'off';
  $('#think-note').textContent=thinking?.supported?(model.api?'Thinking · API':'Budget di ragionamento'):'Non supportato dal modello';
  $('#think-note').title=thinking?.note||'';
  const mtp=model?.mtp;
  const draft=mtp?.supported&&state.settings.mtp_enabled?Math.min(state.settings.mtp_draft_tokens,mtp.max_draft_tokens||8):0;
  $('#generation-settings').textContent=(draft?'MTP On · '+draft:mtp?.supported?'MTP Off':'MTP N/D')+' · Contesto '+Number(state.settings.context).toLocaleString('it-IT')+' · Max '+state.settings.max_tokens+' token';
  $('#generation-settings').title=(mtp?.note||'Seleziona un modello per verificare MTP.')+' Apri le Preferenze per contesto LLM, MTP e max token di risposta. Le modifiche valgono dal prossimo messaggio.';
  $('#job-status').textContent=job?(job.chat_id!==current?'Richiesta in un’altra chat · ':'')+job.stage:chat?.archived?'Conversazione archiviata. Ripristinala per continuare.':canvasOpen?'Destinazione: canvas · nella chat solo il messaggio di accompagnamento.':'';
  $('#send').hidden=!!job;$('#stop').hidden=!job;$('#prompt').disabled=!!chat?.archived;
  $('#regenerate').disabled=!!job||!!chat?.archived||!chat?.messages.some(m=>m.role==='user');
  $('#setup-nudge').hidden=state.settings.setup_done&&!!state.models.find(m=>m.id===state.settings.chat_model)?.ready;
  $('#chat-title').textContent=chat?.title||'Una nuova conversazione';
  $('#canvas-source').readOnly=!!canvasJob?.canvas;
  $('#canvas-title').readOnly=!!canvasJob?.canvas;
  $('#canvas-restore').disabled=!!canvasJob?.canvas||!canvas.id||canvas.id===canvasHistory.active_id;
  composerUI?.render();manimPresentation?.render();
}
async function newChat(){if(current)await persistCanvas();const fresh=await api('/chats',{collection_id:collection,project_id:project});await openChat(fresh.id);await refresh();$('#prompt').focus();}
async function openChat(id){
  if(current){drafts.set(current,{prompt:$('#prompt').value,attachments:[...attachments]});await persistCanvas();}
  current=id;chat=await api('/chats/'+id);$('#messages').innerHTML='';
  const draft=drafts.get(id)||{prompt:'',attachments:[]};$('#prompt').value=draft.prompt;attachments=draft.attachments;renderAttachments();
  canvasSelection++;canvasHistory={items:[],active_id:null};canvasFollow=true;canvasDirty=false;lastCanvas='';canvasEditing=false;
  await loadCanvasHistory(id);await setCanvas(await api('/canvas/'+id));
  renderSidebar();renderStatus();await renderChat();$('#sidebar').classList.remove('visible');
  $('#scroll-area').scrollTop=$('#scroll-area').scrollHeight;
}
async function renderChat(){
  $('#welcome').hidden=!!chat?.messages.length;
  if(!chat)return;
  const scroll=$('#scroll-area'),atBottom=scroll.scrollHeight-scroll.scrollTop-scroll.clientHeight<130;
  for(const message of chat.messages){
    const pending=message.role==='assistant'&&['queued','running'].includes(message.status);
    const job=pending?(state.jobs.find(j=>j.message_id===message.id)||activeJob()):null;
    const elapsed=job?Math.max(0,Math.floor(Date.now()/1000-job.created)):0;
    let article=document.getElementById('msg-'+message.id);const signature=JSON.stringify([message.content,message.status,message.media,message.meta,state.settings.chat_advanced,pending?job?.stage:null,pending?elapsed:null]);
    if(article?.dataset.signature===signature)continue;
    if(!article){article=document.createElement('article');article.id='msg-'+message.id;article.className='message '+message.role;$('#messages').append(article);}
    article.dataset.signature=signature;
    article.innerHTML=`<div class="message-head">${message.role==='user'?'<span class="user-avatar">TU</span>':'<img src="/static/icon.svg" alt="">'}<strong>${message.role==='user'?'Tu':'H3 Chat'}</strong><span>${message.meta.model?esc(message.meta.model_identity?.label||message.meta.model):''}</span>${message.meta.canvas?'<span class="badge">Canvas</span>':''}</div><div class="message-content ${message.role==='assistant'?'rich':''}"></div><div class="message-actions"></div>`;
    const content=article.querySelector('.message-content');
    if(message.role==='user')content.textContent=message.content;
    else if(message.content)await renderRich(content,message.content,{final:message.status==='done',sources:message.meta.rag_sources||[],onCitation:(source,sources)=>projects.citation(source,sources,message),onExecute:act(executeArtifact)});
    if(pending){
      const title=({create:'Creazione immagine',edit:'Modifica immagine',video:'Generazione video',music:'Generazione musica',slides:'Creazione slide nel canvas',transcribe:'Trascrizione audio',manim:message.meta.narrated_manim?'Animazione Manim con voce':'Animazione Manim',calculate:'Calcolo in corso',chat:message.meta.canvas?'Scrittura nel canvas':'Risposta in corso'})[message.meta.intent]||(job?.status==='queued'?'In attesa':'Preparazione della risposta');
      const activity=document.createElement('div');activity.className='generation-activity';activity.setAttribute('role','status');
      const duration=elapsed<60?elapsed+' s':Math.floor(elapsed/60)+' min '+elapsed%60+' s';
      activity.innerHTML=`<div class="thinking" aria-hidden="true"><i></i><i></i><i></i></div><div><strong>${esc(title)}</strong><span class="activity-stage">${esc(job?.stage||'Preparazione del motore…')}</span><small class="activity-elapsed">Tempo trascorso: ${duration}</small></div>`;
      content.append(activity);
    }
    appendMedia(content,message.media,{api});appendMusicDetails(content,message,state.settings.chat_advanced);appendVideoDetails(content,message,state.settings.chat_advanced);appendToolsDetails(content,message,state.settings.chat_advanced);
    if(message.role==='assistant')projects.append(content,message);
    if(message.meta.quote_warnings?.length){const warning=document.createElement('p');warning.className='render-error';warning.textContent='Citazione letterale da verificare: '+message.meta.quote_warnings.join(' ');content.append(warning);}
    if(message.meta.slide_warning){const warning=document.createElement('p');warning.className='small-note';warning.textContent=message.meta.slide_warning;content.append(warning);}
    if(message.role==='assistant'&&message.meta.execution_mode){const hint=document.createElement('p');hint.className='mode-hint';hint.textContent=message.meta.execution_mode+(message.meta.device_warning?' · '+message.meta.device_warning:'');content.append(hint);}
    if(message.meta.loras?.length&&(message.role==='user'||state.settings.chat_advanced)){const row=document.createElement('div');row.className='message-loras';row.textContent=message.meta.loras.map(l=>'◇ '+l.name+' × '+l.weight+' · '+l.model_name).join(' / ');content.append(row);}
    if(message.meta.loras_skipped?.length){const note=document.createElement('p');note.className='small-note';note.textContent=message.meta.loras_skipped.length+' LoRA non applicati: associati a un altro modello o con peso 0.';content.append(note);}
    if(message.meta.image_parameters&&state.settings.chat_advanced){const p=message.meta.image_parameters,details=document.createElement('details');details.className='image-parameters';const title=document.createElement('summary');title.textContent='Parametri immagine';const values=document.createElement('p');values.textContent=p.width+' × '+p.height+' · '+p.steps+' step · CFG '+p.cfg+' · '+p.sampler+' / '+p.scheduler+' · Seed '+p.seed+' · Intensità '+p.strength+(p.vae_backend?' · VAE '+(p.vae_backend==='cpu'?'CPU':'GPU'):'');details.append(title,values);if(p.negative_prompt){const negative=document.createElement('p');negative.textContent='Negative prompt: '+p.negative_prompt;details.append(negative);}content.append(details);}
    if(message.meta.image_parameters&&state.settings.chat_advanced){const d=document.createElement('details'),summary=document.createElement('summary'),prompt=document.createElement('pre');summary.textContent='Assistant '+(message.meta.assistant_on?'On · '+message.meta.assistant?.model+(message.meta.assistant?.prompt_format==='tags'?' · tag in inglese':''):'Off')+' · prompt immagini';prompt.textContent=message.meta.image_prompt;prompt.style.whiteSpace='pre-wrap';d.append(summary,prompt);content.append(d);}
    if(message.role==='assistant'&&message.meta.model_warning){const note=document.createElement('div');note.className='vision-warning';note.textContent=message.meta.model_warning;content.append(note);}
    if(message.role==='assistant'&&message.meta.mtp_tokens){const badge=document.createElement('span');badge.className='badge';badge.textContent='MTP · '+message.meta.mtp_tokens;article.querySelector('.message-head').append(badge);}
    if(message.role==='assistant'&&message.meta.think_level){const badge=document.createElement('span');badge.className='badge';badge.textContent='Think '+message.meta.think_level;badge.title=message.meta.api?message.meta.think_note:message.meta.think_budget+' token massimi di ragionamento';article.querySelector('.message-head').append(badge);}
    if(['failed','interrupted','cancelled'].includes(message.status)){const err=document.createElement('div');err.className='message-error';err.textContent=message.meta.error||'Risposta interrotta. Puoi riprovare.';content.append(err);}
    const actions=article.querySelector('.message-actions');
    if(message.status==='failed'&&message.meta.intent==='manim'&&message.meta.error?.startsWith('Durata errata:')){
      const recover=document.createElement('button');recover.className='text-button';recover.textContent='Recupera animazione';recover.onclick=act(async()=>{await api('/chats/'+current+'/recover-manim',{message_id:message.id});await refresh();toast('Animazione recuperata.');});actions.append(recover);
    }
    if(message.content){const copy=document.createElement('button');copy.className='text-button';copy.textContent='Copia';copy.onclick=act(async()=>{await navigator.clipboard.writeText(message.content);toast('Copiato.');});actions.append(copy);}
    if(message.role==='assistant'&&message.status==='done'){
      const toCanvas=document.createElement('button');toCanvas.className='text-button';toCanvas.textContent=message.meta.canvas?'Apri canvas':'Apri nel canvas';toCanvas.onclick=act(async()=>{
        await persistCanvas();await loadCanvasHistory();const item=canvasHistory.items.findLast(x=>x.message_id===message.id&&!x.source_key.startsWith('manual:'));
        if(item)await selectCanvasArtifact(item.id);
        else{await setCanvas({title:chat.title,content:message.content,media:message.media});canvasDirty=true;await persistCanvas();}
        await toggleCanvas(true);
      });actions.append(toCanvas);
      if(message.meta.finish_reason==='length'){const note=document.createElement('span');note.textContent='Limite di risposta raggiunto';actions.append(note);}
    }
    if(message.role==='user'){const repeat=document.createElement('button');repeat.className='text-button';repeat.textContent='Riutilizza';repeat.onclick=()=>{$('#prompt').value=message.content;attachments=[...message.media];if(message.meta.manim_presentation){$('#lab-tool').value='manim';composerUI?.render();}manimPresentation?.set(message.meta.manim_presentation?{enabled:true,...message.meta.manim_presentation}:null);loraUI.setSelections(message.meta.loras||[]);visualControls.set({voice:message.meta.voice||false,voice_fields:message.meta.voice_fields||{},image_model:message.meta.image_model||'',assistant:message.meta.assistant??true,video:message.meta.video||false,web:message.meta.web||false,transcribe:message.meta.transcribe||false,music:message.meta.music||false,music_fields:message.meta.music_fields||{}});renderAttachments();$('#prompt').focus();};actions.append(repeat);}
  }
  if(atBottom)scroll.scrollTop=scroll.scrollHeight;
}
function renderAttachments(){
 let image=0,audio=0,document=0;
 $('#attachments').innerHTML=attachments.map((m,i)=>{const sound=m.mime?.startsWith('audio/'),doc=m.mime?.startsWith('application/'),label=doc?'Documento '+(++document):sound?'Audio '+(++audio):'Immagine '+(++image);return `<div class="attachment" title="${esc(m.name)}">${doc?'<span class="audio-attachment">▤</span>':sound?'<span class="audio-attachment">♫</span>':`<img src="/media/${esc(m.path)}" alt="${esc(m.name)}">`}<small>${label}</small><button data-remove-attachment="${i}" aria-label="Rimuovi ${label}">×</button></div>`;}).join('');
 manimPresentation?.render();
}
async function uploadFiles(files){
 if(attachments.length+files.length>12)throw Error('Massimo 12 allegati per messaggio.');
 for(const file of files){
  const sound=file.type.startsWith('audio/')||/\.(wav|mp3|flac|ogg)$/i.test(file.name),doc=/\.(pdf|docx|pptx)$/i.test(file.name);
  const category=doc?'application/':sound?'audio/':'image/';
  if(attachments.filter(x=>x.mime.startsWith(category)).length>=(doc||sound?3:9))throw Error(doc?'Massimo tre documenti.':sound?'Massimo tre audio.':'Massimo nove immagini; il modello mantiene il proprio limite.');
  if(!doc&&!sound&&!['image/png','image/jpeg','image/webp'].includes(file.type))throw Error('Scegli immagini, audio WAV/MP3/FLAC/OGG, PDF, Word .docx o PowerPoint .pptx.');
  if(file.size>(doc?25:sound?64:12)*1024*1024)throw Error(doc?'Documenti: massimo 25 MB.':sound?'Audio: massimo 64 MB.':'Immagini: massimo 12 MB.');
  let source=file;
  if(!sound&&!doc){const bitmap=await createImageBitmap(file);if(Math.max(bitmap.width,bitmap.height)>8192){bitmap.close();throw Error('Massimo 8192 pixel.');}
   if(file.type==='image/webp'){const c=document.createElement('canvas');c.width=bitmap.width;c.height=bitmap.height;c.getContext('2d').drawImage(bitmap,0,0);source=await new Promise(r=>c.toBlob(r,'image/png'));}bitmap.close();}
  const data=await new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(reader.result.split(',')[1]);reader.onerror=reject;reader.readAsDataURL(source);});
  attachments.push(await api('/uploads',{name:file.name,data}));renderAttachments();
 }
}
async function send(event){event.preventDefault();if(userJob())return;const prompt=$('#prompt').value.trim();if(!prompt)return;
  $('#send').disabled=true;
  try{await chatModels.wait();if(!current){const fresh=await api('/chats',{collection_id:collection,project_id:project});loraUI.migrateNew(fresh.id);visualControls.migrateNew(fresh.id);manimPresentation?.migrateNew(fresh.id);current=fresh.id;chat=fresh;}
    await persistCanvas();const presentation=await manimPresentation.prepare();const sent=await api('/chats/'+current+'/messages',{prompt,media:attachments,canvas:canvasOpen,...presentation,...visualControls.read(),...projects.read(),lab:$('#lab-tool').value,...($('#lab-tool').value==='slides'?{slides:{engine:$('#slides-engine').value,count:Number($('#slides-count').value),format:$('#slides-format').value,design:$('#slides-design').value,detail:$('#slides-detail').value,vision_scope:$('#slides-vision').value,...slideImages.read()}}:{}),think_level:$('#think-level').value,loras:loraUI.getSelections()});
    if(sent.intent==='slides'){canvasFollow=true;canvasEditing=false;await toggleCanvas(true);}
    $('#prompt').value='';attachments=[];renderAttachments();drafts.delete(current);await refresh();
  }finally{$('#send').disabled=false;}
}

async function regenerate(){
  if(!current||userJob())return;
  $('#regenerate').disabled=true;
  try{await chatModels.wait();await api('/chats/'+current+'/regenerate',{});const previous=chat?.messages.findLast(m=>m.role==='assistant');if(previous?.meta?.canvas||previous?.meta?.intent==='slides'){canvasFollow=true;canvasEditing=false;await toggleCanvas(true);}await refresh();}
  finally{renderStatus();}
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
    {label:'Sposta in un progetto',action:async()=>{const dest=await ask('Scegli progetto',{value:c.project_id||'',options:[{value:'',label:'Nessun progetto'},...state.projects.map(x=>({value:x.id,label:x.name}))]});if(dest!==null)await patch({project_id:dest||null});}},
    {label:c.archived?'Ripristina chat':'Archivia chat',action:()=>patch({archived:!c.archived})},
    {label:'Esporta conversazione',action:async()=>{const data=await api('/chats/'+id);saveBlob(new Blob([JSON.stringify(data,null,2)],{type:'application/json'}),'chat.json');}},
    {label:'Elimina chat',danger:true,action:async()=>{if(await ask('Eliminare questa chat?',{description:'Messaggi e canvas saranno eliminati. Gli allegati restano sul disco se usati in altre conversazioni.',confirm:true})){await api('/chats/'+id,{},'DELETE');if(current===id){current=null;chat=null;$('#messages').innerHTML='';$('#welcome').hidden=false;await setCanvas({title:'Canvas',content:'',media:[]});}await refresh();}}}]);
}
function collectionMenu(id,button){const c=state.collections.find(c=>c.id===id);menuAt(button,[{label:'Rinomina raccolta',action:async()=>{const name=await ask('Rinomina raccolta',{value:c.name});if(name){await api('/collections/'+id,{name},'PATCH');await refresh();}}},{label:'Elimina raccolta',danger:true,action:async()=>{if(await ask('Eliminare la raccolta?',{description:'Le conversazioni restano disponibili in Tutte le chat.',confirm:true})){await api('/collections/'+id,{},'DELETE');if(collection===id)collection=null;await refresh();}}}]);}

async function loadCanvasHistory(id=current){
  if(!id){canvasHistory={items:[],active_id:null};renderCanvasHistory();return;}
  const request=++canvasHistoryRequest,value=await api('/canvas/'+id+'/history');if(current!==id||request!==canvasHistoryRequest)return;
  canvasHistory=value;renderCanvasHistory();
}
function renderCanvasHistory(){
  const items=canvasHistory.items,index=items.findIndex(x=>x.id===canvas.id),select=$('#canvas-history');
  const signature=JSON.stringify([items,canvas.id,canvasHistory.active_id]);
  if(select.dataset.signature!==signature){select.dataset.signature=signature;
    select.innerHTML=(!items.length||index<0?'<option value="">Canvas in uso</option>':'')+items.map((x,i)=>`<option value="${esc(x.id)}">${i+1}. ${esc(x.title)}${x.id===canvasHistory.active_id?' · in uso':''}</option>`).join('');select.value=canvas.id||'';
  }
  select.disabled=!items.length;$('#canvas-previous').disabled=index<=0;
  $('#canvas-next').disabled=index<0||index>=items.length-1;
  const item=items[index];$('#canvas-history-status').textContent=item?`${index+1} di ${items.length} · ${new Date(item.created*1000).toLocaleString('it-IT',{dateStyle:'short',timeStyle:'short'})}`:items.length+' artefatti salvati';
  $('#canvas-follow').checked=canvasFollow;
  $('#canvas-restore').hidden=!canvas.id||canvas.id===canvasHistory.active_id;
  $('#canvas-restore').disabled=!!activeJob()?.canvas;
}
async function selectCanvasArtifact(ident){
  await persistCanvas();const id=current,selection=++canvasSelection;canvasFollow=false;canvasEditing=false;renderCanvasHistory();
  const value=await api('/canvas/'+id+'/history/'+ident);if(current!==id||selection!==canvasSelection)return;
  await setCanvas(value);renderStatus();
}
async function followCanvas(){
  await persistCanvas();const id=current,selection=++canvasSelection;canvasFollow=true;canvasEditing=false;
  if(id){await loadCanvasHistory(id);const value=await api('/canvas/'+id);if(current===id&&selection===canvasSelection)await setCanvas(value);}
  renderCanvasHistory();renderStatus();
}
async function toggleCanvas(value=!canvasOpen){projects.hide();canvasOpen=value;$('#canvas-panel').hidden=!value;$('#workspace').classList.toggle('has-canvas',value);$('#canvas-toggle').setAttribute('aria-pressed',value);
  if(value&&current){await loadCanvasHistory();if(canvasFollow&&!canvasDirty&&!canvasEditing)await setCanvas(await api('/canvas/'+current),true);}if(value)await renderCanvas();renderStatus();}
async function setCanvas(value,force=true){if(!current){canvasHistory={items:[],active_id:null};canvasFollow=true;canvasSelection++;}const signature=JSON.stringify([value.id,value.title,value.content,value.media]);if(!force&&signature===lastCanvas)return;canvas={id:value.id||null,title:value.title||'Canvas',content:value.content||'',media:value.media||[]};lastCanvas=signature;$('#canvas-title').value=canvas.title;$('#canvas-source').value=canvas.content;renderCanvasHistory();await renderCanvas();}
async function renderCanvas(){
  const empty=!canvas.content&&!canvas.media.length;$('#canvas-empty').hidden=!empty||canvasEditing;$('#canvas-preview').hidden=canvasEditing||empty;$('#canvas-source').hidden=!canvasEditing;
  $('#canvas-preview-tab').classList.toggle('active',!canvasEditing);$('#canvas-source-tab').classList.toggle('active',canvasEditing);
  const isDeck=canvas.content.startsWith('```h3-slides\n');$('#canvas-source-tab').textContent=isDeck?'Sorgente slide':'Modifica';$('#canvas-source').ariaLabel=isDeck?'Sorgente della presentazione':'Sorgente canvas';
  for(const kind of ['html','pptx']){const button=document.querySelector('[data-export="'+kind+'"]');if(button)button.hidden=!isDeck;}
  if(!canvasEditing){const value={...canvas,media:[...canvas.media]},entry=canvasHistory.items.find(x=>x.id===value.id),message=(chat?.messages||[]).find(m=>m.id===entry?.message_id)||[...(chat?.messages||[])].reverse().find(m=>m.meta?.artifact?.content===value.content||m.content===value.content);renderQueue=renderQueue.catch(()=>{}).then(async()=>{const options={final:!activeJob()?.canvas||value.id!==canvasHistory.active_id,sources:message?.meta?.rag_sources||[],onCitation:(s,all)=>projects.citation(s,all,message),onExecute:act(executeArtifact)};
    if(isDeck){try{await renderSlides($('#canvas-preview'),value,{...options,api,chatId:current,editable:!userJob(),onRegenerate:async(page,prompt)=>{
      if(userJob())throw Error('Attendi o interrompi la tua richiesta in corso.');
      await chatModels.wait();await persistCanvas();
      await api('/canvas/'+current+'/slides/regenerate',{artifact_id:canvas.id,page,prompt,think_level:$('#think-level').value});
      canvasFollow=true;canvasEditing=false;await toggleCanvas(true);await refresh();
    },onChange:async (content,media)=>{
      if(activeJob()?.canvas)throw Error('Attendi la fine della generazione prima di modificare.');
      canvasFollow=false;canvasSelection++;canvas.content=content;if(media)canvas.media=media;canvasDirty=true;$('#canvas-source').value=content;
      await persistCanvas();await renderCanvas();
    }});}catch(e){$('#canvas-preview').textContent=e.message;}}
    else{$('#canvas-preview').classList.remove('slides-preview');await renderRich($('#canvas-preview'),value.content,options);appendMedia($('#canvas-preview'),value.media,{api});}
  });await renderQueue;}
}
async function persistCanvas(){clearTimeout(canvasSaveTimer);if(canvasSaving){await canvasSaving;if(canvasDirty)return persistCanvas();return;}if(!canvasDirty)return;
  canvasSaving=(async()=>{
    if(!current){const fresh=await api('/chats',{project_id:project});loraUI.migrateNew(fresh.id);visualControls.migrateNew(fresh.id);manimPresentation?.migrateNew(fresh.id);current=fresh.id;chat=fresh;}
    const id=current,value=structuredClone(canvas),saved=await api('/canvas/'+id,value,'PUT');
    if(current===id){const unchanged=JSON.stringify(canvas)===JSON.stringify(value);transferSlideView(canvas.id,saved.id);canvas.id=saved.id;if(unchanged)canvasDirty=false;await loadCanvasHistory(id);$('#canvas-save-status').textContent=canvasDirty?'Modifiche da salvare':'Salvato sul computer';}
  })();try{await canvasSaving;}finally{canvasSaving=null;}
}
function canvasChanged(){canvas.title=$('#canvas-title').value;canvas.content=$('#canvas-source').value;canvasDirty=true;$('#canvas-save-status').textContent='Modifiche da salvare';clearTimeout(canvasSaveTimer);canvasSaveTimer=setTimeout(act(persistCanvas),800);}

function collectSettings(){
 let model=settingsDraft.chat_model;
 for(const field of $('#settings-body').querySelectorAll('[data-setting]')){
  if(field.dataset.llmSetting)continue;
  const key=field.dataset.setting;if(key==='chat_model'){model=field.value;continue;}
  settingsDraft[key]=field.type==='number'||key==='ram_cache_gb'?Number(field.value):field.type==='checkbox'?field.checked:field.value;
 }
 syncLlmDraft(settingsDraft,state,model);
}
function options(items,value){return items.map(([id,label])=>`<option value="${id}" ${id===value?'selected':''}>${esc(label)}</option>`).join('');}
function settingSelect(key,label,items,hint=''){return `<label class="field"><span>${label}</span><select data-setting="${key}">${options(items,settingsDraft[key])}</select>${hint?`<small>${hint}</small>`:''}</label>`;}
function numberField(key,label,min,max,step=1){return `<label class="field"><span>${label}</span><input type="number" data-setting="${key}" value="${settingsDraft[key]}" min="${min}" max="${max}" step="${step}"></label>`;}
async function openSettings(tab='setup'){
 if(!state)return;
 try{
  const fresh=await api('/state');llmOptions(fresh);state=fresh;
  settingsDraft=structuredClone(state.settings);selectLlmPreferencesModel(settingsDraft.chat_model);selectImagePreferencesModel(settingsDraft.create_model||settingsDraft.edit_model);settingsTab=tab;settingsError();$('#settings').showModal();renderSettings();
 }catch(e){toast(e.message,true);}
}
function scheduleAssessment(){
  clearTimeout(assessmentTimer);assessmentRequest++;
  assessmentTimer=setTimeout(act(updateAssessment),300);
}
async function updateAssessment(){
  if(!$('#settings').open)return;
  collectSettings();const ticket=++assessmentRequest;lastAssessment=Date.now();
  const box=$('#memory-assessment');if(!box)return;
  box.setAttribute('aria-busy','true');
  try{
    const report=await api('/assess',{loras:loraUI.getSelections(),settings:settingsDraft,references:Math.max(1,attachments.length)});
    if(ticket!==assessmentRequest||!$('#settings').open)return;
    const h=report.hardware,mem=n=>n==null?'non rilevata':(n/1024).toLocaleString('it-IT',{maximumFractionDigits:1})+' GiB';
    const summary=`${h.cpu_name} · ${h.cpu_threads} thread · RAM ${mem(h.ram.total_mb)}, libera ${mem(h.ram.free_mb)}`;
    const gpus=h.gpu.map(g=>`${g.name} · VRAM ${mem(g.total_mb)}, libera ${mem(g.free_mb)}`).join(' / ');
    const info=$('#hardware-info');if(info)info.textContent=summary+(gpus?' · '+gpus:' · Nessuna GPU rilevata');
    const roles={chat_model:'Chat / vision',create_model:'Creazione immagini',edit_model:'Modifica immagini',diagram_model:'Grafici e diagrammi',music_model:'Musica',video_model:'Video MiniMax H3'};
    box.innerHTML=`<div class="assessment-head"><h3>Memoria per i modelli predefiniti</h3><button type="button" id="refresh-hardware" class="text-button">Aggiorna</button></div><p class="small-note">${esc(summary)}${gpus?'<br>'+esc(gpus):''}</p><p class="small-note">Stime per ${report.references} riferiment${report.references===1?'o':'i'}, contesto LLM ${settingsDraft.context} e parametri immagini dei rispettivi preset. ${esc(report.overall.note)}</p><article class="memory-total ${report.overall.status}"><strong>${esc(report.overall.title)} · ${report.overall.unique_models} modelli distinti</strong><p>${esc(report.overall.advice)}</p><small>Totale stimato RAM ${report.overall.ram_gb} GiB · VRAM ${report.overall.vram_gb} GiB</small></article>${report.memory.models.length?'<p class="small-note">Ci sono modelli già caricati: la memoria libera ne include l’occupazione. Per una previsione a freddo premi Libera memoria e Aggiorna.</p>':''}`+report.models.map((m,i)=>`<article class="memory-result ${m.status}"><div><strong>${roles[m.role]} · ${esc(m.name)}</strong><span class="badge">${esc(m.title)}</span></div><p>${esc(m.advice)}</p><small>Stima RAM ${m.ram_gb} GiB · VRAM ${m.vram_gb} GiB${m.gpu_name?' · '+esc(m.gpu_name):''}</small>${m.assumptions.length?`<details><summary>Come viene stimata</summary><p>${esc(m.assumptions.join(' '))}</p></details>`:''}${Object.keys(m.recommended_patch).length?`<button type="button" class="btn small" data-memory-patch="${i}">Applica suggerimento</button>`:''}</article>`).join('')+(!report.models.length?'<p class="small-note">Seleziona i modelli per vedere la stima prima di scaricarli.</p>':'')+`<p class="small-note">${esc(h.note)}</p>`;
    if(report.rag_embedding){const e=report.rag_embedding;box.insertAdjacentHTML('beforeend',`<article class="memory-result ${esc(e.status)}"><div><strong>RAG · Ovis-Omni-Embedding-3B</strong><span class="badge">${esc(e.title)}</span></div><p>${esc(e.advice)}</p>${e.ram_gb!=null?`<small>Stima RAM ${e.ram_gb} GiB · VRAM ${e.vram_gb} GiB · fase RAG, prima della risposta LLM</small>`:''}</article>`);}
      if(report.voice){const e=report.voice;box.insertAdjacentHTML('beforeend',`<article class="memory-result ${esc(e.status)}"><strong>${esc(e.title)}</strong><p>${esc(e.advice)}</p><small>Stima RAM ${e.ram_gb} GiB · VRAM ${e.vram_gb} GiB</small></article>`);}
      $('#refresh-hardware').onclick=scheduleAssessment;
    box.querySelectorAll('[data-memory-patch]').forEach(b=>b.onclick=()=>{collectSettings();Object.assign(settingsDraft,report.models[Number(b.dataset.memoryPatch)].recommended_patch);renderSettings();});
  }catch(e){if(ticket===assessmentRequest)box.textContent='Stima non disponibile: '+e.message;}
  finally{box.removeAttribute('aria-busy');}
}
function renderSettings(){
  document.querySelectorAll('[data-tab]').forEach(b=>b.classList.toggle('active',b.dataset.tab===settingsTab));
  const body=$('#settings-body');
  if(settingsTab==='setup'){
    const modelSelect=(key,label,cap)=>settingSelect(key,label,[['','Scegli dal catalogo…'],...state.models.filter(m=>m.capabilities.includes(cap)).map(m=>[m.id,modelLabel(m)+(cap==='chat'?(m.vision?.enabled?' · Vision':m.vision?.expected?' · Vision da completare':' · Non vision'):'')+(m.ready?'':m.external?' · percorso non disponibile':' · da scaricare')])]);
    body.innerHTML=`<div class="hardware-note" id="hardware-info">Scegli l'hardware. CPU, NVIDIA, AMD e Intel condividono la stessa interfaccia.</div><div class="settings-grid"><section class="card"><h3>01 · Il tuo computer</h3>${settingSelect('profile','Profilo memoria',[['cpu','Solo CPU / nessuna GPU'],['low','GPU · 4–8 GB VRAM'],['balanced','GPU · 12–24 GB VRAM']],'Il profilo imposta valori iniziali modificabili nelle Preferenze.')}${settingSelect('backend','Motore di calcolo',[['cpu','CPU · massima compatibilità'],['vulkan','Vulkan · NVIDIA / AMD / Intel'],['cuda','CUDA · NVIDIA']],'Il profilo Solo CPU usa sempre il backend CPU.')}<div class="runtime-actions"><button id="install-runtime" class="btn">Installa motori</button><span class="small-note" id="runtime-ready"></span></div><div id="runtime-downloads"></div></section><section class="card"><h3>02 · I tuoi modelli</h3>${modelSelect('chat_model','Chat, router e visione','chat')}${modelIdentityHtml(state.models.find(m=>m.id===settingsDraft.chat_model))}<p id="setup-vision-note" class="vision-warning"></p>${modelSelect('create_model','Creazione immagini','create')}${modelSelect('edit_model','Modifica e riferimenti','edit')}<p>Un'unica chat. Il router sceglie cosa fare dal prompt; la modalità memoria decide quali modelli conservare.</p><button id="go-catalog" class="text-button">Catalogo e modelli già scaricati →</button></section></div><div class="note">Con 4–8 GB scegli modelli quantizzati e pochi riferimenti. FLUX usa anche la RAM di sistema; CPU e offload riducono la VRAM ma aumentano i tempi. MiniMax H3 video si configura nella sezione Video qui sotto.</div>`;
    body.insertAdjacentHTML('beforeend',`<section class="card memory-settings"><h3>03 · Modelli in memoria</h3><div class="settings-grid">${settingSelect('memory_policy','Caricamento dei modelli',[['on_demand','A richiesta · un modello alla volta'],['resident','Residenti · tutti i modelli scelti']],'A richiesta conserva il modello corrente e lo scarica prima di caricarne uno diverso. Residenti carica i modelli installati al prossimo messaggio e li mantiene in VRAM (o RAM con CPU).')}${settingSelect('ram_cache_gb','Cache file in RAM recuperabile',[[0,'Disattivata'],[2,'Fino a 2 GiB'],[4,'Fino a 4 GiB'],[8,'Fino a 8 GiB'],[16,'Fino a 16 GiB'],[32,'Fino a 32 GiB']],'Conserva mapping recuperabili dei pesi. Con cache attiva mantiene inizializzato anche il motore Ming/Qwen dopo aver liberato i pesi: evita di ricaricare Python e le librerie a ogni cambio. Il motore usa ancora RAM e un piccolo contesto CUDA; la lettura dei pesi e i trasferimenti GPU restano necessari. Disattiva la cache o premi Libera memoria per chiuderlo.')}</div><p>Se creazione ed editing usano lo stesso modello, condividono il caricamento. In Residenti tutti i layer LLM usano la GPU; il proiettore vision resta sempre sulla CPU; il numero di layer nelle Preferenze vale per A richiesta. Per MiniMax H3 vale anche l’opzione di offload del suo preset: componenti caricati a richiesta e liberati dopo la loro fase quando è attiva. Le modifiche si applicano dopo il lavoro in corso.</p><div class="memory-live"><span id="resident-models"></span><button type="button" id="release-memory" class="btn small">Libera memoria</button></div></section>`);
    const visuals=document.createElement('section');visuals.className='visual-setup';body.append(visuals);
    renderVisualSetup(visuals,{state,draft:settingsDraft,link:kind=>localModels.open(null,kind),edit:localModels.open,
      preferences:id=>{collectSettings();selectImagePreferencesModel(id);settingsTab='advanced';renderSettings();},
      changed:()=>{for(const key of ['create_model','edit_model'])body.querySelector('[data-setting="'+key+'"]').value=settingsDraft[key];scheduleAssessment();toast('Modello selezionato. Salva le impostazioni.');},
      install:act(async()=>{await api('/downloads',{id:'vision',kind:'runtime'});await refresh();})});
    $('#release-memory').onclick=act(async()=>{await api('/memory/release',{});await refresh();scheduleAssessment();toast('Modelli scaricati e cache file liberata.');});
    renderStatus();
    $('#install-runtime').onclick=act(async()=>{collectSettings();const backend=settingsDraft.profile!=='cpu'&&settingsDraft.backend==='cuda'?'cuda':'cpu';await api('/downloads',{id:backend,kind:'runtime'});await refresh();});
    body.querySelector('[data-setting="chat_model"]').onchange=()=>{collectSettings();selectLlmPreferencesModel(settingsDraft.chat_model);renderSettings();};
    $('#go-catalog').onclick=()=>{collectSettings();settingsTab='models';renderSettings();};
    body.querySelector('[data-setting="profile"]').onchange=e=>{collectSettings();Object.assign(settingsDraft,{width:state.profiles[e.target.value].width,height:state.profiles[e.target.value].height});if(e.target.value==='cpu')settingsDraft.backend='cpu';renderSettings();};
    body.querySelector('[data-setting="backend"]').onchange=()=>{collectSettings();updateDownloads();};
  }else if(settingsTab==='models'){
    body.innerHTML='<div class="hardware-note external-intro"><div><strong>Usa i modelli già presenti sul computer</strong><p>Collega GGUF e modelli immagini dalle loro cartelle originali, anche su altre unità. Il mmproj viene cercato accanto al GGUF; encoder e VAE possono essere scelti da cartelle diverse.</p></div><button type="button" id="add-external-model" class="btn primary">Collega un modello</button></div><p class="small-note">Restano disponibili anche le cartelle models/local. <button type="button" id="rescan-models" class="text-button">Aggiorna modelli e percorsi</button></p>'+state.models.filter(m=>m.external).map(localCard).join('')+'<p class="small-note">Catalogo scaricabile: pesi e componenti vengono verificati con SHA-256. I collegamenti esterni usano i file originali senza copiarli.</p>' +state.models.filter(m=>!m.external&&!m.api&&!m.remote_media).map(m=>`<article class="model-card"><div class="model-top"><h3>${esc(m.name)}</h3><button class="btn small" data-download="${m.id}">${m.local?'Locale pronto':m.complete?'Verificato':'Scarica · '+gb(m.size)}</button></div><p>${esc(m.description)}</p>${modelIdentityHtml(m)}<div class="model-meta">${m.local?'<span class="badge">LOCALE</span>':''}${m.thinking?.supported?'<span class="badge">THINK</span>':''}${m.mtp?.supported?'<span class="badge">MTP</span>':''}${m.vision?'<span class="badge '+(m.vision.enabled?'ready':'warning')+'">'+(m.vision.enabled?'Vision attiva':'Non vision / mmproj assente')+'</span>':''}${m.capabilities.map(c=>`<span class="badge">${({chat:'CHAT',vision:'VISION',create:'CREA',edit:'MODIFICA',music:'MUSICA',video:'VIDEO'})[c]}</span>`).join('')}<span class="badge">${m.max_refs?m.max_refs+' riferimenti':'Testo'}</span><span class="badge">RAM indicativa ≥ ${m.ram_gb} GB</span><span class="badge ${m.ready?'ready':''}" id="ready-${m.id}">${m.complete?'Installato':m.ready?'Solo testo · completa mmproj':'Non installato'}</span></div><details><summary>Componenti e licenza</summary><p>${esc(m.license)}</p>${m.files.map(f=>`<div class="component"><span>${esc(f.role)} · ${f.repo?`<a href="https://huggingface.co/${esc(f.repo)}/blob/${f.revision}/${esc(f.filename)}" target="_blank" rel="noopener noreferrer">${esc(f.filename)}</a>`:esc(f.filename)}</span><span>${gb(f.size)}</span></div>`).join('')}</details><div data-download-status="${m.id}"></div></article>`).join('');
    $('#add-external-model').onclick=()=>localModels.open();
    body.querySelectorAll('[data-model-parameters]').forEach(b=>b.onclick=()=>{collectSettings();const m=state.models.find(m=>m.id===b.dataset.modelParameters);if(m.capabilities.includes('chat'))selectLlmPreferencesModel(m.id);else if(m.capabilities.includes('video'))selectVideoPreferencesModel(m.id);else if(m.capabilities.includes('music'))selectMusicPreferencesModel(m.id);else selectImagePreferencesModel(m.id);settingsTab='advanced';renderSettings();document.querySelector(m.capabilities.includes('chat')?'#llm-settings-card':m.capabilities.includes('video')?'.video-settings':m.capabilities.includes('music')?'.music-settings':'#image-settings-card')?.scrollIntoView({block:'start'});});
    body.querySelectorAll('[data-edit-external]').forEach(b=>b.onclick=()=>localModels.open(state.models.find(m=>m.id===b.dataset.editExternal)));
    body.querySelectorAll('[data-remove-external]').forEach(b=>b.onclick=()=>localModels.remove(state.models.find(m=>m.id===b.dataset.removeExternal)));
    $('#rescan-models').onclick=act(async()=>{collectSettings();state=await api('/state');renderSettings();renderStatus();toast('Cartelle locali aggiornate.');});
    body.querySelectorAll('[data-download]').forEach(b=>{const model=state.models.find(m=>m.id===b.dataset.download);b.disabled=model.complete||model.local;b.onclick=act(async()=>{await api('/downloads',{id:model.id,kind:'model'});await refresh();});});
  }else if(settingsTab==='providers'){
    body.replaceChildren();
  }else{
    body.innerHTML=`<div class="settings-grid"><section class="card" id="llm-settings-card"></section><section class="card" id="image-settings-card"></section><section class="card full"><h3>Preferenze generali</h3>${numberField('threads','Thread CPU · motori chat e immagini',1,64)}<h3>Come vuoi che risponda</h3><label class="field"><span>Istruzioni personali</span><textarea data-setting="system_prompt">${esc(settingsDraft.system_prompt)}</textarea></label><p>Codice evidenziato, Markdown, LaTeX, diagrammi Mermaid e grafici numerici sono già abilitati. Il canvas esporta Word modificabile e PDF/PNG fedeli all'anteprima; formule e figure nel Word sono immagini.</p></section></div>`;
  }
  if(['setup','advanced','models','providers'].includes(settingsTab)){
    const providers=document.createElement('section');providers.className='card api-providers';body.append(providers);
    renderProviders(providers,{state,request:api,changed:async()=>{collectSettings();state=await api('/state');if(settingsDraft.chat_model&&!state.models.some(m=>m.id===settingsDraft.chat_model))syncLlmDraft(settingsDraft,state,'');renderSettings();renderStatus();toast('Collegamento API salvato. Sceglilo per la chat oppure premi Usa in chat.');},use:async id=>{collectSettings();syncLlmDraft(settingsDraft,state,id);selectLlmPreferencesModel(id);state.settings=await api('/settings',settingsDraft);state=await api('/state');renderSettings();renderStatus();toast('Modello API selezionato per chat, router e Assistant.');}});
  }
  if(settingsTab==='setup'||settingsTab==='advanced'){
    const media=document.createElement('section');media.className='card workspace-settings';body.append(media);renderMediaProviders(media,{state,api,changed:async()=>{collectSettings();const next=await api('/state');for(const key of ['chat_model','create_model','edit_model','music_model','video_model'])if(settingsDraft[key]===state.settings[key])settingsDraft[key]=next.settings[key];state=next;renderSettings();renderStatus();},notify:toast,act});
    const server=document.createElement('section');server.className='card workspace-settings';body.append(server);renderServer(server,{state,api,act,refresh});
    const workspace=document.createElement('section');workspace.className='card workspace-settings';body.append(workspace);renderWorkspaceSettings(workspace,{draft:settingsDraft,state,api,pickFile:localModels.pickFile,pickDirectory:localModels.pickDirectory,refresh,notify:toast,changed:scheduleAssessment});
    const tools=document.createElement('section');tools.className='card tools-settings';body.append(tools);renderToolsSettings(tools,{state,draft:settingsDraft,pickDirectory:localModels.pickDirectory,changed:scheduleAssessment,install:act(async kind=>{await api('/downloads',{id:'tools_'+kind,kind:'runtime'});await refresh();}),download:act(async id=>{await api('/downloads',{id,kind:'tool_model'});await refresh();})});
    const video=document.createElement('section');video.className='card video-settings';body.append(video);
    const voice=document.createElement('section');voice.className='card voice-settings';body.append(voice);renderVoiceSettings(voice,{state,draft:settingsDraft,pickDirectory:localModels.pickDirectory,pickFile:localModels.pickFile,changed:scheduleAssessment,install:act(async id=>{await api('/downloads',{id,kind:'runtime'});await refresh();})});
    renderVideoSettings(video,{state,draft:settingsDraft,link:()=>localModels.open(null,'minimax-h3'),edit:localModels.open,pickFile:localModels.pickFile,changed:scheduleAssessment,install:act(async(id='vision')=>{await api('/downloads',{id,kind:'runtime'});await refresh();})});
    const music=document.createElement('section');music.className='card music-settings';body.append(music);
    renderMusicSettings(music,{state,draft:settingsDraft,link:()=>localModels.open(null,'yue2'),edit:localModels.open,changed:()=>{updateDownloads();scheduleAssessment();},
      install:act(async()=>{collectSettings();const backend=settingsDraft.music_backend==='auto'?(settingsDraft.profile!=='cpu'&&settingsDraft.backend==='cuda'?'cuda':'cpu'):settingsDraft.music_backend;if(!['cpu','cuda'].includes(backend))throw Error('YuE2 richiede CPU oppure CUDA.');await api('/downloads',{id:'music_'+backend,kind:'runtime'});await refresh();}),
      download:act(async()=>{await api('/downloads',{id:'yue2-q8',kind:'model'});await refresh();})});
  }
  if(settingsTab==='advanced')renderLlmPreferences($('#llm-settings-card'),settingsDraft,state,scheduleAssessment);
  if(settingsTab==='advanced')renderImagePreferences($('#image-settings-card'),settingsDraft,state,scheduleAssessment);
  if(settingsTab==='advanced'){const folders=document.createElement('section');folders.className='card lora-folder-settings';body.append(folders);loraUI.renderFolders(folders,settingsDraft);}
  if(settingsTab!=='providers')body.insertAdjacentHTML('beforeend','<section id="memory-assessment" class="memory-assessment" aria-live="polite">Rilevamento del computer e stima della memoria…</section>');
  const updateVision=()=>{const m=state.models.find(m=>m.id===settingsDraft.chat_model),el=$('#setup-vision-note');if(el){el.textContent=m?.api?(m.vision?.enabled?'Vision tramite API: le immagini vengono inviate al provider.':'LLM via API · solo testo. Conversazione ed estratti vengono inviati al provider.'):m?.vision?.enabled?'Vision attiva: mmproj caricato automaticamente.':m?.vision?.warning||'Scegli un modello vision per leggere immagini e grafici.';el.classList.toggle('vision-ok',!!m?.vision?.enabled);}};
  body.onchange=e=>{if(e.target.matches('[data-setting]:not([data-llm-setting])')){collectSettings();updateVision();updateDownloads();scheduleAssessment();}};
  updateVision();scheduleAssessment();updateDownloads();
  $('#settings-note').textContent=state.models.find(m=>m.id===settingsDraft.chat_model)?.api?'LLM via API: i contenuti della richiesta vengono inviati al provider.':'Chat e file vengono salvati sul computer.';
}
function updateDownloads(){
  if(!$('#settings').open)return;
  const progress=task=>`<div class="download-status ${task.status==='failed'?'error':''}"><span>${task.status==='running'?esc(task.file.split('/').pop()):({done:'Download completato e verificato',failed:esc(task.error),cancelled:'Interrotto · premi Scarica per riprendere'})[task.status]}</span>${task.status==='running'?`<progress max="${task.total||1}" value="${task.received}"></progress><span>${gb(task.received)} / ${gb(task.total)}</span> <button class="text-button" data-cancel-download="${task.id}">Interrompi</button>`:''}</div>`;
  for(const div of document.querySelectorAll('[data-download-status]')){const task=state.downloads.find(t=>t.id===div.dataset.downloadStatus);div.innerHTML=task?progress(task):'';}
  for(const m of state.models){const ready=document.getElementById('ready-'+m.id);if(ready){ready.textContent=m.complete?'Installato':m.ready?'Solo testo · completa mmproj':'Non installato';ready.classList.toggle('ready',m.ready);}const b=document.querySelector(`[data-download="${m.id}"]`);if(b){b.disabled=m.complete||m.local||state.downloads.some(t=>t.status==='running');b.textContent=m.local?'Locale pronto':m.complete?'Verificato':'Scarica · '+gb(m.size);}}
  const backend=settingsDraft?.profile==='cpu'?'cpu':settingsDraft?.backend;
  if($('#runtime-ready')){$('#runtime-ready').textContent=state.runtimes[backend]?.ready?'Motori installati':gb(state.runtimes[backend]?.size||0);$('#install-runtime').disabled=state.downloads.some(t=>t.status==='running');}
  if($('#vision-runtime-status')){$('#vision-runtime-status').textContent=state.vision_runtime?.ready?'Installato · autonomo':gb(state.runtimes.vision?.size||0);$('#install-vision').disabled=!!state.vision_runtime?.ready||state.downloads.some(t=>t.status==='running');}
  if($('#music-runtime-status')){const kind=settingsDraft.music_backend==='auto'?(settingsDraft.profile!=='cpu'&&settingsDraft.backend==='cuda'?'cuda':'cpu'):settingsDraft.music_backend;const ready=state.music_runtime?.[kind]?.ready;$('#music-runtime-status').textContent=ready?'Installato · '+kind.toUpperCase():gb(state.runtimes['music_'+kind]?.size||0);$('#music-runtime-install').disabled=ready||state.downloads.some(d=>d.status==='running');$('#music-model-download').disabled=!!state.models.find(m=>m.id==='yue2-q8')?.ready||state.downloads.some(d=>d.status==='running');}
  if($('#runtime-downloads'))$('#runtime-downloads').innerHTML=state.downloads.filter(d=>d.kind==='runtime').map(progress).join('');
  document.querySelectorAll('[data-cancel-download]').forEach(b=>b.onclick=act(async()=>{await api('/downloads/'+b.dataset.cancelDownload+'/cancel',{});await refresh();}));
}

$('#chat-advanced').onchange=act(async()=>{const value=$('#chat-advanced').checked;state.settings=await api('/settings',{chat_advanced:value});renderStatus();await renderChat();});
$('#generation-settings').onclick=()=>openSettings('advanced');
$('#vision-enabled').onchange=act(async()=>{state.settings=await api('/settings',{vision_enabled:$('#vision-enabled').checked});renderStatus();toast('Vision '+(state.settings.vision_enabled?(state.models.find(m=>m.id===state.settings.chat_model)?.api?'On · API':'On · '+(state.settings.vision_device==='gpu'?'GPU':'CPU')):'Off')+' dal prossimo messaggio.');});
$('#think-level').onchange=act(async()=>{const level=$('#think-level').value;thinkSaving=true;try{state.settings=await api('/settings',{think_level:level});}finally{thinkSaving=false;renderStatus();}});
$('#composer').onsubmit=act(send);
$('#prompt').onkeydown=act(async e=>{if(e.key==='Enter'&&!e.shiftKey&&!e.isComposing){e.preventDefault();await send(e);}});
$('#prompt').oninput=()=>{$('#prompt').style.height='auto';$('#prompt').style.height=Math.min(180,$('#prompt').scrollHeight)+'px';};
$('#stop').onclick=act(async()=>{const j=userJob();if(j){await api('/jobs/'+j.id+'/cancel',{});await refresh();}});
$('#regenerate').onclick=act(regenerate);
$('#new-chat').onclick=act(newChat);$('#home').onclick=act(async e=>{e.preventDefault();await newChat();});
$('#search').oninput=renderSidebar;
document.querySelectorAll('[data-filter]').forEach(b=>b.onclick=()=>{filter=b.dataset.filter;collection=null;project=null;renderSidebar();});
$('#new-collection').onclick=act(async()=>{const name=await ask('Nuova raccolta');if(name){await api('/collections',{name});await refresh();}});
$('#chat-list').onclick=act(async e=>{const open=e.target.closest('[data-chat]'),menu=e.target.closest('[data-chat-menu]');if(open)await openChat(open.dataset.chat);if(menu)chatMenu(menu.dataset.chatMenu,menu);});
$('#collections').onclick=act(async e=>{const open=e.target.closest('[data-collection]'),menu=e.target.closest('[data-collection-menu]');if(open){collection=open.dataset.collection;project=null;filter='all';renderSidebar();}if(menu)collectionMenu(menu.dataset.collectionMenu,menu);});
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
$('#memory-status').onclick=()=>openSettings();
$('#settings-open').onclick=()=>openSettings();$('#setup-nudge').onclick=()=>openSettings();$('#settings-close').onclick=()=>$('#settings').close();
document.querySelectorAll('[data-tab]').forEach(b=>b.onclick=()=>{collectSettings();settingsTab=b.dataset.tab;renderSettings();});
$('#settings-save').onclick=async()=>{
  const button=$('#settings-save');if(button.disabled)return;
  settingsError();button.disabled=true;button.textContent='Salvataggio…';
  try{
    collectSettings();settingsDraft.setup_done=true;state.settings=await api('/settings',settingsDraft);
    $('#settings').close();toast('Impostazioni salvate.');await refresh();
  }catch(e){settingsError(e.message);}
  finally{button.disabled=false;button.textContent='Salva impostazioni';}
};
$('#canvas-toggle').onclick=act(()=>toggleCanvas());$('#canvas-close').onclick=act(()=>toggleCanvas(false));
$('#canvas-follow').onchange=act(async()=>{if($('#canvas-follow').checked)await followCanvas();else{canvasFollow=false;canvasSelection++;renderCanvasHistory();}});
$('#canvas-history').onchange=act(()=>selectCanvasArtifact($('#canvas-history').value));
$('#canvas-previous').onclick=act(()=>{const i=canvasHistory.items.findIndex(x=>x.id===canvas.id);if(i>0)return selectCanvasArtifact(canvasHistory.items[i-1].id);});
$('#canvas-next').onclick=act(()=>{const i=canvasHistory.items.findIndex(x=>x.id===canvas.id);if(i>=0&&i<canvasHistory.items.length-1)return selectCanvasArtifact(canvasHistory.items[i+1].id);});
$('#canvas-current').onclick=act(followCanvas);
$('#canvas-restore').onclick=act(async()=>{
  await persistCanvas();const id=current,value=await api('/canvas/'+id+'/history/'+canvas.id+'/restore',{});
  if(current!==id)return;canvasFollow=true;canvasSelection++;await loadCanvasHistory(id);await setCanvas(value);renderStatus();toast('Artefatto in uso: le prossime richieste nel canvas partiranno da questo contenuto.');
});
$('#canvas-preview-tab').onclick=act(async()=>{canvasEditing=false;await persistCanvas();await renderCanvas();});
$('#canvas-source-tab').onclick=act(async()=>{if(activeJob()?.canvas)throw Error('Attendi la scrittura del motore prima di modificare.');canvasEditing=true;await renderCanvas();$('#canvas-source').focus();});
$('#canvas-write').onclick=$('#canvas-source-tab').onclick;
$('#canvas-title').oninput=canvasChanged;$('#canvas-source').oninput=canvasChanged;$('#canvas-save').onclick=act(async()=>{await persistCanvas();toast('Canvas salvato.');});
document.querySelector('[data-export="md"]').insertAdjacentHTML('afterend','<button class="btn small" data-export="html" hidden>HTML</button><button class="btn small" data-export="pptx" hidden>PowerPoint</button>');
document.querySelectorAll('[data-export]').forEach(b=>b.onclick=act(async()=>{if(activeJob()?.canvas&&canvas.id===canvasHistory.active_id)throw Error('Attendi che il documento sia completo prima di esportare.');await persistCanvas();if(!canvas.content&&!canvas.media.length)throw Error('Il canvas è vuoto.');canvasEditing=false;await renderCanvas();const root=$('#canvas-preview');$('#canvas-panel').classList.add('exporting');try{if(b.dataset.export==='md')saveBlob(new Blob([canvas.content],{type:'text/markdown;charset=utf-8'}),canvas.title+'.md');else if(readDeck(canvas.content))await exportSlides(canvas,b.dataset.export,state.token);else{if(b.dataset.export==='pdf')await exportPdf(root,canvas.title,state.token);if(b.dataset.export==='docx')await exportDocx(root,canvas.title);if(b.dataset.export==='png')await exportPng(root,canvas.title);}toast('Esportazione pronta.');}finally{$('#canvas-panel').classList.remove('exporting');}}));
composerUI=initComposerPanel({getState:()=>state,visualControls,getAttachments:()=>attachments,notify:toast});
manimPresentation=initManimPresentation({getAttachments:()=>attachments,getCanvas:()=>canvas,getState:()=>state,getChatId:()=>current,api,notify:toast});
document.querySelector('#composer').addEventListener('change',()=>manimPresentation.render());
initWorkspaceLayout();
await refresh();
window.addEventListener('beforeunload',e=>{if(canvasDirty){e.preventDefault();e.returnValue='';}});

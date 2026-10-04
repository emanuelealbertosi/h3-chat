import {uploadProjectDocument,projectUploadLimits} from './project-upload.js';
const extensions=new Set(['pdf','docx','txt','md','csv','json','py','js','ts','html','css','tex']);
const supported=file=>extensions.has(file.name.split('.').at(-1).toLowerCase());
const relativePaths=new WeakMap();

async function droppedFiles(transfer){
  const items=[...transfer.items],fallback=[...transfer.files];
  const entries=items.filter(i=>i.kind==='file').map(i=>i.webkitGetAsEntry?.()).filter(Boolean);
  if(!entries.length)return fallback;
  const files=[];let visited=0;
  async function walk(entry,depth=0,prefix=''){
    if(++visited>5000||files.length>=500)throw Error('Selezione troppo grande: importa fino a 500 documenti per volta.');
    if(entry.isFile){const file=await new Promise((resolve,reject)=>entry.file(resolve,reject));if(supported(file)){relativePaths.set(file,prefix+file.name);files.push(file);}return;}
    if(depth>=4||['.git','node_modules','__pycache__','.venv'].includes(entry.name))return;
    const reader=entry.createReader();
    for(;;){const batch=await new Promise((resolve,reject)=>reader.readEntries(resolve,reject));if(!batch.length)break;for(const child of batch)await walk(child,depth+1,prefix+entry.name+'/');}
  }
  for(const entry of entries)await walk(entry);
  return files;
}

export function initProjectImports({api,getProjectId,getToken,getLimits,onChange,showError,notify}){
  const $=s=>document.querySelector(s);let busy=false,indexingState=false;
  const initialLimits=getLimits?.()||projectUploadLimits;
  $('#project-documents').querySelector('p').textContent='Importa documenti dal tuo dispositivo: la copia del progetto resta disponibile anche nelle prossime chat.';
  $('#project-documents').querySelector('.field').insertAdjacentHTML('beforebegin',`<div class="project-import-actions"><button id="project-files" class="btn primary">Scegli file…</button><button id="project-import-folder" class="btn">Importa cartella…</button><input id="project-file-input" type="file" multiple accept=".pdf,.docx,.txt,.md,.csv,.json,.py,.js,.ts,.html,.css,.tex" hidden><input id="project-folder-input" type="file" multiple webkitdirectory hidden></div><div id="project-dropzone" class="project-dropzone" role="button" tabindex="0" aria-label="Scegli o trascina documenti per il progetto"><strong>Trascina qui file o cartelle</strong><span>PDF, Word e testo · fino a ${Math.round(initialLimits.file_bytes/1024**2)} MB per file · PDF fino a ${initialLimits.pdf_pages||3000} pagine</span><small>I documenti vengono copiati nel progetto. Gli originali restano sul tuo dispositivo.</small></div><p id="project-import-status" role="status" aria-live="polite" hidden></p>`);
  const pathField=$('#project-paths').closest('label'),actions=$('#project-folder').parentElement;
  const advanced=document.createElement('details');advanced.className='project-path-options';advanced.innerHTML='<summary>Collega percorsi originali · senza copia</summary><p>Usa file e cartelle sul computer dove gira H3-Chat. Le cartelle collegate vengono controllate per nuovi documenti e modifiche.</p>';
  pathField.before(advanced);advanced.append(pathField,actions);$('#project-folder').textContent='Collega cartella originale…';
  function controls(indexing){if(indexing!==undefined)indexingState=indexing;for(const id of ['project-files','project-import-folder','project-file-input','project-folder-input'])$('#'+id).disabled=busy||indexingState;$('#project-dropzone').setAttribute('aria-disabled',String(busy||indexingState));}
  async function importFiles(files){
    if(busy)return;const id=getProjectId();if(!id)throw Error('Salva prima il progetto.');
    const chosen=[...files].filter(supported),skipped=files.length-chosen.length;
    if(!chosen.length)throw Error('Scegli PDF, Word .docx oppure documenti di testo/codice.');
    if(chosen.length>500)throw Error('Seleziona fino a 500 documenti per volta.');
    const limits=getLimits?.()||projectUploadLimits;
    const oversized=chosen.find(f=>f.size>limits.file_bytes||f.size===0);if(oversized)throw Error(oversized.name+': il documento è vuoto o supera '+Math.round(limits.file_bytes/1024**2)+' MB.');
    busy=true;controls();$('#project-error').hidden=true;$('#project-add').disabled=true;$('#project-refresh').disabled=true;$('#project-delete').disabled=true;
    const status=$('#project-import-status');status.hidden=false;let imported=0,duplicates=0;
    try{
      for(const [index,file] of chosen.entries()){
        status.textContent=`Importazione ${index+1}/${chosen.length} · ${file.name}`;
        const result=await uploadProjectDocument(file,{project:id,relativePath:file.webkitRelativePath||relativePaths.get(file)||file.name,api,getToken,limits,onProgress:(bytes,total)=>{status.textContent=`Importazione ${index+1}/${chosen.length} · ${file.name} · ${Math.round(bytes/total*100)}%`;}});if(result.duplicate)duplicates++;else imported++;
      }
      status.textContent=`${imported} documenti importati${duplicates?' · '+duplicates+' già presenti':''}${skipped?' · '+skipped+' file non supportati ignorati':''}. Indicizzazione in corso…`;
      notify(status.textContent);
    }catch(e){status.textContent=`Importazione interrotta dopo ${imported} documenti nuovi: ${e.message}`;showError(e);}
    finally{
      try{if(imported||duplicates)await api('/projects/'+id+'/refresh',{});await onChange(id);}finally{busy=false;controls();}
    }
  }
  const safe=fn=>async(...args)=>{try{await fn(...args);}catch(e){showError(e);}};
  $('#project-files').onclick=()=>$('#project-file-input').click();$('#project-import-folder').onclick=()=>$('#project-folder-input').click();
  for(const id of ['project-file-input','project-folder-input'])$('#'+id).onchange=safe(async e=>{const files=[...e.target.files];e.target.value='';if(files.length)await importFiles(files);});
  const zone=$('#project-dropzone'),host=$('#project-documents');
  zone.onclick=()=>{if(!busy&&zone.getAttribute('aria-disabled')!=='true')$('#project-file-input').click();};zone.onkeydown=e=>{if(['Enter',' '].includes(e.key)){e.preventDefault();zone.click();}};
  host.ondragover=e=>{e.preventDefault();zone.classList.add('dragging');};host.ondragleave=e=>{if(!host.contains(e.relatedTarget))zone.classList.remove('dragging');};
  host.ondrop=safe(async e=>{e.preventDefault();e.stopPropagation();zone.classList.remove('dragging');if(zone.getAttribute('aria-disabled')==='true')return;await importFiles(await droppedFiles(e.dataTransfer));});
  $('#project-dialog').addEventListener('dragover',e=>e.preventDefault());$('#project-dialog').addEventListener('drop',e=>e.preventDefault());
  return {controls,isBusy:()=>busy};
}

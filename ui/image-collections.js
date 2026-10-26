import JSZip from 'jszip';
import {uploadFile} from './file-upload.js';
import {openImageZoom} from './image-zoom.js';
import {deleteCollections,collectionDeleteButton} from './collection-delete.js';

export async function downloadCollection(api,id){
 const result=await api('/image-collections/'+id+'/export',{});const a=document.createElement('a');a.href=result.url;a.download=result.name;a.click();
}
export function collectionExportButton(target,api,id,onRemoved){
 if(!api)return;const b=document.createElement('button');b.type='button';b.className='btn small no-export';b.textContent='Esporta lotto ZIP';
 b.onclick=async()=>{b.disabled=true;try{await downloadCollection(api,id);}catch(e){b.textContent=e.message;}finally{b.disabled=false;}};target.append(b);
 collectionDeleteButton(target,api,id,onRemoved);
}
export function openImageCollections({api,onSelect,onCreate,slideMode=false,onGenerate,state,projectId,onConfigureVision}){
 const dialog=document.createElement('dialog');dialog.className='gallery-dialog image-collections-dialog';dialog.ariaLabel='Lotti immagini e sfondi';
 dialog.innerHTML='<header><h2>Lotti immagini e sfondi</h2><button type="button" class="icon-button" data-close aria-label="Chiudi lotti">×</button></header><div class="project-actions"><button type="button" class="btn" data-import>Importa lotto ZIP</button><input type="file" accept=".zip" data-file hidden><button type="button" class="btn" data-create>Crea lotto dalla galleria</button><button type="button" class="btn" data-refresh>Aggiorna</button></div><p class="small-note">Il prompt originale descrive la richiesta. Le didascalie Vision descrivono il risultato effettivo e si possono correggere. Aggiungi il lotto al progetto RAG per cercarlo per contenuto. Le immagini senza descrizione non vengono presentate come catalogate.</p><p data-status role="status"></p><div data-lots></div>';document.body.append(dialog);dialog.showModal();
 const q=s=>dialog.querySelector(s),status=q('[data-status]');let busy=false;const selected=new Set();let visible=[];
 const selection=document.createElement('div');selection.className='project-actions';const all=document.createElement('input'),allLabel=document.createElement('label'),deleteSelected=document.createElement('button');all.type='checkbox';all.ariaLabel='Seleziona tutti i lotti';allLabel.append(all,' Seleziona tutti');deleteSelected.type='button';deleteSelected.className='btn';selection.append(allLabel,deleteSelected);q('[data-lots]').before(selection);
 function selectionState(){deleteSelected.disabled=!selected.size||busy;deleteSelected.textContent='Elimina selezionati ('+selected.size+')';all.checked=visible.length>0&&visible.every(v=>selected.has(v.id));all.indeterminate=selected.size>0&&!all.checked;}
 all.onchange=()=>{for(const v of visible)all.checked?selected.add(v.id):selected.delete(v.id);for(const c of q('[data-lots]').querySelectorAll('[data-lot-selection]'))c.checked=selected.has(c.dataset.lotSelection);selectionState();};
 deleteSelected.onclick=async()=>{if(busy)return;try{const result=await deleteCollections(api,[...selected]);if(result){for(const id of result.removed)selected.delete(id);await load();status.textContent=result.removed.length+' lotti rimossi · '+result.files_deleted+' file eliminati'+(result.errors.length?' · '+result.errors.length+' file non eliminati.':'');}}catch(error){status.textContent=error.message;}finally{selectionState();}};
 const run=fn=>async()=>{if(busy)return;busy=true;dialog.setAttribute('aria-busy','true');status.textContent='Operazione in corso…';try{await fn();}catch(e){status.textContent=e.message;}finally{busy=false;dialog.removeAttribute('aria-busy');}};
 q('[data-close]').onclick=()=>dialog.close();dialog.addEventListener('close',()=>dialog.remove());
 if(onConfigureVision&&state?.models?.some(m=>m.id===state.settings?.chat_model&&m.api)){const configure=document.createElement('button');configure.type='button';configure.className='btn';configure.textContent='Configura modello Vision';configure.onclick=async()=>{dialog.close();await onConfigureVision();};q('.project-actions').append(configure);}
 if(slideMode){
  dialog.ariaLabel='Immagini per le slide';q('h2').textContent='Immagini per le slide';
  const form=document.createElement('form');form.className='card slide-lot-generation';
  form.innerHTML='<h3>Crea un lotto di illustrazioni</h3><div class="settings-grid"><label>Nome del lotto<input name="name" required maxlength="150" value="Illustrazioni per le slide"></label><label>Numero di immagini<input name="count" type="number" min="1" max="50" value="4" required></label><label>Formato<select name="format"><option>16:9</option><option>9:16</option><option>4:3</option><option>3:4</option><option>1:1</option><option>3:2</option><option>2:3</option></select></label><label>Modello immagini<select name="model"></select></label></div><label>Tema e istruzioni<textarea name="prompt" rows="4" required maxlength="16000" placeholder="Es. illustrazioni sulle porte logiche, stile fumettoso. La prima…, la seconda…"></textarea></label><label><input name="rag" type="checkbox"> Usa le fonti RAG del progetto della chat per pianificare le immagini</label><p class="small-note" data-project-note></p><button class="btn primary" type="submit">Genera solo il lotto</button><p class="small-note">Fino a 50 immagini. Assistant prepara il piano, in gruppi per i lotti grandi restando caricato; poi le immagini vengono generate in sequenza e salvate nel lotto. Non vengono create slide. Passi, seed e altri parametri seguono il modello o le richieste esplicite nel testo.</p>';
  const fields=form.elements;fields.model.add(new Option('Predefinito dalle impostazioni',''));for(const m of state?.models||[])if(m.ready&&m.capabilities.includes('create'))fields.model.add(new Option(m.name,m.id));
  fields.rag.disabled=!projectId;form.querySelector('[data-project-note]').textContent=projectId?'Progetto: '+(state?.projects?.find(p=>p.id===projectId)?.name||'progetto della chat'):'Per usare il RAG, apri prima una chat appartenente a un progetto con fonti.';
  fields.prompt.value=document.querySelector('#prompt')?.value||'';q('[data-lots]').before(form);
  form.onsubmit=e=>{e.preventDefault();run(async()=>{if(!form.reportValidity())return;const options={name:fields.name.value,count:Number(fields.count.value),format:fields.format.value,model:fields.model.value,rag:fields.rag.checked};await onGenerate({prompt:fields.prompt.value,options});dialog.close();})();};
 }
 async function load(){
  const [data,projects]=await Promise.all([api('/image-collections'),api('/state')]);q('[data-lots]').replaceChildren();
  visible=data.items.filter(s=>!slideMode||s.kind==='images');for(const id of selected)if(!visible.some(v=>v.id===id))selected.delete(id);
  const projectList=Array.isArray(projects)?projects:projects.items||projects.projects||[];
  for(const set of visible){
   const section=document.createElement('section');section.className='card';const heading=document.createElement('h3');heading.textContent=set.name+' · '+set.available+' immagini';
   const controls=document.createElement('div');controls.className='project-actions';
   const selectionLabel=document.createElement('label'),checkLot=document.createElement('input');checkLot.type='checkbox';checkLot.dataset.lotSelection=set.id;checkLot.ariaLabel='Seleziona lotto '+set.name;checkLot.checked=selected.has(set.id);checkLot.onchange=()=>{checkLot.checked?selected.add(set.id):selected.delete(set.id);selectionState();};selectionLabel.append(checkLot,' Seleziona lotto');controls.append(selectionLabel);
   const caption=document.createElement('button');caption.type='button';caption.textContent='Analizza con Vision';caption.disabled=set.captioned===set.available;caption.onclick=run(async()=>{const job=await api('/image-collections/'+set.id+'/caption',{});status.textContent='Catalogazione in coda · '+job.job_id.slice(0,8)+'. Le descrizioni già completate vengono conservate. Premi Aggiorna per rileggerle.';});
   const rename=document.createElement('button');rename.type='button';rename.textContent='Rinomina';rename.onclick=()=>nameDialog(set);
   const select=document.createElement('select');select.ariaLabel='Progetto RAG per '+set.name;select.add(new Option('Scegli progetto RAG…',''));for(const p of projectList)select.add(new Option(p.name,p.id));
   const rag=document.createElement('button');rag.type='button';rag.textContent='Aggiungi al RAG';rag.onclick=run(async()=>{if(!select.value)throw Error('Scegli un progetto RAG.');await api('/image-collections/'+set.id+'/rag',{project_id:select.value});status.textContent='Immagini aggiunte al progetto. Indicizzazione avviata: controlla l’avanzamento nel progetto.';});
   controls.append(rename,caption,select,rag);collectionExportButton(controls,api,set.id,async()=>{selected.delete(set.id);await load();});
   if(slideMode){const label=document.createElement('label'),check=document.createElement('input');check.type='checkbox';check.checked=set.semantic_enabled??set.captioned>0;check.onchange=run(async()=>{await api('/image-collections/'+set.id,{semantic_enabled:check.checked},'PATCH');status.textContent=check.checked?'Catalogazione del lotto attiva: le descrizioni disponibili guideranno la scelta nelle slide.':'Catalogazione disattivata: le slide useranno la rotazione delle immagini.';});label.append(check,' Usa catalogazione del lotto per scegliere le figure nelle slide');controls.append(label);}
   const note=document.createElement('p');note.className='small-note';note.textContent=set.captioned+'/'+set.available+' didascalie disponibili · '+(set.kind==='backgrounds'?'Sfondi':'Immagini')+' · '+new Date(set.created*1000).toLocaleString();
   const grid=document.createElement('div');grid.className='gallery-grid';
   for(const item of set.images){
    const m=item.media,card=document.createElement('article'),zoom=document.createElement('button'),img=document.createElement('img');zoom.type='button';img.src='/media/'+m.path;img.alt=m.name;img.loading='lazy';img.style.cssText='width:100%;height:130px;object-fit:contain';zoom.append(img);zoom.onclick=()=>openImageZoom(img.src,m.name,zoom);const label=document.createElement('small');label.textContent=item.caption?(item.caption_source==='vision'?'Analizzata con Vision':item.caption_source==='manual'?'Didascalia modificata':'Didascalia importata'):'Da analizzare';
    const field=document.createElement('textarea');field.rows=3;field.maxLength=1200;field.ariaLabel='Descrizione di '+m.name;field.value=item.caption||'';field.placeholder='Descrizione del contenuto effettivo';
    const save=document.createElement('button');save.type='button';save.textContent='Salva descrizione';save.onclick=run(async()=>{await api('/image-collections/'+set.id,{image_id:m.id,caption:field.value},'PATCH');status.textContent='Descrizione salvata. Aggiorna l’indice RAG del progetto se già presente.';label.textContent=field.value?'Didascalia modificata':'Da analizzare';});
    card.append(zoom,label,field,save);
    if(onSelect){const use=document.createElement('button');use.type='button';use.textContent='Usa immagine';use.onclick=run(async()=>{await onSelect([m]);dialog.close();});card.append(use);}
    grid.append(card);
   }
   section.append(heading,note,controls,grid);q('[data-lots]').append(section);
  }
  status.textContent=data.items.length?'Lotti salvati: '+data.items.length:'Nessun lotto salvato. Puoi importarne uno oppure crearlo dalla galleria.';
  selectionState();
 }
 function nameDialog(set){
  const d=document.createElement('dialog');d.className='prompt-options-dialog';const form=document.createElement('form'),label=document.createElement('label'),input=document.createElement('input'),save=document.createElement('button');input.value=set.name;input.required=true;input.maxLength=150;label.textContent='Nome del lotto';label.append(input);save.textContent='Salva';form.append(label,save);d.append(form);document.body.append(d);d.showModal();d.addEventListener('close',()=>d.remove());form.onsubmit=async e=>{e.preventDefault();save.disabled=true;try{await api('/image-collections/'+set.id,{name:input.value},'PATCH');d.close();await load();}catch(error){status.textContent=error.message;}finally{save.disabled=false;}};
 }
 q('[data-refresh]').onclick=run(load);q('[data-import]').onclick=()=>q('[data-file]').click();
 q('[data-create]').hidden=!onCreate;q('[data-create]').onclick=()=>onCreate(async media=>{await api('/image-collections',{name:'Lotto dalla galleria',images:media.map(m=>({id:m.id}))});await load();});
 q('[data-file]').onchange=run(async()=>{
  const file=q('[data-file]').files[0];if(!file)return;if(file.size>256*1024**2)throw Error('ZIP oltre 256 MB.');
  const zip=await JSZip.loadAsync(file),manifestFile=zip.file('manifest.json');if(!manifestFile||manifestFile._data.uncompressedSize>1024**2)throw Error('Manifest del lotto assente o troppo grande.');
  const manifest=JSON.parse(await manifestFile.async('string'));
  if(manifest.version!==1||!['images','backgrounds'].includes(manifest.kind)||!Array.isArray(manifest.images)||!manifest.images.length||manifest.images.length>128)throw Error('Formato del lotto non valido.');
  if(slideMode&&manifest.kind!=='images')throw Error('Questo è un lotto di sfondi: importalo nella raccolta sfondi. Qui scegli un lotto di illustrazioni.');
  const members=new Set();let total=0;
  for(const item of manifest.images){const entry=zip.file(item.file);if(!/^images\/[\w.-]+\.(png|jpg|jpeg|webp)$/i.test(item.file)||members.has(item.file)||!entry||entry._data.uncompressedSize>32*1024**2)throw Error('File del lotto non valido o troppo grande.');members.add(item.file);total+=entry._data.uncompressedSize;}
  if(total>256*1024**2)throw Error('Immagini del lotto oltre 256 MB.');
  const images=[];
  for(const [i,item] of manifest.images.entries()){
   status.textContent='Importazione immagine '+(i+1)+'/'+manifest.images.length;const raw=await zip.file(item.file).async('uint8array');
   const digest=[...new Uint8Array(await crypto.subtle.digest('SHA-256',raw))].map(x=>x.toString(16).padStart(2,'0')).join('');if(digest!==item.sha256)throw Error('Integrità immagine non valida: '+item.file);
   const asset=await uploadFile(new File([raw],item.file.split('/').pop()),{api});images.push({id:asset.id,caption:item.caption||'',prompt:item.prompt||'',recipe:item.recipe||{}});
  }
  await api('/image-collections',{name:manifest.name,kind:manifest.kind,options:manifest.options,prompt:manifest.prompt,images});await load();status.textContent='Lotto importato. Le didascalie importate sono modificabili e distinte dalle analisi Vision eseguite qui.';
 });run(load)();return dialog;
}

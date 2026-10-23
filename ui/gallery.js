import {uploadFile} from './file-upload.js';
import {escape as esc} from './render.js';
import {addBrowserPreview} from './video-browser-preview.js';
import {appendGalleryDetails} from './gallery-details.js';
import {appendCreationDetails} from './creation-details.js';

export function openGallery({api,onSelect,kind='all',multiple=true,browse=false,actions={}}){
 const dialog=document.createElement('dialog');dialog.className='gallery-dialog';dialog.ariaLabel='Galleria';
 dialog.innerHTML=`<header><div><span class="eyebrow">I TUOI FILE</span><h2>Galleria</h2></div><button type="button" class="icon-button" data-close aria-label="Chiudi galleria">×</button></header><div class="gallery-filters"><input data-query type="search" placeholder="Cerca per nome…" aria-label="Cerca nella galleria"><select data-kind aria-label="Tipo di file">${[['all','Tutti'],['image','Immagini'],['audio','Audio'],['video','Video'],['document','Documenti'],['model','Modelli 3D'],['other','Altri file']].map(([v,t])=>`<option value="${v}">${t}</option>`).join('')}</select><select data-origin aria-label="Origine"><option value="all">Caricati e generati</option><option value="uploaded">Caricati</option><option value="generated">Generati</option></select></div><p data-status role="status"></p><div class="gallery-grid"></div><footer><button class="btn" data-more hidden>Altri file</button><span data-count></span><button class="btn primary" data-select disabled>Usa i file selezionati</button></footer>`;
 document.body.append(dialog);const q=s=>dialog.querySelector(s);q('[data-kind]').value=kind;let offset=0,revision=0,selected=new Map(),timer,items=[],canManage=false;const deleting=new Map();
 const removeSelected=document.createElement('button'),selectVisible=document.createElement('button'),deleteCount=document.createElement('span');
 removeSelected.type=selectVisible.type='button';removeSelected.className=selectVisible.className='btn';removeSelected.textContent='Elimina selezionati';selectVisible.textContent='Seleziona visibili';removeSelected.disabled=true;removeSelected.hidden=selectVisible.hidden=true;deleteCount.setAttribute('role','status');
 q('footer').prepend(selectVisible,deleteCount,removeSelected);
 const deletionSelection=()=>{removeSelected.disabled=!deleting.size;deleteCount.textContent=deleting.size?deleting.size+' da eliminare':'';for(const box of dialog.querySelectorAll('[data-delete-id]'))box.checked=deleting.has(box.dataset.deleteId);};
 selectVisible.onclick=()=>{const all=items.length&&items.every(i=>deleting.has(i.id));for(const item of items){if(all)deleting.delete(item.id);else deleting.set(item.id,item);}deletionSelection();};
 removeSelected.onclick=()=>confirmDelete([...deleting.values()]);
 const sort=document.createElement('select');sort.ariaLabel='Ordina la galleria';sort.disabled=true;
 for(const [value,label] of [['modified_desc','Ultima modifica · più recenti'],['modified_asc','Ultima modifica · meno recenti'],['added_desc','Aggiunta / caricamento · più recenti'],['added_asc','Aggiunta / caricamento · meno recenti'],['name_asc','Nome · A–Z'],['name_desc','Nome · Z–A'],['type_asc','Tipo · A–Z'],['type_desc','Tipo · Z–A']])sort.add(new Option(label,value));
 q('.gallery-filters').append(sort);sort.onchange=()=>load();
 const project=document.createElement('select');project.ariaLabel='Filtra per progetto';project.add(new Option('Tutti i progetti',''));q('.gallery-filters').append(project);project.onchange=()=>load();
 q('[data-select]').hidden=browse;q('[data-count]').hidden=browse;
 q('[data-close]').onclick=()=>dialog.close();dialog.onclose=()=>{clearTimeout(timer);revision++;dialog.remove();};
 const status=t=>q('[data-status]').textContent=t;
 const selection=()=>{q('[data-select]').disabled=!selected.size;q('[data-count]').textContent=selected.size?selected.size+' selezionati':'';};
 async function load(append=false){
  if(append&&q('[data-more]').disabled)return;
  const request=++revision;q('[data-more]').disabled=true;q('.gallery-grid').setAttribute('aria-busy','true');if(!append){offset=0;items=[];q('.gallery-grid').replaceChildren();}status('Caricamento…');
  try{const params=new URLSearchParams({q:q('[data-query]').value,kind:q('[data-kind]').value,origin:q('[data-origin]').value,offset:String(offset),sort:sort.value,project_id:project.value}),result=await api('/gallery?'+params);
   if(request!==revision||!dialog.open)return;offset=result.offset;q('[data-more]').hidden=!result.more;status(result.total?result.total+' file nella tua galleria':'La galleria è vuota. Carica un file o crea un contenuto nella chat.');
   if(result.projects){const chosen=project.value;project.replaceChildren(new Option('Tutti i progetti',''));for(const p of result.projects)project.add(new Option(p.name,p.id));project.value=chosen;}
   sort.disabled=!result.sorting;sort.title=result.sorting?'':'L’ordinamento sarà disponibile dopo l’aggiornamento del server a generazione terminata.';
   const fragment=document.createDocumentFragment();
   canManage=!!result.manage;removeSelected.hidden=selectVisible.hidden=!canManage;items.push(...result.items);for(const item of result.items){const card=document.createElement('article');card.className='gallery-card';
    if(canManage){const label=document.createElement('label'),box=document.createElement('input');label.className='gallery-delete-pick';box.type='checkbox';box.dataset.deleteId=item.id;box.ariaLabel='Seleziona per eliminare '+item.name;box.checked=deleting.has(item.id);box.onchange=()=>{if(box.checked)deleting.set(item.id,item);else deleting.delete(item.id);deletionSelection();};label.append(box,' Seleziona per eliminare');card.append(label);}
    const pick=document.createElement('button');pick.type='button';pick.className='gallery-pick';pick.ariaLabel=(item.timeline_only?'Apri ':'Seleziona ')+item.name;pick.setAttribute('aria-pressed',String(selected.has(item.id)));
    const media=item.mime.startsWith('image/')?`<img loading="lazy" decoding="async" width="180" height="110" src="${esc(item.url)}" alt="">`:`<span class="gallery-symbol">${item.mime.startsWith('audio/')?'♫':item.mime.startsWith('video/')?'▷':'▤'}</span>`;
    pick.innerHTML=media+`<strong>${esc(item.name)}</strong><small>${item.timeline_only?'Montaggio salvato':(item.origin==='generated'?'Generato':'Caricato')+' · '+(item.size/1024/1024).toLocaleString('it-IT',{maximumFractionDigits:1})+' MB'}</small>`;
    appendGalleryDetails(pick,item);
    pick.onclick=()=>{if(browse||item.timeline_only){show(item);return;}if(selected.has(item.id))selected.delete(item.id);else{if(!multiple){selected.clear();for(const b of dialog.querySelectorAll('.gallery-pick'))b.setAttribute('aria-pressed','false');}selected.set(item.id,item);}pick.setAttribute('aria-pressed',String(selected.has(item.id)));selection();};card.append(pick);
    if(browse)pick.ariaLabel='Apri '+item.name;
    const preview=document.createElement('button');preview.type='button';preview.className='text-button';preview.textContent='Anteprima e azioni';preview.onclick=()=>show(item);card.append(preview);
    if(item.mime.startsWith('audio/')){const audio=document.createElement('audio');audio.controls=true;audio.preload='none';audio.src=item.url;card.append(audio);}
    fragment.append(card);
   }
   q('.gallery-grid').append(fragment);
  }catch(e){if(request===revision)status(e.message);}
  finally{if(request===revision&&dialog.open){q('[data-more]').disabled=false;q('.gallery-grid').setAttribute('aria-busy','false');}}
 }
 async function confirmDelete(chosen,onRemoved=()=>{}){
  if(!chosen.length)return;const d=document.createElement('dialog');d.className='prompt-options-dialog gallery-delete-dialog';d.ariaLabel='Elimina asset';
  d.innerHTML='<header><h2>Elimina asset</h2><button type="button" class="icon-button" data-cancel aria-label="Chiudi eliminazione">×</button></header><div class="prompt-options-body"><p data-summary></p><ul data-names></ul><fieldset><legend>Cosa vuoi eliminare?</legend><label class="field"><span><input type="radio" name="delete-mode" value="gallery" checked> Solo dalla galleria · conserva i file sul disco</span></label><label class="field"><span><input type="radio" name="delete-mode" value="files" disabled> Anche i file dal disco · eliminazione definitiva</span></label></fieldset><p data-warning class="small-note">Le chat, le timeline e i lavori già salvati continuano a trovare i file.</p><p data-blocked class="small-note"></p><p data-error role="alert" class="settings-error" hidden></p></div><footer><button type="button" class="btn" data-back>Annulla</button><button type="button" class="btn primary" data-confirm disabled>Rimuovi dalla galleria</button></footer>';
  document.body.append(d);const p=s=>d.querySelector(s);let busy=false,plan=null;p('[data-summary]').textContent=chosen.length+' asset selezionati. Controllo dei file…';
  for(const item of chosen){const li=document.createElement('li');li.textContent=item.name;p('[data-names]').append(li);}
  p('[data-cancel]').onclick=p('[data-back]').onclick=()=>d.close();d.oncancel=e=>{if(busy)e.preventDefault();};d.onclose=()=>d.remove();d.showModal();
  const mode=()=>p('input[value=files]').checked;
  for(const radio of d.querySelectorAll('input'))radio.onchange=()=>{p('[data-warning]').textContent=mode()?'I file selezionati saranno cancellati definitivamente. Le chat e le timeline che li usano non potranno più aprirli. Gli altri file nelle stesse cartelle restano salvati.':'Le chat, le timeline e i lavori già salvati continuano a trovare i file.';p('[data-confirm]').textContent=mode()?'Elimina anche dal disco':'Rimuovi dalla galleria';};
  try{plan=await api('/gallery/delete-plan',{ids:chosen.map(i=>i.id)});if(!d.open)return;p('[data-summary]').textContent=plan.count+' asset · '+(plan.bytes/1024/1024).toLocaleString('it-IT',{maximumFractionDigits:1})+' MB';p('input[value=files]').disabled=!plan.can_delete_files;p('[data-blocked]').textContent=[...new Set(plan.items.filter(i=>!i.file_deletion_allowed).map(i=>i.reason))].join(' ');p('[data-confirm]').disabled=false;}catch(e){p('[data-error]').hidden=false;p('[data-error]').textContent=e.message;}
  p('[data-confirm]').onclick=async()=>{if(busy||!plan)return;busy=true;for(const b of d.querySelectorAll('button,input'))b.disabled=true;try{
   const result=await api('/gallery/delete',{ids:chosen.map(i=>i.id),delete_files:mode(),confirmed:mode(),snapshot:plan.snapshot});
   for(const id of result.removed){selected.delete(id);deleting.delete(id);}selection();deletionSelection();onRemoved(result.removed);await load();
   status(result.removed.length+(result.files_preserved?' asset rimossi dalla galleria; file conservati.':' asset eliminati anche dal disco.'));
   if(result.errors?.length){p('[data-error]').hidden=false;p('[data-error]').textContent=result.errors.map(e=>e.name+': '+e.message).join(' ');p('[data-confirm]').hidden=true;}else d.close();
  }catch(e){p('[data-error]').hidden=false;p('[data-error]').textContent=e.message;}finally{busy=false;p('[data-cancel]').disabled=p('[data-back]').disabled=false;}};
 }
 function show(item){
  const d=document.createElement('dialog');d.className='gallery-player';d.ariaLabel='Anteprima file';
  d.innerHTML='<header><h2></h2><button type="button" class="icon-button" data-close aria-label="Chiudi anteprima">×</button></header><div data-preview></div><div class="video-edit-toolbar" data-actions></div><form data-rename><label class="field"><span>Nome nella galleria</span><input maxlength="150" required></label><button class="btn" type="submit">Rinomina</button></form><details><summary>Elimina asset</summary><p>Scegli nella conferma se conservare il file oppure cancellarlo anche dal disco.</p><button type="button" class="btn" data-delete>Elimina asset…</button></details><p role="alert" class="settings-error" hidden></p><footer class="video-edit-toolbar"><button type="button" class="btn" data-prev>← Precedente</button><button type="button" class="btn" data-next>Successivo →</button><a class="btn" data-download>Scarica</a></footer>';
  document.body.append(d);const p=s=>d.querySelector(s),error=e=>{p('[role="alert"]').hidden=false;p('[role="alert"]').textContent=e.message;};
  p('[data-rename]').hidden=!canManage;p('details').hidden=!canManage;
  p('h2').textContent=item.name;p('input').value=item.name;p('[data-close]').onclick=()=>d.close();
  const details=document.createElement('div');details.className='gallery-file-details';appendGalleryDetails(details,item);p('header').after(details);
  d.onclose=()=>{for(const media of d.querySelectorAll('video,audio')){media.pause();media.removeAttribute('src');media.load();}d.remove();};
  const type=item.mime.split('/')[0],tag=item.timeline_only?null:['image','video','audio'].includes(type)?({image:'img',video:'video',audio:'audio'})[type]:item.mime==='application/pdf'?'iframe':null;
  if(tag){const view=document.createElement(tag);view.src=item.url;if(tag==='img')view.alt=item.name;else if(['video','audio'].includes(tag)){view.controls=true;view.preload='metadata';view.playsInline=true;}else view.title=item.name;p('[data-preview]').append(view);}
  else p('[data-preview]').textContent=item.timeline_only?'La timeline e le clip completate sono salvate. Aprila per vedere le versioni e continuare a modificarle. Il filmato completo non è ancora stato esportato.':'Anteprima non disponibile per questo formato. Puoi scaricarlo o usarlo in chat.';
  appendCreationDetails(p('[data-actions]'),item,{api,load:true,onReuseImage:actions.reuseImage?async recipe=>{await actions.reuseImage(recipe);d.close();dialog.close();}:undefined});
  if(tag==='video'&&canManage)addBrowserPreview(p('[data-actions]'),p('video'),item,api);
  p('[data-download]').href=item.url;p('[data-download]').download=item.name;
  p('[data-download]').hidden=!!item.timeline_only;if(item.timeline_only)p('[data-download]').removeAttribute('href');
  const action=(label,callback)=>{const b=document.createElement('button');b.className='btn';b.type='button';b.textContent=label;b.onclick=async()=>{b.disabled=true;try{const media=(await api('/gallery/select',{ids:[item.id]}))[0];await callback(media,item);d.close();dialog.close();}catch(e){error(e);b.disabled=false;}};p('[data-actions]').append(b);};
  if(item.timeline_only){
   const open=document.createElement('button');open.type='button';open.className='btn primary';open.textContent='Apri timeline salvata';
   open.onclick=async()=>{open.disabled=true;try{const media={id:item.timeline_id||item.id,mime:'video/mp4',timeline_only:true};if(actions.edit)await actions.edit(media,item);else{const {openVideoEdit}=await import('./video-edit.js');await openVideoEdit({api,chatId:item.chat_id,source:media.id});}d.close();dialog.close();}catch(e){error(e);open.disabled=false;}};
   p('[data-actions]').append(open);
  }else{
   if(onSelect)action(browse?'Usa in chat':'Usa questo file',media=>onSelect([media]));
   if(type==='video')for(const [key,label] of [['edit','Modifica / estendi video'],['recreate','Ricrea video'],['remix','Remix audio'],['upscale','Upscale']])if(actions[key])action(label,actions[key]);
  }
  p('[data-rename]').onsubmit=async e=>{e.preventDefault();try{await api('/gallery/'+item.id,{name:p('input').value},'PATCH');item.name=p('input').value;p('h2').textContent=item.name;await load();const refreshed=items.find(i=>i.id===item.id);if(refreshed)Object.assign(item,refreshed);details.replaceChildren();appendGalleryDetails(details,item);}catch(e){error(e);}};
  p('[data-delete]').onclick=()=>confirmDelete([item],removed=>{if(removed.includes(item.id))d.close();});
  for(const [key,delta] of [['prev',-1],['next',1]]){const b=p('[data-'+key+']'),next=items.indexOf(item)+delta;b.disabled=next<0||next>=items.length;b.onclick=()=>{d.close();show(items[next]);};}
  d.showModal();
 }
 q('[data-query]').oninput=()=>{clearTimeout(timer);timer=setTimeout(()=>load(),250);};q('[data-kind]').onchange=q('[data-origin]').onchange=()=>load();q('[data-more]').onclick=()=>load(true);
 if(browse){const input=document.createElement('input');input.type='file';input.multiple=true;input.hidden=true;const upload=document.createElement('button');upload.type='button';upload.className='btn';upload.textContent='Carica dal PC';q('footer').prepend(upload,input);upload.onclick=()=>input.click();input.onchange=async()=>{upload.disabled=true;try{for(const file of input.files){status('Caricamento: '+file.name);await uploadFile(file,{api});}q('[data-origin]').value='all';await load();}catch(e){status(e.message);}finally{input.value='';upload.disabled=false;}};}
 q('[data-select]').onclick=async()=>{q('[data-select]').disabled=true;try{const items=await api('/gallery/select',{ids:[...selected.keys()]});await onSelect(items);dialog.close();}catch(e){status(e.message);selection();}};
 dialog.showModal();load();return dialog;
}

export function initGallery({api,getAttachments,setAttachments,notify,actions={}}){
 document.addEventListener('h3-export',async event=>{try{const {blob,name}=event.detail;await uploadFile(blob,{api,name,origin:'generated'});}catch(e){notify(e.message,true);}});
 const button=document.createElement('button');button.type='button';button.id='gallery-open';button.className='btn small';button.textContent='▧ Galleria';button.title='Riutilizza file caricati e generati in ogni modalità';document.querySelector('#attach').after(button);
 const attach=items=>{const existing=getAttachments(),ids=new Set(existing.map(m=>m.id)),next=[...existing,...items.filter(m=>!ids.has(m.id))];if(next.length>12)throw Error('Seleziona al massimo 12 allegati.');setAttachments(next);notify('File aggiunti al prompt.');};
 button.onclick=()=>openGallery({api,onSelect:attach,actions});
 const navigation=document.createElement('button');navigation.type='button';navigation.id='gallery-nav';navigation.className='settings-button';navigation.innerHTML='▧ <span>Galleria</span>';navigation.title='Tutti i tuoi file caricati e generati';document.querySelector('#settings-open').before(navigation);
 navigation.onclick=()=>{document.querySelector('#sidebar').classList.remove('visible');openGallery({api,onSelect:attach,browse:true,actions});};
}

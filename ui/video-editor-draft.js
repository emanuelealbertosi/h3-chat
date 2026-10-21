export const draftSignature=clips=>clips.map(c=>[Math.round(c.start*24),Math.round((c.end-c.start)*24)]);

export function remapEditorDraft(state,images){
 const mapping=new Map(state.image_ids.map((id,i)=>[i+1,images.find(x=>x.id===id)?.index]));
 const image=index=>index==null?null:mapping.get(index);
 if([...mapping.values()].some(x=>!x))throw Error('Un’immagine della bozza non è più disponibile.');
 const prompt=text=>text.replace(/<Picture\s+(\d+)>/gi,(tag,n)=>mapping.has(Number(n))?'<Picture '+mapping.get(Number(n))+'>':tag);
 return {...state,common_prompt:prompt(state.common_prompt),clips:state.clips.map(c=>({...c,prompt:prompt(c.prompt),images:c.images.map(image),start_image:image(c.start_image),anchor_image:image(c.anchor_image),anchor_images:Object.fromEntries(Object.entries(c.anchor_images).map(([key,n])=>[key,image(n)]))}))};
}

export function videoEditorDraft(host,{dialog,data,api,chatId,source,capture,reopen,beforeLaunch,restored=false}){
 const bar=document.createElement('section');bar.className='video-draft-toolbar';
 bar.innerHTML='<div><button type="button" class="btn small" data-save-editor-draft>Salva bozza</button><button type="button" class="btn small" data-restore-editor-draft title="Annulla le modifiche successive all’ultimo salvataggio">Ripristina bozza salvata</button><button type="button" class="text-button" data-clear-editor-draft>Riparti dal video</button></div><p class="small-note" role="status" data-editor-draft-status></p>';
 const anchor=host.nextElementSibling?.classList.contains('video-timeline-versions')?host.nextElementSibling:host;
 anchor.after(bar);const q=s=>bar.querySelector(s),form=dialog.querySelector('form');
 let saved=data.editor_draft||null,pending=false,disposed=false,notice='';
 const encoded=()=>{try{return JSON.stringify(capture());}catch{return null;}};
 let baseline=restored||!saved?encoded():null;
 const status=()=>{
  if(disposed)return;
  q('[data-save-editor-draft]').disabled=pending||!data.draft_supported;
  q('[data-restore-editor-draft]').disabled=pending||!saved;
  q('[data-restore-editor-draft]').title=pending?'Operazione sulla bozza in corso.':saved?'Annulla le modifiche successive all’ultimo salvataggio.':'Nessuna bozza salvata per questa suddivisione. Premi Salva bozza per conservare le impostazioni attuali.';
  q('[data-clear-editor-draft]').disabled=pending||!data.draft_supported;
  bar.setAttribute('aria-busy',String(pending));
  const current=encoded(),dirty=current===null||current!==baseline;
  q('[data-editor-draft-status]').textContent=notice||(!data.draft_supported?'Il salvataggio delle bozze si attiverà dopo l’aggiornamento del motore.':dirty?'Modifiche non salvate. Premi Salva bozza prima di chiudere.':saved?'Bozza salvata · '+new Date(saved.saved_at*1000).toLocaleString('it-IT'):'Nessuna bozza salvata. Il salvataggio conserva tutte le modifiche senza avviare generazioni.');
 };
 async function persist(){
  const state=capture();saved=await api('/chats/'+chatId+'/video-editor-draft/'+source,{state,segment_seconds:data.segment_seconds||null});
  baseline=JSON.stringify(state);notice='';
 }
 q('[data-save-editor-draft]').onclick=async()=>{
  pending=true;notice='Salvataggio bozza…';status();
  try{
   await persist();
  }catch(e){notice='Bozza non salvata: '+e.message;}
  finally{pending=false;status();}
 };
 q('[data-restore-editor-draft]').onclick=async()=>{
  if(!saved)return;pending=true;notice='Ripristino bozza…';status();
  try{await reopen(saved);}catch(e){notice=e.message;}finally{pending=false;status();}
 };
 q('[data-clear-editor-draft]').onclick=async()=>{
  pending=true;notice='Ripristino del video…';status();
  try{await api('/chats/'+chatId+'/video-editor-draft/'+source,{segment_seconds:data.segment_seconds||null},'DELETE');saved=null;await reopen(null);}catch(e){notice=e.message;}finally{pending=false;status();}
 };
 const changed=e=>{if(e.target.closest('.video-draft-toolbar,.video-timeline-preview')||e.target.type==='submit')return;notice='';queueMicrotask(status);};
 form.addEventListener('input',changed);form.addEventListener('change',changed);form.addEventListener('click',changed);status();
 return {async saveForLaunch(){
  if(!data.draft_supported)return false;
  pending=true;notice='Salvataggio impostazioni di lancio…';status();
  try{beforeLaunch?.();await persist();return true;}catch(e){throw Error('Impostazioni non salvate: '+e.message);}finally{pending=false;status();}
 },close(){disposed=true;form.removeEventListener('input',changed);form.removeEventListener('change',changed);form.removeEventListener('click',changed);}};
}

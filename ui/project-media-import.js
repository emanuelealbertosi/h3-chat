import {uploadFile} from './file-upload.js';
export function initProjectMediaImport({api,getProjectId,getChat,getAttachments=()=>[],notify,onChange}){
 const host=document.querySelector('#project-documents'),button=document.createElement('button');button.type='button';button.className='btn';button.textContent='Importa link, audio o video…';host.querySelector('.project-import-actions').append(button);
 button.onclick=()=>{
  const dialog=document.createElement('dialog');dialog.className='study-modal';dialog.style.cssText='width:min(620px,90vw);padding:24px;border:1px solid #ddd;border-radius:14px';
  const title=document.createElement('h2');title.textContent='Aggiungi una fonte al RAG';const close=document.createElement('button');close.type='button';close.textContent='Chiudi';close.className='btn';close.onclick=()=>dialog.close();
  const form=document.createElement('div');form.style.cssText='display:grid;gap:14px;margin-top:18px';
  const kind=document.createElement('select');kind.ariaLabel='Tipo fonte';for(const [v,label] of [['web','Pagina web'],['youtube','YouTube · sottotitoli'],['audio','File audio o video · trascrizione']])kind.append(new Option(label,v));
  const name=document.createElement('input');name.placeholder='Nome della fonte';name.maxLength=150;name.ariaLabel='Nome fonte';const url=document.createElement('input');url.placeholder='https://…';url.maxLength=4096;url.ariaLabel='URL fonte';
  const file=document.createElement('input');file.type='file';file.accept='audio/*,video/*';file.ariaLabel='File audio o video';const note=document.createElement('p');note.textContent='Il testo indicizzato sarà disponibile a tutti gli strumenti del progetto. Per i video si indicizza il parlato, non l’analisi dei fotogrammi. Whisper legge fino a 30 minuti per file. YouTube usa i sottotitoli IT/EN disponibili.';
  const status=document.createElement('p');status.role='status';const start=document.createElement('button');start.type='button';start.className='btn primary';start.textContent='Importa e indicizza';
  kind.onchange=()=>{url.hidden=kind.value==='audio';file.hidden=kind.value!=='audio';};kind.onchange();
  start.onclick=async()=>{start.disabled=true;try{const project=getProjectId();if(!project)throw Error('Salva prima il progetto.');let item;
   if(kind.value==='audio'){if(!file.files[0])throw Error('Seleziona un file audio o video.');item=await uploadFile(file.files[0],{api,onProgress:(n,total)=>status.textContent='Caricamento '+Math.round(n/total*100)+'%'});}
   const result=await api('/projects/'+project+'/media-import',{kind:kind.value,name:name.value||file.files[0]?.name||'Fonte web',url:url.value,asset_id:item?.id,chat_id:getChat()?.project_id===project?getChat().id:undefined});
   notify('Fonte in coda: verrà trascritta/letta e indicizzata per tutti gli strumenti del progetto.');await onChange?.(project,result);dialog.close();
  }catch(e){status.textContent=e.message;start.disabled=false;}};
  form.append(note,kind,name,url,file,status,start);dialog.append(title,close,form);dialog.addEventListener('close',()=>dialog.remove());document.body.append(dialog);dialog.showModal();
 };
 return {render:locked=>button.disabled=!!locked};
}

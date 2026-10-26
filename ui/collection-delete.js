let deleting=false;
export async function deleteCollections(api,ids){
 if(deleting)return null;
 deleting=true;
 try{
 const plan=await api('/image-collections/delete-plan',{ids});
 return await new Promise(resolve=>{
  const dialog=document.createElement('dialog');dialog.className='prompt-options-dialog collection-delete-dialog';dialog.ariaLabel='Conferma eliminazione lotti';
  const form=document.createElement('form'),title=document.createElement('h2'),summary=document.createElement('p'),list=document.createElement('ul'),label=document.createElement('label'),disk=document.createElement('input'),warning=document.createElement('p'),status=document.createElement('p'),footer=document.createElement('footer'),cancel=document.createElement('button'),remove=document.createElement('button');
  title.textContent='Elimina '+plan.count+' '+(plan.count===1?'lotto':'lotti');summary.textContent=plan.file_count+' immagini distinte · '+(plan.bytes/1024**2).toFixed(1)+' MB. Senza la casella seguente rimuovi solo i lotti: i file restano sul disco.';
  for(const item of plan.lots){const li=document.createElement('li');li.textContent=item.name+' · '+item.images+' immagini';list.append(li);}
  disk.type='checkbox';disk.name='delete_files';disk.disabled=!plan.can_delete_files;label.append(disk,' Elimina anche i file dal disco — operazione non annullabile');
  const refs=[...new Set(plan.files.flatMap(f=>f.references))];warning.className='message-error';warning.textContent=plan.referenced_files?`${plan.referenced_files} immagini sono usate anche altrove. Eliminandole dal disco non saranno più disponibili in: ${refs.slice(0,8).join('; ')}${refs.length>8?'…':''}.`:'';
  if(plan.reason){const note=document.createElement('p');note.className='small-note';note.textContent=plan.reason;label.append(note);}
  cancel.type='button';cancel.className='btn';cancel.textContent='Annulla';cancel.onclick=()=>dialog.close();remove.type='submit';remove.className='btn primary';remove.textContent='Rimuovi solo i lotti';remove.disabled=!plan.can_remove;
  disk.onchange=()=>remove.textContent=disk.checked?'Conferma eliminazione lotti e file':'Rimuovi solo i lotti';
  footer.append(cancel,remove);form.append(title,summary,list,label,warning,status,footer);dialog.append(form);document.body.append(dialog);let result=null;
  dialog.addEventListener('close',()=>{dialog.remove();resolve(result);},{once:true});
  dialog.addEventListener('cancel',event=>{if(cancel.disabled)event.preventDefault();});
  form.onsubmit=async event=>{event.preventDefault();remove.disabled=true;cancel.disabled=true;status.textContent='Rimozione in corso…';try{result=await api('/image-collections/delete',{ids,delete_files:disk.checked,confirmed:true,snapshot:plan.snapshot});dialog.close();}catch(error){status.textContent=error.message;}finally{remove.disabled=!plan.can_remove;cancel.disabled=false;}};
  dialog.showModal();
 });
 }finally{deleting=false;}
}

export function collectionDeleteButton(target,api,id,onRemoved){
 let removed=false;
 const button=document.createElement('button');button.type='button';button.className='text-button no-export';button.textContent='Elimina lotto';
 button.onclick=async()=>{button.disabled=true;try{const result=await deleteCollections(api,[id]);if(result){removed=result.removed.includes(id);await onRemoved?.(result);button.textContent=removed?'Lotto rimosso':'Eliminazione incompleta';}}catch(error){button.textContent=error.message;}finally{button.disabled=removed;}};
 target.append(button);
}

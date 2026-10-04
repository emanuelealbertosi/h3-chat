export const projectUploadLimits={file_bytes:512*1024**2,upload_chunk_bytes:2*1024**2};

export async function uploadProjectDocument(file,{project,relativePath=file.name,api,getToken,limits=projectUploadLimits,onProgress=()=>{},fetcher=fetch}){
 if(!Number.isSafeInteger(file.size)||file.size<=0||file.size>limits.file_bytes)throw Error(file.name+': il documento è vuoto o supera '+Math.round(limits.file_bytes/1024**2)+' MB.');
 const base='/projects/'+encodeURIComponent(project)+'/import';let upload;
 try{
  upload=await api(base+'/start',{name:file.name,relative_path:relativePath,size:file.size,defer:true});
  if(!/^[a-f0-9]{32}$/.test(upload.id)||!Number.isInteger(upload.chunk_bytes)||upload.chunk_bytes<=0||upload.chunk_bytes>limits.upload_chunk_bytes)throw Error('Risposta di caricamento non valida.');
  for(let offset=0;offset<file.size;){
   const end=Math.min(file.size,offset+upload.chunk_bytes);
   const response=await fetcher('/api'+base+'/'+upload.id,{method:'PATCH',cache:'no-store',credentials:'same-origin',headers:{'Content-Type':'application/octet-stream','X-H3-Token':getToken(),'X-H3-Offset':String(offset)},body:file.slice(offset,end)});
   const value=await response.json();if(!response.ok)throw Error(value.error||'Caricamento del documento non riuscito.');
   if(value.received!==end)throw Error('Il server non ha ricevuto tutto il blocco del documento.');
   offset=end;onProgress(offset,file.size);
  }
  return await api(base+'/'+upload.id+'/finish',{});
 }catch(error){
  if(upload?.id&&/^[a-f0-9]{32}$/.test(upload.id))try{await api(base+'/'+upload.id,{},'DELETE');}catch{}
  throw error;
 }
}

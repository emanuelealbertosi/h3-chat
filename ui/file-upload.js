// Whole files never become base64 strings: only one bounded block is read at a time.
export async function uploadFile(file,{api,name=file.name||'File',origin='uploaded',onProgress=()=>{}}){
 if(!Number.isSafeInteger(file.size)||file.size<0)throw Error('Dimensione del file non valida.');
 let upload;
 try{
  upload=await api('/uploads/start',{name,size:file.size,origin});
  if(!/^[a-f0-9]{32}$/.test(upload.id)||!Number.isInteger(upload.chunk_bytes)||upload.chunk_bytes<=0||upload.chunk_bytes>2*1024**2)throw Error('Risposta di caricamento non valida.');
  for(let offset=0;offset<file.size;){
   const end=Math.min(file.size,offset+upload.chunk_bytes),data=await new Promise((resolve,reject)=>{
    const reader=new FileReader();reader.onload=()=>resolve(String(reader.result).split(',')[1]);reader.onerror=()=>reject(Error('Lettura del file non riuscita.'));reader.readAsDataURL(file.slice(offset,end));
   });
   const result=await api('/uploads/'+upload.id+'/chunk',{offset,data});
   if(result.received!==end)throw Error('Il server non ha ricevuto tutto il blocco.');
   offset=end;onProgress(offset,file.size);
  }
  return await api('/uploads/'+upload.id+'/finish',{});
 }catch(error){
  if(upload?.id&&/^[a-f0-9]{32}$/.test(upload.id))try{await api('/uploads/'+upload.id,{},'DELETE');}catch{}
  throw error;
 }
}

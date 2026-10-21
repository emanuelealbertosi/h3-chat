// Older servers still return the complete reference archive. Resolve the saved
// edit recipe through existing read-only routes, leaving replay media intact.
const resolved=new Map();
export async function resolveVideoEditInputs(chat,jobs,api,readJson=async url=>{
 const response=await fetch(url);if(!response.ok)throw Error('Ricetta non disponibile');return response.json();
}){
 for(let i=0;i<chat.messages.length;i++){
  const message=chat.messages[i],answer=chat.messages[i+1];
  if(message.role!=='user'||message.display_media!==undefined||!message.content?.startsWith('Post-produzione video ·')||answer?.role!=='assistant')continue;
  const job=jobs.find(j=>j.message_id===answer.id)?.id||answer.media?.map(m=>m.path?.match(/^outputs\/([a-f0-9]{32})\//)?.[1]).find(Boolean);
  if(!/^[a-f0-9]{32}$/.test(job||''))continue;
  const key=chat.id+':'+message.id+':'+job;
  if(resolved.has(key)){message.display_media=resolved.get(key);continue;}
  try{
   const recipe=await readJson('/media/outputs/'+job+'/scenes.json');
   if(!Array.isArray(recipe.revision_request)||!/^[a-f0-9]{32}$/.test(recipe.revision_source||''))continue;
   const selected=new Set(recipe.revision_request.flatMap(p=>p.images||[])),images=message.media.filter(m=>m.mime?.startsWith('image/'));
   const visible=images.filter((_,index)=>selected.has(index+1));
   visible.push(...message.media.filter(m=>!m.mime?.startsWith('image/')&&!m.mime?.startsWith('video/')));
   const patch=recipe.revision_request.find(p=>p.mode==='video');
   if(patch){
    try{
     const source=await api('/chats/'+chat.id+'/video-edit/'+recipe.revision_source),clip=source.clips.find(c=>c.clip===patch.clip);
     if(clip?.url?.startsWith('/media/'))visible.unshift({id:recipe.revision_source,name:'Video sorgente · clip '+patch.clip,mime:'video/mp4',path:clip.url.slice(7)});
    }catch{/* Selected images and soundtrack remain valid if the source vanished. */}
   }
   resolved.set(key,visible);message.display_media=visible;
  }catch{/* Queued edits may not have a checkpoint yet. Retry on a later refresh. */}
 }
}

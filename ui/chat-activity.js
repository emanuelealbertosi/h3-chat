export function chatActivities(jobs=[]){
 const result=new Map();
 for(const job of jobs){
  if(!['queued','running'].includes(job.status))continue;
  if(job.status==='running'||!result.has(job.chat_id))result.set(job.chat_id,job.status);
 }
 return result;
}
export function chatActivityIcon(status){
 if(status==='running')return '<span class="chat-activity running" role="img" aria-label="Generazione in corso" title="Generazione in corso"></span>';
 if(status==='queued')return '<span class="chat-activity queued" role="img" aria-label="Richiesta in coda" title="Richiesta in coda">◷</span>';
 return '';
}

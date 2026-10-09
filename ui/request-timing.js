const valid=value=>typeof value==='number'&&Number.isFinite(value)&&value>=0;
export function formatDuration(value){
 const seconds=Math.max(0,Math.floor(value));
 if(seconds<60)return seconds+' s';
 if(seconds<3600)return Math.floor(seconds/60)+' min '+seconds%60+' s';
 return Math.floor(seconds/3600)+' h '+Math.floor(seconds%3600/60)+' min '+seconds%60+' s';
}
export function requestTiming(message,job,now=Date.now()/1000){
 if(message.role!=='assistant')return null;
 const timing=message.meta?.timing||{},pending=['queued','running'].includes(message.status);
 if(pending){
  const started=valid(timing.started_at),queued=valid(timing.queued_at)?timing.queued_at:job?.created;
  if(!started&&!valid(queued))return null;
  const elapsed=Math.max(0,now-(started?timing.started_at:queued));
  const waiting=started&&valid(queued)?Math.max(0,timing.started_at-queued):0;
  return {text:(started?'Tempo trascorso: ':'In coda da: ')+formatDuration(elapsed)+(waiting>=1?' · Attesa in coda: '+formatDuration(waiting):''),title:'Include caricamento dei modelli, pianificazione, generazione e salvataggio. L’attesa in coda è separata.'};
 }
 if(!valid(timing.finished_at)||!valid(timing.elapsed_seconds))return {text:'Durata non registrata',title:'Per questa risposta non è disponibile un tempo completo e affidabile.'};
 const neverStarted=!valid(timing.started_at),waiting=valid(timing.queue_seconds)?timing.queue_seconds:0;
 const duration=timing.elapsed_seconds>0&&timing.elapsed_seconds<1?'<1 s':formatDuration(timing.elapsed_seconds);
 return {text:neverStarted?'Attesa in coda: '+formatDuration(waiting):(message.status==='done'?'Durata: ':'Tempo impiegato: ')+duration+(waiting>=1?' · Attesa in coda: '+formatDuration(waiting):''),
  title:'Tempo totale dalla richiesta: '+formatDuration(valid(timing.total_seconds)?timing.total_seconds:timing.elapsed_seconds+waiting)+'. Include caricamento dei modelli, pianificazione, generazione e salvataggio.'};
}

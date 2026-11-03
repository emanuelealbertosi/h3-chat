const active=new Set(['queued','running','cancelling']);
const labels={queued:'In coda',running:'In corso',cancelling:'Interruzione in corso',done:'Completato',failed:'Da controllare',cancelled:'Interrotto',interrupted:'Interrotto'};
const el=(tag,text,cls)=>{const e=document.createElement(tag);if(text!=null)e.textContent=text;if(cls)e.className=cls;return e;};
const size=n=>{const bytes=Math.max(0,Number(n)||0),unit=Math.min(3,Math.floor(Math.log10(Math.max(1,bytes))/3));return (bytes/1000**unit).toLocaleString('it-IT',{maximumFractionDigits:1})+' '+['B','kB','MB','GB'][unit];};
export function workItems(state){
 const chats=new Map((state?.chats||[]).map(c=>[c.id,c]));
 const jobs=(state?.jobs||[]).map(j=>({...j,key:'job:'+j.id,kind:'job',title:chats.get(j.chat_id)?.title||'Richiesta salvata'}));
 const downloads=(state?.downloads||[]).map(d=>({...d,key:'download:'+d.id,kind:'download',title:'Download · '+(d.file?.split(/[\\/]/).pop()||d.id)}));
 return [...jobs,...downloads].sort((a,b)=>Number(active.has(b.status))-Number(active.has(a.status))||(b.created||0)-(a.created||0));
}
export function recoveryAdvice(error=''){
 if(/memoria|memory|vram|out of memory/i.test(error))return 'Controlla la memoria e i parametri del modello prima di rilanciare.';
 if(/timeout|timed out|tempo.*(massimo|scaduto)/i.test(error))return 'Controlla il tempo massimo del modello nelle impostazioni e verifica i risultati già disponibili.';
 if(/json|formato.*(risposta|richiesto)/i.test(error))return 'Controlla modello e formato della risposta nelle impostazioni API.';
 if(/connessione|connection|fetch|network/i.test(error))return 'Verifica il collegamento al servizio e controlla Lavori prima di inviare di nuovo.';
 return 'Puoi controllare i risultati disponibili oppure recuperare la richiesta come bozza.';
}
export function appendRecovery(host,{message,onReload,onResults,onSettings}){
 if(!['failed','interrupted','cancelled'].includes(message.status))return;
 const box=el('section',null,'request-recovery'),stopped=message.status!=='failed';
 box.append(el('strong',stopped?'Lavoro interrotto':'Richiesta da controllare'),el('p',stopped?'Controlla gli elementi già creati. Ricarica richiesta ripristina una bozza da verificare prima di inviare.':recoveryAdvice(message.meta?.error)));
 const actions=el('div',null,'work-actions');
 for(const [label,fn] of [['Ricarica richiesta',onReload],['Risultati salvati',onResults],['Apri impostazioni',onSettings]])if(fn){const b=el('button',label,'btn small');b.type='button';b.onclick=fn;actions.append(b);}
 box.append(actions);host.append(box);
}
export function initWorkCenter({getState,onOpen,onReload,onResults,onCancel,onSettings,notify}){
 const button=el('button','Lavori','btn');button.id='work-center-open';button.type='button';button.setAttribute('aria-haspopup','dialog');document.querySelector('.top-actions').prepend(button);
 const dialog=el('dialog',null,'work-center-dialog');dialog.id='work-center';dialog.ariaLabel='Lavori e download';
 const header=el('header'),title=el('h2','Lavori e download'),close=el('button','×','icon-button');close.type='button';close.ariaLabel='Chiudi lavori';close.onclick=()=>dialog.close();header.append(title,close);
 const body=el('div',null,'work-center-body'),summary=el('p'),filters=el('div',null,'work-filters'),list=el('div',null,'work-list'),error=el('p',null,'settings-error');error.hidden=true;error.setAttribute('role','alert');
 body.append(summary,el('p','Ultime richieste e download del tuo account. Apri una chat per vedere dettagli, risultati e comandi di completamento.','small-note'),filters,error,list);dialog.append(header,body);document.body.append(dialog);
 let filter='active',identity=null,reviewed=new Set();const cards=new Map();
 const saveReviewed=()=>{if(identity)try{localStorage.setItem('h3.work-reviewed.'+identity,JSON.stringify([...reviewed].slice(-300)));}catch{}};
 const run=fn=>async()=>{error.hidden=true;try{await fn();}catch(e){error.textContent=e.message;error.hidden=false;notify?.(e.message,true);}};
 for(const [key,label] of [['active','In corso'],['attention','Da controllare'],['all','Tutti']]){const b=el('button',label,'btn small');b.type='button';b.dataset.filter=key;b.onclick=()=>{filter=key;render();};filters.append(b);}
 function card(item){
  const row=el('article',null,'work-card'),heading=el('h3'),badge=el('span',null,'badge'),stage=el('p'),time=el('small'),bar=el('progress'),detail=el('details'),detailTitle=el('summary','Dettagli'),detailText=el('p'),actions=el('div',null,'work-actions');
  detail.append(detailTitle,detailText);row.append(heading,badge,stage,bar,time,detail,actions);bar.ariaLabel='Avanzamento download';
  const controls={};
  const add=(key,label,fn)=>{const b=el('button',label,'btn small');b.type='button';b.onclick=run(()=>fn(row.item));actions.append(b);controls[key]=b;};
  if(item.kind==='job'){
   add('open','Apri chat',async v=>{dialog.close();await onOpen(v);});
   add('results','Risultati salvati',async v=>{dialog.close();await onResults(v);});
   add('reload','Ricarica richiesta',async v=>{dialog.close();await onReload(v);});
  }else add('setup','Apri installazione',async()=>{dialog.close();await onSettings();});
  add('reviewed','Ho controllato',async v=>{reviewed.add(v.key);saveReviewed();render();});
  add('cancel','Interrompi',onCancel);
  return {row,heading,badge,stage,time,bar,detail,detailText,controls};
 }
 function render(){
  const state=getState();if(!state)return;
  const account=state.access?.id||null;if(account!==identity){identity=account;try{reviewed=new Set(identity?JSON.parse(localStorage.getItem('h3.work-reviewed.'+identity)||'[]'):[]);}catch{reviewed=new Set();}}
  const items=workItems(state),busy=items.filter(i=>active.has(i.status));let changed=false;for(const item of busy)changed=reviewed.delete(item.key)||changed;if(changed)saveReviewed();
  const failed=items.filter(i=>i.status==='failed'&&!reviewed.has(i.key));
  button.textContent=busy.length?'Lavori · '+busy.length:failed.length?'Lavori · '+failed.length+' da controllare':'Lavori';
  if(!dialog.open)return;
  summary.textContent=busy.length+' in corso / in coda · '+failed.length+' da controllare';
  for(const b of filters.children)b.setAttribute('aria-pressed',String(b.dataset.filter===filter));
  const shown=items.filter(i=>filter==='all'||filter==='active'&&active.has(i.status)||filter==='attention'&&i.status==='failed'&&!reviewed.has(i.key));
  const keys=new Set(shown.map(i=>i.key));for(const [key,c] of cards)if(!keys.has(key)){c.row.remove();cards.delete(key);}
  list.querySelector('.work-empty')?.remove();
  if(!shown.length)list.append(el('p',filter==='active'?'Nessun lavoro in corso.':filter==='attention'?'Nessun errore tra i lavori disponibili.':'Nessun lavoro disponibile.','work-empty'));
  for(const [index,item] of shown.entries()){
   let c=cards.get(item.key);if(!c){c=card(item);cards.set(item.key,c);}c.row.item=item;
   if(list.children[index]!==c.row)list.insertBefore(c.row,list.children[index]||null);
   c.heading.textContent=item.title;c.badge.textContent=item.status==='failed'&&reviewed.has(item.key)?'Errore consultato':labels[item.status]||item.status;
   c.stage.textContent=item.stage||(item.kind==='download'?(item.file?.split(/[\\/]/).pop()||'Preparazione download'):item.status==='queued'?'Attende il motore disponibile':'');
   c.bar.hidden=item.kind!=='download'||!active.has(item.status);if(item.total>0){c.bar.max=item.total;c.bar.value=Math.min(item.total,item.received||0);}else c.bar.removeAttribute('value');
   const elapsed=Math.max(0,Math.floor((state.server_time??Date.now()/1000)-(item.created||0)));
   c.time.textContent=item.kind==='download'?size(item.received)+(item.total>0?' / '+size(item.total):' ricevuti'):item.created?active.has(item.status)?'Da invio '+Math.floor(elapsed/60)+' min '+elapsed%60+' s · include la coda':'Inviato '+new Date(item.created*1000).toLocaleString('it-IT',{dateStyle:'short',timeStyle:'short'}):'';
   c.detail.hidden=!item.error;c.detailText.textContent=item.error||'';
   c.controls.cancel.hidden=!active.has(item.status);c.controls.cancel.disabled=item.status==='cancelling';
   c.controls.reviewed.hidden=item.status!=='failed'||reviewed.has(item.key);
   if(c.controls.reload)c.controls.reload.hidden=active.has(item.status);
   if(c.controls.results)c.controls.results.hidden=!item.canvas;
  }
 }
 button.onclick=()=>{filter=workItems(getState()).some(i=>active.has(i.status))?'active':'all';dialog.showModal();render();};
 return {render,open(){button.click();}};
}

const active=status=>['queued','running','cancelling'].includes(status);

export function canvasFingerprint(value,jobs=[],chatId=null){
 return JSON.stringify([value.id,value.title,value.content,value.media,jobs.filter(j=>active(j.status)).map(j=>[j.id,j.status,j.chat_id===chatId?j.stage:null])]);
}

export function revisionDraft(selected,index=selected.index){
 selected.aiPages||={};return selected.aiPages[index]||={prompt:'',open:false,submitting:false};
}

export async function savedCanvasArtifact(expectedId,read,persist,wait=async()=>{}){
 const before=read();
 if(before.artifactId!==expectedId)throw Error('La presentazione è cambiata: scegli di nuovo la slide.');
 await wait();
 const ready=read();
 if(ready.chatId!==before.chatId||ready.selection!==before.selection)throw Error('La selezione è cambiata: riapri la presentazione.');
 await persist();
 const after=read();
 if(after.chatId!==before.chatId||after.selection!==before.selection)throw Error('La selezione è cambiata: riapri la presentazione.');
 return after.artifactId;
}

export function slideProgress(deck,index,job){
 const missing=deck.pages.filter(p=>p.status!=='ready').length,page=deck.pages[index];
 const characters=typeof page.html==='string'?page.html.length:(page.nodes||[]).reduce((sum,node)=>sum+(node.text||'').length,0);
 if(job)return {missing,text:(job.stage||'Slide · generazione in corso')+' · pagina '+(index+1)+' · '+characters.toLocaleString('it-IT')+' caratteri in anteprima'};
 return {missing,text:missing?'Generazione interrotta · '+(deck.pages.length-missing)+'/'+deck.pages.length+' slide complete. Le pagine già pronte restano salvate.':''};
}

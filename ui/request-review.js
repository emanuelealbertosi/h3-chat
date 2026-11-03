const node=(tag,text)=>{const e=document.createElement(tag);e.textContent=text??'';return e;};
export function reviewRows({mode='Automatico',models=[],destination='Chat',media=[],rag=false,project='',rag_sources,rag_top_k,parameters=[],loras=[],assistant=true,web=false}={}){
 const rows=[['Modalità',mode],['Modelli',models.filter(Boolean).join(' · ')||'Automatici · dal prompt'],['Destinazione',destination],['Allegati',media.length?media.map((m,i)=>(i+1)+'. '+m.name).join(' · '):'Nessuno']];
 rows.push(['Fonti RAG',!rag?'Disattivate':!project?'Nessun progetto selezionato':project+' · '+(Array.isArray(rag_sources)?rag_sources.length+' documenti selezionati':'tutti i documenti')+' · max '+(rag_top_k??6)+' estratti']);
 rows.push(['Assistant',assistant?'On':'Off'],['Web',web?'Attivo':'Disattivato']);
 for(const row of parameters)if(row[1]!=null&&row[1]!=='')rows.push(row);
 if(loras.length)rows.push(['LoRA',loras.map(l=>(l.name||l.id)+' × '+l.weight).join(' · ')]);
 return rows;
}
export function initRequestReview({getSnapshot}){
 const root=node('details');root.id='request-review';root.className='request-review';const summary=node('summary','Riepilogo richiesta'),body=node('div'),rows=node('dl'),note=node('p','Impostazioni della bozza. Le istruzioni esplicite nel prompt hanno la priorità; in Automatico il percorso e gli eventuali modelli vengono risolti dopo l’invio.');note.className='small-note';body.append(rows,note);root.append(summary,body);document.querySelector('.composer-bottom').before(root);
 let signature='';
 function render(){
  let value;try{value=getSnapshot();}catch{summary.textContent='Riepilogo · completa le impostazioni';rows.replaceChildren();signature='';return;}if(!value)return;
  summary.textContent='Riepilogo · '+value.mode+(value.media.length?' · '+value.media.length+' allegati':'')+(value.rag?' · RAG':'');
  const next=reviewRows(value),s=JSON.stringify(next);if(s===signature)return;signature=s;rows.replaceChildren();for(const [key,text] of next)rows.append(node('dt',key),node('dd',text));
 }
 document.addEventListener('input',render);document.addEventListener('change',render);document.addEventListener('click',()=>queueMicrotask(render));root.addEventListener('toggle',render);
 return {render};
}

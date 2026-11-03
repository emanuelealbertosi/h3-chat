// Less common request inputs stay visible and editable after reloading.
export function initRequestExtras({getChatId,getLab,getState,getImageModel,getRag}){
 const drafts=new Map(),panel=document.createElement('section');panel.className='request-reloaded-extras';panel.hidden=true;
 panel.innerHTML='<details data-source hidden open><summary>Codice della richiesta ricaricata</summary><textarea data-code rows="7" aria-label="Codice della richiesta ricaricata"></textarea></details><fieldset data-lot hidden><legend>Lotto immagini ricaricato</legend><label>Nome <input data-lot-name maxlength="150"></label> <label>Immagini <input data-lot-count type="number" min="1" max="50"></label> <label>Formato <select data-lot-format></select></label><p class="small-note">Modello e RAG seguono i controlli della richiesta. Gli altri parametri del modello sono ripristinati nelle impostazioni.</p></fieldset>';
 document.querySelector('#prompt').after(panel);
 const sequence=document.createElement('details');sequence.hidden=true;sequence.open=true;sequence.innerHTML='<summary>Sequenza vocale ricaricata</summary><p class="small-note">Parti in ordine, con testo e interpretazione. Modifica i valori JSON oppure svuota il campo per leggere il prompt normale.</p><textarea data-voice-parts rows="8" aria-label="Parti della sequenza vocale"></textarea>';panel.append(sequence);
 const q=s=>panel.querySelector(s),current=()=>drafts.get(getChatId())||{};
 for(const fmt of ['16:9','9:16','4:3','3:4','1:1','3:2','2:3'])q('[data-lot-format]').add(new Option(fmt,fmt));
 q('[data-code]').oninput=()=>current().source=q('[data-code]').value;
 for(const key of ['name','count','format'])q('[data-lot-'+key+']').oninput=()=>{if(current().lot)current().lot[key]=key==='count'?Number(q('[data-lot-count]').value):q('[data-lot-'+key+']').value;};
 q('[data-voice-parts]').oninput=()=>current().voiceParts=q('[data-voice-parts]').value;
 function render(){const d=current(),lab=getLab();q('[data-source]').hidden=!d.source||!['manim','calculate'].includes(lab);q('[data-lot]').hidden=!d.lot||lab!=='auto';sequence.hidden=d.voiceParts===undefined||lab!=='auto';panel.hidden=q('[data-source]').hidden&&q('[data-lot]').hidden&&sequence.hidden;if(document.activeElement!==q('[data-voice-parts]'))q('[data-voice-parts]').value=d.voiceParts||'';if(document.activeElement!==q('[data-code]'))q('[data-code]').value=d.source||'';if(d.lot)for(const key of ['name','count','format'])q('[data-lot-'+key+']').value=d.lot[key];}
 return {render,migrateNew(id){const value=drafts.get(getChatId());if(value)drafts.set(id,structuredClone(value));drafts.delete(getChatId());},set(value){drafts.set(getChatId(),{source:value.lab_source||'',voiceParts:value.voice_parts?.length?JSON.stringify(value.voice_parts,null,2):undefined,lot:value.image_lot?structuredClone(value.image_lot):null,agent_context:structuredClone(value.agent_context||{}),agent_start_artifact:value.agent_start_artifact});render();},read(){
  const d=current(),lab=getLab(),result={};
  if(d.voiceParts?.trim()&&lab==='auto'){try{result.voice_parts=JSON.parse(d.voiceParts);}catch{throw Error('La sequenza vocale deve essere JSON valido.');}}
  if(lab==='agent'){
   if(d.agent_context&&Object.keys(d.agent_context).length)result.agent_context=structuredClone(d.agent_context);
   if(d.agent_start_artifact)result.agent_start_artifact=d.agent_start_artifact;
  }
  if(d.source&&['manim','calculate'].includes(lab))result.lab_source=q('[data-code]').value;
  if(d.lot&&lab==='auto'){if(!q('[data-lot-count]').reportValidity())throw Error('Lotto immagini: scegli da 1 a 50 immagini.');result.image_lot={...d.lot,model:getImageModel()||d.lot.model,rag:getRag()};}
  return result;
 }};
}

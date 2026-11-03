import {escape as esc} from './render.js';

export function initGenerationPresets({api,getChatId,apply,notify}){
 const dialog=document.createElement('dialog');dialog.className='prompt-options-dialog';dialog.id='generation-presets';
 dialog.innerHTML='<header><h2>Preset di generazione</h2><button type="button" class="icon-button" data-close aria-label="Chiudi preset">×</button></header><div class="prompt-options-body"><section data-save hidden><label class="field"><span>Nome del preset</span><input maxlength="80" aria-label="Nome del preset di generazione"></label><button type="button" class="btn primary" data-confirm-save>Salva i parametri della richiesta</button></section><p class="small-note">Richiama modello, parametri e opzioni della modalità. Prompt, allegati, fonti selezionate e permessi dell’Agente restano quelli attuali. Il prompt mantiene la priorità. Un nome già presente nella stessa modalità aggiorna il preset.</p><label class="field"><span>Modalità</span><select data-kind aria-label="Filtra preset per modalità"><option value="">Tutte</option></select></label><label class="field"><span>Preset salvati</span><select data-presets aria-label="Preset di generazione"></select></label><p data-description></p><p class="message-error" data-error hidden></p></div><footer><button type="button" class="text-button" data-delete>Elimina preset</button><button type="button" class="btn primary" data-apply>Usa preset</button></footer>';
 document.body.append(dialog);const q=s=>dialog.querySelector(s);let library=[],source=null,busy=false;
 const selected=()=>library.find(p=>p.id===q('[data-presets]').value);
 function draw(){
  const previous=q('[data-presets]').value,kind=q('[data-kind]').value;
  q('[data-presets]').innerHTML='<option value="">Scegli un preset</option>'+library.filter(p=>!kind||p.kind===kind).map(p=>`<option value="${esc(p.id)}">${esc(p.label+' · '+p.name)}</option>`).join('');q('[data-presets]').value=previous;
  describe();
 }
 function describe(){const p=selected();q('[data-description]').textContent=p?'Carica «'+p.name+'» nelle impostazioni della prossima richiesta. Non avvia generazioni.':library.length?'Seleziona un preset.':'Nessun preset salvato: usa «Salva preset» sotto una richiesta.';q('[data-apply]').disabled=q('[data-delete]').disabled=busy||!p;}
 async function run(fn){if(busy)return;busy=true;q('[data-error]').hidden=true;q('[data-confirm-save]').disabled=true;describe();try{await fn();}catch(e){q('[data-error]').textContent=e.message;q('[data-error]').hidden=false;}finally{busy=false;q('[data-confirm-save]').disabled=false;describe();}}
 async function refresh(){library=(await api('/generation-presets')).items;const previous=q('[data-kind]').value;q('[data-kind]').replaceChildren(new Option('Tutte',''));for(const [kind,label] of new Map(library.map(p=>[p.kind,p.label])))q('[data-kind]').append(new Option(label,kind));q('[data-kind]').value=previous;draw();}
 async function open(message){source=message?{chat_id:getChatId(),message_id:message.id}:null;q('[data-save]').hidden=!source;q('[data-error]').hidden=true;q('input').value='';dialog.showModal();await run(refresh);if(source)q('input').focus();}
 q('[data-close]').onclick=()=>dialog.close();q('[data-kind]').onchange=draw;q('[data-presets]').onchange=describe;
 q('[data-confirm-save]').onclick=()=>run(async()=>{if(!source)return;const name=q('input').value.trim();library=(await api('/generation-presets',{action:'save',...source,name})).items;q('[data-save]').hidden=true;source=null;await refresh();notify('Preset salvato.');});
 q('[data-apply]').onclick=()=>run(async()=>{const item=selected();if(!item)return;await apply(structuredClone(item.recipe));dialog.close();notify('Preset «'+item.name+'» caricato. Controlla gli allegati e premi Invia.');});
 q('[data-delete]').onclick=()=>run(async()=>{const item=selected();if(!item)return;await api('/generation-presets',{action:'delete',id:item.id});await refresh();notify('Preset eliminato.');});
 return {open:()=>open(),save:message=>open(message)};
}

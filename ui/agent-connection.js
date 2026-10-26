// This form is a human input surface. Password never enters chat/composer state.
const opened=new Set();
export function connectionPrompt({run,action,chatId,api,onChanged,notify,automatic=false}){
 const key=run.id+':'+action.id;
 if(automatic&&opened.has(key))return;
 if(document.querySelector('dialog[data-agent-connection]'))return;
 opened.add(key);
 const dialog=document.createElement('dialog');dialog.dataset.agentConnection=key;dialog.className='agent-connection-dialog';
 dialog.innerHTML='<form><header><h2>Configura connessione API</h2><p>Controlla server e modello. La chiave viene salvata dal servizio H3 e non passa al modello o nella chat.</p></header><div class="settings-grid"><label>Nome<input name="name" maxlength="100" required></label><label>Indirizzo base API<input name="base_url" type="url" required></label><label>ID modello<input name="model" maxlength="200" required></label><label>Chiave API<input name="api_key" type="password" autocomplete="new-password" placeholder="Inserisci qui la chiave"></label><label>Formato JSON<select name="format"><option value="json_object">JSON object</option><option value="json_schema">JSON schema</option><option value="prompt">Istruzioni nel prompt</option></select></label><label>Thinking<select name="thinking"><option value="none">Non configurato</option><option value="deepseek">DeepSeek</option><option value="openrouter">OpenRouter</option><option value="effort">reasoning_effort</option></select></label><label>Massimo immagini<input name="max_refs" type="number" min="1" max="9" value="4" required></label></div><label><input name="vision" type="checkbox"> Il modello accetta immagini / Vision</label><label><input name="use_for_run" type="checkbox"> Usa questo modello per proseguire questa sessione Agent</label><p class="small-note">Il modello predefinito dell’app resta invariato. La prova invia “Reply with OK.” al server indicato e può consumare credito; salvare da solo non esegue una prova.</p><p data-connection-status role="status" aria-live="polite"></p><footer><button type="button" data-close class="btn">Chiudi per ora</button><button type="button" data-reject class="text-button">Annulla richiesta</button><button type="button" data-test class="btn">Prova connessione</button><button type="submit" class="btn primary">Salva e continua</button></footer></form>';
 const form=dialog.querySelector('form'),status=dialog.querySelector('[data-connection-status]');
 for(const [name,value] of Object.entries(action.connection||{})){const input=form.elements.namedItem(name);if(!input)continue;if(input.type==='checkbox')input.checked=!!value;else input.value=String(value);}
 function clear(){form.elements.api_key.value='';dialog.remove();}
 dialog.addEventListener('close',clear,{once:true});dialog.querySelector('[data-close]').onclick=()=>dialog.close();
 async function submit(operation){
  if(!form.reportValidity())return;
  const buttons=[...dialog.querySelectorAll('button')];buttons.forEach(b=>b.disabled=true);status.textContent='Operazione in corso…';
  try{
   const config={};for(const name of ['name','base_url','model','format','thinking','max_refs','vision']){const input=form.elements.namedItem(name);config[name]=input.type==='checkbox'?input.checked:input.type==='number'?Number(input.value):input.value;}
   const value=await api(`/chats/${chatId}/agent-runs/${run.id}/connection`,{action_id:action.id,config,api_key:form.elements.api_key.value,use_for_run:form.elements.use_for_run.checked,operation});
   if(operation==='test'){status.textContent=value.message;return;}
   form.elements.api_key.value='';dialog.close();await onChanged();notify('Collegamento salvato. Agent può proseguire.');
  }catch(error){status.textContent=error.message;}finally{buttons.forEach(b=>b.disabled=false);}
 }
 form.onsubmit=event=>{event.preventDefault();submit('save');};dialog.querySelector('[data-test]').onclick=()=>submit('test');
 dialog.querySelector('[data-reject]').onclick=async()=>{try{await api(`/chats/${chatId}/agent-runs/${run.id}/resume`,{action_id:action.id,decision:'reject'});dialog.close();await onChanged();}catch(error){status.textContent=error.message;}};
 document.body.append(dialog);dialog.showModal();form.elements.api_key.focus();
}

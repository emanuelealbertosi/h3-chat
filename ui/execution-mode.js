export const cpuMode=state=>(state?.execution?.mode||state?.settings?.execution_mode)==='cpu';
export function chatModelId(state){
 if(!cpuMode(state))return state?.settings.chat_model;
 const ids=(state?.models||[]).filter(m=>m.api&&m.ready!==false&&m.capabilities.includes('chat')).map(m=>m.id);
 return [state?.settings.cpu_chat_model,state?.settings.chat_model,...ids].find(id=>ids.includes(id))||'';
}
export function cpuControls(value,state){return cpuMode(state)?{...value,image_model:'',music:false,video:false,voice:false,transcribe:false}:value;}
export function cpuRequest(body,state){
 if(!cpuMode(state))return body;
 const value=cpuControls(body,state);
 if(value.slides)value.slides={...value.slides,generate_images:false};
 if(value.infographic)value.infographic={...value.infographic,voice:false,music:'none',images:'provided',sfx:'none'};
 value.loras=[];return value;
}
export function initExecutionMode({api,getState,onChange,notify}){
 const group=document.createElement('span');group.className='execution-switch';group.setAttribute('role','group');group.ariaLabel='Modalità di esecuzione';
 group.innerHTML='<button type="button" data-execution="gpu" aria-pressed="true">GPU</button><button type="button" data-execution="cpu" aria-pressed="false">CPU</button>';
 document.querySelector('.top-actions').prepend(group);let pending=false;
 for(const button of group.querySelectorAll('button'))button.onclick=async()=>{
  if(pending||button.getAttribute('aria-pressed')==='true')return;
  pending=true;render();
  try{await api('/settings',{execution_mode:button.dataset.execution});await onChange();notify(button.dataset.execution==='cpu'?'Modalità CPU · chat e Assistant tramite API; RAG su CPU.':'Modalità GPU · impostazioni normali ripristinate.');}
  catch(error){notify(error.message,true);}finally{pending=false;render();}
 };
 function render(){
  const state=getState();if(!state)return;const cpu=cpuMode(state),noApi=cpu&&!chatModelId(state);
  const busy=state.jobs?.some(j=>['queued','running','cancelling'].includes(j.status))||state.projects?.some(p=>p.indexing);
  for(const b of group.querySelectorAll('button')){b.setAttribute('aria-pressed',String(b.dataset.execution===(cpu?'cpu':'gpu')));b.disabled=pending||busy||state.access?.role==='guest';}
  group.title=busy?'Attendi la fine dei lavori per cambiare modalità.':cpu?'Chat/Assistant via API, RAG e strumenti su CPU.':'Motori e impostazioni normali.';
  for(const id of ['prompt-images','music-toggle','video-toggle','voice-toggle','prompt-video-edit','transcribe-toggle','image-model','lora-open','slides-generate-images','slides-image-model','upscale-open','video-recreate-open','video-remix-open','video-edit-open']){
   const e=document.getElementById(id);if(!e)continue;
   if(cpu){if(!e.hasAttribute('data-cpu-disabled')){e.dataset.cpuDisabled=String(e.disabled);e.dataset.cpuTitle=e.title;}e.disabled=true;e.title='Disabilitato in modalità CPU';}
   else if(e.hasAttribute('data-cpu-disabled')){if(!['prompt-images','music-toggle','video-toggle','voice-toggle','prompt-video-edit','transcribe-toggle','slides-generate-images'].includes(id))e.disabled=e.dataset.cpuDisabled==='true';e.title=e.dataset.cpuTitle||'';delete e.dataset.cpuDisabled;delete e.dataset.cpuTitle;}
  }
  for(const e of document.querySelectorAll('[data-info=voice],[data-info=image_model],[data-infographic-field=images] button[data-value=generate],[data-infographic-field=music] button[data-value=generate],[data-infographic-field=music] button[data-value=jingle]')){e.disabled=cpu;e.title=cpu?'Generazione disabilitata in modalità CPU':'';}
  const assistant=document.querySelector('#image-assistant');if(assistant)assistant.disabled=noApi;
  for(const b of document.querySelectorAll('#prompt-sources button'))if(b.textContent.startsWith('Assistant')){b.disabled=noApi;b.title=noApi?'Configura un provider LLM esterno nelle Impostazioni API.':'Assistant usa il modello chat selezionato.';}
  if(noApi){document.querySelector('#send').disabled=true;document.querySelector('#regenerate').disabled=true;}
  const hint=document.querySelector('#execution-hint');if(cpu&&hint)hint.textContent=noApi?'CPU · Collega un provider LLM esterno nelle Impostazioni API per usare chat e Assistant.':'CPU · Chat e Assistant via API · RAG, documenti e grafica su CPU · Generazione immagini, video e audio disabilitata';
 }
 return {render};
}

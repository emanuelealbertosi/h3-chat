import {escape as esc} from './render.js';
import {modelLabel} from './model-identity.js';

export function initChatModels({api,getState,onChange,notify}){
  const row=document.createElement('div');row.className='chat-controls chat-model-controls';
  row.innerHTML='<label class="think-control chat-model-control" for="chat-model">LLM <select id="chat-model" aria-label="Modello chat" aria-describedby="chat-model-note"></select></label><label class="think-control">Vision <select id="chat-vision-device" aria-label="Dispositivo Vision" aria-describedby="chat-vision-device-note"><option value="cpu">CPU</option><option value="gpu">GPU</option></select></label><span id="chat-vision-device-note" class="small-note"></span><span id="chat-model-note" class="small-note" role="status">Dal prossimo messaggio</span>';
  document.querySelector('#prompt').after(row);
  const select=row.querySelector('#chat-model'),vision=row.querySelector('#chat-vision-device'),visionNote=row.querySelector('#chat-vision-device-note'),note=row.querySelector('#chat-model-note');
  let pending=null,revision=0,committed=null,signature='';

  function render(){
    const state=getState();if(!state){select.disabled=true;return;}
    const models=state.models.filter(model=>model.capabilities.includes('chat'));
    const selected=pending?.patch?.chat_model??state.settings.chat_model;
    const next=JSON.stringify(models.map(model=>[model.id,modelLabel(model),!!model.api,model.ready]));
    if(next!==signature){
      signature=next;
      select.innerHTML='<option value="" disabled>Scegli un modello</option>'+[false,true].map(remote=>{
        const group=models.filter(model=>!!model.api===remote);
        return group.length?`<optgroup label="${remote?'Provider API':'Sul tuo computer'}">${group.map(model=>`<option value="${esc(model.id)}" ${model.ready===false?'disabled':''}>${esc(modelLabel(model))}${model.ready===false?' · non disponibile':''}</option>`).join('')}</optgroup>`:'';
      }).join('');
    }
    select.value=selected||'';
    select.disabled=!!pending||!models.some(model=>model.ready!==false);
    select.setAttribute('aria-busy',String(!!pending));
    select.title=modelLabel(models.find(model=>model.id===selected));
    const model=models.find(model=>model.id===selected),settings={...state.settings,...pending?.patch};
    const gpu=settings.llm_device==='gpu'||settings.llm_device!=='cpu'&&settings.profile!=='cpu'&&['cuda','vulkan'].includes(settings.backend);
    vision.value=settings.vision_device||'cpu';vision.disabled=!!pending||!!model?.api||!model?.vision?.enabled||!settings.vision_enabled;
    vision.querySelector('[value="gpu"]').disabled=!gpu;
    visionNote.textContent=model?.api?'Vision gestita dal provider':!model?.vision?.enabled?'Modello senza Vision':!settings.vision_enabled?'Vision Off':!gpu?'GPU richiede un motore CUDA o Vulkan nelle Preferenze':vision.value==='gpu'?'Più veloce · usa VRAM':'Risparmia VRAM · può essere lenta';
    note.textContent=pending?'Salvataggio…':'Dal prossimo messaggio';
    row.title='Mantiene questa conversazione e recupera le preferenze salvate del modello. I lavori già avviati continuano con il modello precedente.';
  }

  function change(patch){
    if(pending){render();return pending.promise;}
    const state=getState();
    if(Object.entries(patch).every(([key,value])=>value===state.settings[key]))return Promise.resolve();
    if(patch.chat_model&&!state.models.some(model=>model.id===patch.chat_model&&model.capabilities.includes('chat')&&model.ready!==false)){render();return Promise.reject(Error('Questo modello non è disponibile.'));}
    committed=state.settings;revision++;pending={patch,promise:null};
    pending.promise=(async()=>{
      try{
        const settings=await api('/settings',patch);
        committed=settings;onChange(settings);
      }finally{revision++;pending=null;onChange();}
    })();
    onChange();
    return pending.promise;
  }
  select.onchange=()=>change({chat_model:select.value}).catch(error=>notify(error.message,true));
  vision.onchange=()=>change({vision_device:vision.value}).catch(error=>notify(error.message,true));
  return {
    render,
    busy:()=>!!pending,
    wait:()=>pending?.promise||Promise.resolve(),
    revision:()=>revision,
    reconcile:(next,started)=>pending||started!==revision?{...next,settings:committed||getState()?.settings||next.settings}:next,
  };
}

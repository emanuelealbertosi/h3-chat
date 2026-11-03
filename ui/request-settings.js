// Reloaded model preferences belong to the draft, never to global defaults.
export function initRequestSettings({getChatId,onClear}){
 let base=null;
 const key=()=> 'h3.request-settings.'+(getChatId()||'new');
 const read=()=>{try{return JSON.parse(localStorage.getItem(key())||'null');}catch{return null;}};
 const save=value=>{if(value&&Object.keys(value).length)localStorage.setItem(key(),JSON.stringify(value));else localStorage.removeItem(key());};
 const overlay=value=>({...value,...read(),...(value.execution_mode==='cpu'&&read()?.chat_model?{cpu_chat_model:read().chat_model}:{}),...Object.fromEntries(['image_overrides','video_overrides','music_overrides','llm_overrides'].map(k=>[k,{...value[k],...read()?.[k]}]))});
 const note=document.createElement('p');note.className='small-note';note.hidden=true;note.id='request-settings-note';
 const label=document.createElement('span'),clear=document.createElement('button');clear.type='button';clear.className='text-button';clear.textContent='Usa impostazioni attuali';note.append(label,' ',clear);
 document.querySelector('#prompt').after(note);
 function render(){note.hidden=!read();label.textContent='Impostazioni recuperate dalla richiesta · modificabili · predefiniti invariati.';}
 clear.onclick=()=>{save(null);render();onClear?.();};
 return {
  read,apply(value){save(value);render();},render,migrateNew(id){const value=read();if(value)localStorage.setItem('h3.request-settings.'+id,JSON.stringify(value));localStorage.removeItem(key());},
  state(value){base=structuredClone(value.settings);render();return {...value,settings:overlay(base)};},
  current(value){render();return base?{...value,settings:overlay(base)}:value;},
  request(path,body){return body&&getChatId()&&path.startsWith('/chats/'+getChatId()+'/')&&/\/(messages|slide-backgrounds|image-lots|video-edit|upscale|video-remix)$/.test(path)&&read()?{...body,request_settings:structuredClone(read())}:body;},
  settingsChanged(value,patch){
   base=structuredClone(value);let saved=read();
   if(saved){
    for(const name of Object.keys(patch))if(name in saved)saved[name]=structuredClone(value[name]);
    if('chat_model' in patch||'cpu_chat_model' in patch){
     for(const name of ['chat_model','context','max_tokens','temperature','think_level','gpu_layers','mtp_enabled','mtp_draft_tokens','prompt_max_tokens','music_prompt_max_tokens','video_prompt_max_tokens','llm_timeout','vision_max_refs','llm_acceleration','llm_overrides',...Object.keys(saved).filter(k=>k.startsWith('llm_steering'))])if(name in value)saved[name]=structuredClone(value[name]);
    }
    save(saved);
   }
   render();return overlay(base);
  }
 };
}

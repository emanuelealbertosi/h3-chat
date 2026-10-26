// Group existing controls without recreating them or losing their draft values.
export function organizeSettings(body,tab){
 if(tab!=='advanced')return;
 const groups=[['chat','Chat e immagini'],['agent','Agente autonomo'],['media','Video, musica e voce'],['rag','Progetti e RAG'],['computer','Calcolo e memoria'],['tools','Strumenti'],['access','Server e accessi']];
 const holders=new Map(),nav=document.createElement('nav');nav.className='settings-sections';nav.ariaLabel='Sezioni delle preferenze';
 for(const [key,label] of groups){const section=document.createElement('section');section.className='settings-section';section.dataset.settingsSection=key;const title=document.createElement('h3');title.textContent=label;section.append(title);holders.set(key,section);const button=document.createElement('button');button.type='button';button.className='btn small';button.textContent=label;button.onclick=()=>section.scrollIntoView({behavior:'smooth',block:'start'});nav.append(button);}
 for(const [selector,key] of [['.network-settings-section','access'],['.device-settings-section','computer'],['.lab-settings-section','tools'],['.agent-settings-section','agent']])for(const e of body.querySelectorAll(selector))holders.get(key).append(e);
 const threads=body.querySelector('[data-setting="threads"]')?.closest('label');if(threads){const card=document.createElement('section');card.className='card';card.append(threads);holders.get('computer').append(card);}
 for(const child of [...body.children]){
  const key=child.matches('.memory-assessment')?'computer':child.matches('.video-settings,.music-settings,.voice-settings,.upscale-settings')?'media':child.matches('.server-settings-section')?'access':child.matches('.workspace-settings')?'rag':child.matches('.tools-settings')?'tools':child.querySelector('#llm-settings-card')?'chat':child.matches('.lora-folder-settings')?'chat':child.querySelector('[data-media-server]')?'access':'media';holders.get(key).append(child);
 }
 body.append(nav,...holders.values());for(const section of holders.values())if(section.children.length===1)section.hidden=true;
}

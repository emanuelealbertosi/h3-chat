import {settingsPages,compactForm,foldSettingsHelp} from './settings-navigation.js';
export function organizeSettings(body,tab){
 if(tab!=='advanced')return null;
 const definitions=[['chat','Chat e Assistant'],['images','Immagini e LoRA'],['video','Video'],['music','Musica'],['voice','Voce'],['rag','Progetti e RAG'],['agent','Agente'],['tools','Ricerca e strumenti'],['computer','Computer e memoria'],['access','Server e accessi'],['general','Istruzioni personali']];
 const groups=new Map(definitions.map(([id,label])=>[id,{id,label,nodes:[]}]));
 const add=(key,node)=>{if(node){node.remove();groups.get(key).nodes.push(node);}};
 for(const [selector,key] of [['.network-settings-section','access'],['.device-settings-section','computer'],['.lab-settings-section','tools'],['.agent-settings-section','agent']])for(const e of body.querySelectorAll(selector))add(key,e);
 const grid=body.querySelector(':scope > .settings-grid');if(grid){for(const card of [...grid.children])add(card.id==='llm-settings-card'?'chat':card.id==='image-settings-card'?'images':'general',card);grid.remove();}
 for(const child of [...body.children]){if([...groups.values()].some(g=>g.nodes.includes(child)))continue;add(child.matches('.memory-assessment')?'computer':child.matches('.video-settings,.upscale-settings')?'video':child.matches('.music-settings')?'music':child.matches('.voice-settings')?'voice':child.matches('.server-settings-section')?'access':child.matches('.workspace-settings')?'rag':child.matches('.tools-settings')?'tools':child.matches('.lora-folder-settings')?'images':'video',child);}
 for(const group of groups.values())for(const node of group.nodes)if(!node.matches('.memory-assessment'))compactForm(node,'advanced-'+group.id+'-'+(node.id||node.className));
 const controller=settingsPages(body,[...groups.values()],{key:tab});foldSettingsHelp(body);return controller;
}

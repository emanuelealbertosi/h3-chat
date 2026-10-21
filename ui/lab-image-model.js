export function labImageDefault(state){
 const available=state.models.filter(m=>m.ready&&m.capabilities?.includes('create'));
 const qwen=available.filter(m=>m.architecture==='qwen21'&&m.external_config?.profile!=='qwen21-turbo');
 return qwen.find(m=>m.id===state.settings.create_model)||qwen.sort((a,b)=>a.id.localeCompare(b.id))[0]||available.find(m=>m.id===state.settings.create_model);
}

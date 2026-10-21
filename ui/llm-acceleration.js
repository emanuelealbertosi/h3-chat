export function acceleratedPreset(values,model){
 const tokens=model?.acceleration?.draft_tokens??2;
 if(![2,4].includes(tokens))throw Error('Profilo MTP non verificato');
 return {...values,llm_acceleration:'qwen27',context:131072,gpu_layers:999,
  mtp_enabled:true,mtp_draft_tokens:tokens,think_level:'low',
  max_tokens:Math.min(values.max_tokens,65536)};
}
export function acceleratorAvailable(model,draft){
 return !!(model?.acceleration?.supported&&model.acceleration.installed&&
  draft.backend==='cuda'&&draft.llm_device!=='cpu'&&
  (draft.profile!=='cpu'||draft.llm_device==='gpu'));
}

export const attentionChoices=[['auto','Automatico · Sage'],['veda','VEDA · gruppi automatici'],['veda8','VEDA 8 · gruppi espliciti'],['veda56','VEDA 56 · gruppi espliciti'],['sage','SageAttention'],['comfy_kitchen','ComfyKitchen INT8 · sperimentale'],['pytorch','Nessuna accelerazione aggiuntiva · PyTorch']];
export const needsAttentionUpdate=value=>['veda8','veda56','comfy_kitchen'].includes(value);

export function attentionSelection(parameters={}){
 return parameters.attention==='veda'&&parameters.attention_chunks_mode==='manual'?'veda'+parameters.attention_chunks:parameters.attention||'auto';
}

export function attentionParameters(value,explicit=true){
 if(value==='veda8'||value==='veda56')return {attention:'veda',attention_chunks:Number(value.slice(4)),attention_chunks_mode:'manual'};
 return {attention:value,...(explicit?{attention_chunks:0,attention_chunks_mode:'auto'}:{})};
}

export function bindAttention(select,{parameters={},explicit=false}={}){
 // Old servers retain their existing choices; never send unsupported fields.
 select.replaceChildren(...attentionChoices.map(([value,label])=>{
  const option=document.createElement('option');option.value=value;option.textContent=label;
  option.disabled=!explicit&&needsAttentionUpdate(value);return option;
 }));
 select.value=attentionSelection(parameters);
 return {read:()=>attentionParameters(select.value,explicit),set:parameters=>{select.value=attentionSelection(parameters);}};
}

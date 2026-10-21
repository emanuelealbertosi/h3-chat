// Adopt the requested MOSS default once; later explicit empty values stay empty.
export const MOSS_NEGATIVE_PROMPT='low quality, blurry, jpeg artifacts, bad anatomy, malformed hands, extra fingers, missing fingers, extra limbs, distorted face';
export const mossNegativeDefault=state=>state?.image_options?.moss_negative_prompt??MOSS_NEGATIVE_PROMPT;
export function migrateMossNegativeDefaults(value,state){
 if(!state?.image_options)return value;
 const adopted=new Set(value.moss_negative_defaults||[]),presets={...value.image_presets};let changed=false;
 for(const model of state.models||[]){
  if(model.architecture!=='moss'||adopted.has(model.id))continue;
  const preset=presets[model.id];
  if(preset?.negative_prompt===''){
   const next={...preset};delete next.negative_prompt;presets[model.id]=next;
  }
  adopted.add(model.id);changed=true;
 }
 return changed?{...value,image_presets:presets,moss_negative_defaults:[...adopted]}:value;
}

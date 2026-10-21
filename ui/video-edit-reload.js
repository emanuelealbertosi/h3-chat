import {draftSignature} from './video-editor-draft.js';

export function lastLaunchDraft(data){
 const launch=data.last_launch;if(!launch)return null;
 const draft=reloadEditDraft(data,launch.edit,{model:launch.model,parameters:launch.parameters,steps:launch.steps,assistant:launch.assistant,references:launch.image_refs});
 const pending=new Set(launch.pending_clips||[]);
 for(const clip of draft.state.clips)clip.enabled=pending.has(clip.clip);
 draft.state.active=launch.pending_clips?.[0]??launch.edit.patches[0]?.clip??null;
 draft.state.clip_launches=launch.clip_launches||{};
 return {...draft,saved_at:launch.saved_at,last_launch:true};
}

// Reopen the edit contract, never turn its internal frame archive into a
// normal chat request. Resolve ordinals by identity if the source evolved.
export function reloadEditDraft(data,edit,{model,parameters,steps,assistant,references}){
 const images=[...data.images];
 for(const ref of references)if(!images.some(x=>x.id===ref.id))images.push({...ref,index:images.length+1,url:'/media/'+ref.path});
 const number=n=>{if(n==null)return null;const id=edit.image_ids[n-1],found=images.find(x=>x.id===id);if(!found)throw Error('Un riferimento della modifica originale non è più disponibile.');return found.index;};
 const text=s=>(s||'').replace(/<Picture\s+(\d+)>/gi,(_,n)=>'<Picture '+number(Number(n))+'>');
 const clips=data.clips.map(c=>{
  const patch=edit.patches.find(p=>p.clip===c.clip),frames=Math.round((c.end-c.start)*24);
  if(patch&&patch.end!=null&&Math.round(patch.end*24)>frames)throw Error('La durata della clip è cambiata: ricontrolla il tratto prima di rilanciare.');
  return {enabled:!!patch,clip:c.clip,prompt:text(patch?.prompt),images:(patch?.images||[]).map(number),lip_sync:patch?.lip_sync??false,audio_guide:patch?.audio_guide??true,
   range:patch?.start!=null,first:Math.round((patch?.start||0)*24),last:patch?.end!=null?Math.round(patch.end*24):frames,frames,
   mode:patch?.mode||'video',anchors:patch?.anchors||'none',anchor_image:number(patch?.anchor_image),start_image:number(patch?.start_image),
   auto_anchors:patch?.auto_anchors||false,anchor_edit_model:patch?.anchor_edit_model||'',anchor_images:Object.fromEntries(Object.entries(patch?.anchor_images||{}).map(([k,n])=>[k,number(n)]))};
 });
 return {image_refs:references,state:{signature:draftSignature(data.clips),model,parameters,
  values:{megapixels:String(parameters.megapixels??''),video_steps:steps==null?'':String(steps),reference_megapixels:String(edit.patches[0]?.reference_megapixels??.35),assistant,remount:edit.remount!==false},
  active:edit.patches[0]?.clip??null,common_prompt:'',image_ids:images.map(x=>x.id),clips,versions:edit.versions||{}}};
}

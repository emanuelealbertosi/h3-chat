// Existing clip-only exports retain their job path even before timeline IDs.
export function videoTimelineSource(media){
 if(!media.mime?.startsWith('video/'))return null;
 const saved=media.generation?.timeline_id;
 if(/^[a-f0-9]{32}$/.test(saved||''))return {id:saved,recover:false};
 const generation=media.generation;
 if(!generation?.clip_only||!generation?.post_edit)return null;
 const job=media.path?.match(/^outputs\/([a-f0-9]{32})\/clip-\d+\.mp4$/)?.[1];
 return job?{id:job,recover:true}:null;
}

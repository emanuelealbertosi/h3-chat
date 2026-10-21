export function galleryVideoLabel(item){
 if(!item.mime?.startsWith('video/'))return '';
 if(item.video_kind==='timeline')return (item.timeline_only&&['cancelled','failed','interrupted'].includes(item.timeline_status)?'Timeline interrotta':'Timeline')+' · '+item.clip_count+' clip';
 if(item.video_kind==='clip')return 'Spezzone · timeline collegata';
 return 'Video';
}

export function appendGalleryDetails(host,item){
 const label=galleryVideoLabel(item);
 if(label){const badge=document.createElement('span');badge.className='gallery-video-kind';badge.dataset.kind=item.video_kind||'video';badge.textContent=label;host.append(badge);}
 if(item.timeline_only&&Number.isInteger(item.completed_clips)&&item.requested_clips>0){
  const progress=document.createElement('small');progress.className='gallery-timeline-progress';
  progress.textContent=item.completed_clips+' / '+item.requested_clips+' modifiche completate';host.append(progress);
 }
 const stamp=item.modified||item.created;
 if(!Number.isFinite(stamp)||stamp<=0)return;
 const time=document.createElement('time'),date=new Date(stamp*1000);
 time.className='gallery-modified';time.dateTime=date.toISOString();
 time.textContent=(item.modified?'Ultima modifica: ':'Aggiunto: ')+date.toLocaleString('it-IT',{day:'2-digit',month:'2-digit',year:'numeric',hour:'2-digit',minute:'2-digit'});
 time.title=time.textContent;host.append(time);
}

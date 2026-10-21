"""Assemble an existing working timeline through the shared queue, without AI."""
import copy
from .downloads import Cancelled, safe_join
from .video_edit import source
from .video_resume import save


def remove_clips(record,numbers):
    count=len(record['timeline'])
    if not isinstance(numbers,list) or not numbers or any(type(n) is not int or not 1<=n<=count for n in numbers) or len(set(numbers))!=len(numbers) or len(numbers)>=count:
        raise ValueError('Scegli clip validi da eliminare, lasciandone almeno uno.')
    keep=[i for i in range(count) if i+1 not in numbers];result=copy.deepcopy(record);cursor=0;intervals=[]
    for key in ('timeline','outputs','prompts','parameters','clip_sources','clip_versions'):
        if key in record:result[key]=[copy.deepcopy(record[key][i]) for i in keep]
    for new,i in enumerate(keep):
        old=record['timeline'][i];scene=result['timeline'][new]
        intervals.append({'start':record.get('audio_start',0)+old['start'],'duration':old['duration']})
        scene.update(index=new,start=cursor)
        for version in result.get('clip_versions',[[] for _ in keep])[new]:version['scene'].update(index=new,start=cursor)
        cursor+=scene['duration']
    result['selected_versions']={str(n+1):record.get('selected_versions',{}).get(str(i+1)) for n,i in enumerate(keep) if str(i+1) in record.get('selected_versions',{})}
    result['edited_clips']=[n+1 for n,i in enumerate(keep) if i+1 in record.get('edited_clips',[])]
    for key in ('revision_request','revision_completed','revision_plans','revision_generated','revision_versions','storyboard'):
        result.pop(key,None)
    result.update(completed=len(keep),audio_start=0,working_timeline=True,removed_clips=sorted(numbers))
    result['plan']=copy.deepcopy(record['plan'])
    for image in result['plan'].get('images',[]):
        if image.get('role')!='keyframe':continue
        stamp=image.get('seconds',0);shift=0
        for i,scene in enumerate(record['timeline']):
            if i+1 not in numbers:continue
            if scene['start']<=stamp<scene['start']+scene['duration']:
                image.update(role='reference',seconds=0);break
            if scene['start']+scene['duration']<=stamp:shift+=scene['duration']
        else:image['seconds']=max(0,stamp-shift)
    for audio in result['plan']['audios']:audio['start']=0
    return result,intervals


def request(app,chat_id,body):
    value=source(app,chat_id,body.get('source'),body.get('segment_seconds'))
    from .video_versions import choices
    selected=choices(app,chat_id,body['source'],value,body.get('versions'))
    removed=body.get('remove_clips',[])
    if removed:remove_clips(value['record'],removed)
    if not removed and not value['record'].get('working_timeline') and not any(len(v)>1 for v in value['record']['clip_versions']):
        raise ValueError('Scegli una timeline modificata e salvata.')
    canvas=body.get('canvas',False)
    if type(canvas) is not bool:raise ValueError('Destinazione canvas non valida.')
    settings=app.store.settings()|{'_video_assemble':body['source'],'_video_assemble_versions':selected,'_video_remove_clips':removed,'_video_assemble_segment_seconds':body.get('segment_seconds'),'_assistant':False,'_rag':False}
    ident=app.store.enqueue(chat_id,f"Montaggio del video completo · {len(value['record']['timeline'])-len(removed)} clip",[],settings,canvas)
    app.wake.set()
    return {'job_id':ident,'canvas':canvas}


def render(app,job,payload,settings,cancel,stage,log):
    value=source(app,job['chat_id'],settings['_video_assemble'],settings.get('_video_assemble_segment_seconds'))
    from .video_versions import choices,apply
    selected=choices(app,job['chat_id'],settings['_video_assemble'],value,settings.get('_video_assemble_versions'))
    apply(value,selected,app.data)
    record=copy.deepcopy(value['record'])
    if cancel.is_set():raise Cancelled()
    from .soundtrack import compose
    folder=app.data/'outputs'/job['id'];folder.mkdir(parents=True,exist_ok=True)
    from .video_import import prepare
    from .video_import import repair_import_audio
    repair_import_audio(app,value,cancel,stage,log)
    audio=value['audio'];removed=settings.get('_video_remove_clips',[])
    if removed:
        record,intervals=remove_clips(record,removed)
        from .store import uid
        audio={'id':uid(),'name':'Audio della timeline tagliata.wav','mime':'audio/wav','path':(folder/'timeline-audio.wav').relative_to(app.data).as_posix()}
        app.engine.tool_call('video-remix-worker.py',{'op':'timeline_audio','runtime':{'backend':'cpu','threads':4},'folder':str(folder),
            'source':str(safe_join(app.data,value['audio']['path'])),'output':str(safe_join(app.data,audio['path'])),'intervals':intervals},cancel,stage,log,timeout=3600)
        value=value|{'duration':sum(s['duration'] for s in record['timeline'])}
    prepare(app,value|{'record':record},cancel,stage,log)
    stage(f"Timeline · montaggio di tutte le {len(record['timeline'])} clip con audio originale")
    result=compose(app.engine,[safe_join(app.data,p) for p in record['outputs']],
        safe_join(app.data,audio['path']),folder/'video.mp4',cancel,stage,log,
        audio_start=record.get('audio_start',0),audio_duration=value['duration'])
    record['revision_remount']=True;record['working_timeline']=True;save(folder,record)
    parameters=value['meta'].get('video_parameters',{}).copy()
    for key in ('clip_only','source_intervals','source_interval','timeline_id'):parameters.pop(key,None)
    parameters.update(duration=result['duration'],scenes=len(record['timeline']),
        scene_parameters=record['parameters'],audio_preserved=True,audio_start=record.get('audio_start',0),
        remount=True,post_edit=True,assembled_timeline=settings['_video_assemble'],edited_clips=record.get('edited_clips',[]))
    parameters.update(engine='minimax-h3',imported_video=bool(record.get('imported_size')))
    media={'id':job['id'],'name':'Video · timeline montata.mp4','mime':'video/mp4',
        'path':(folder/'video.mp4').relative_to(app.data).as_posix(),'generation':parameters}
    meta={'intent':'video','canvas':bool(payload.get('canvas')),'assistant_on':False,
        'execution_mode':'Standalone · CPU · montaggio timeline','references':[audio if r['id']==value['audio']['id'] else r for r in value['refs']],
        'video_plan':record['plan'],'video_parameters':parameters}
    if payload.get('canvas'):
        app.save_artifact(job['chat_id'],'Video · timeline montata','',[media])
        meta['artifact']={'title':'Video · timeline montata','content':'','media':[media]}
    parameters['removed_clips']=removed
    app.store.update_answer(job,('Ho rimosso le clip '+', '.join(map(str,removed))+' e i corrispondenti tratti audio. Il video originale resta disponibile.') if removed else 'Ho montato la timeline aggiornata con l’audio originale, riutilizzando tutte le clip salvate.',
        'done',[] if payload.get('canvas') else [media],meta)
    app.store.execute("UPDATE jobs SET status='done',stage='Timeline montata' WHERE id=?",(job['id'],))

"""Queued insertion of an independent, boundary-guided or native extended clip."""
import copy
import math
from pathlib import Path
from uuid import uuid4
from .downloads import safe_join, Cancelled
from .video_clip_tools import target, dimensions
from .video_edit import clip_source
from .video_options import validate, options, resolve_canvas, validate_plan
from .video_resume import save


def boundary(value, command):
    return command['clip'] if command['side']=='after' else command['clip']-1


def request(app, chat_id, body):
    value,command=target(app,chat_id,{k:v for k,v in body.items() if k not in ('start','end')})
    mode=body.get('mode','frames');side=body.get('side','after');duration=body.get('duration',15)
    if mode not in ('extension','clip','frames') or side not in ('before','after') or type(duration) is not int or duration not in (5,10,15):
        raise ValueError('Scegli modalità, prima/dopo e durata di 5, 10 o 15 secondi.')
    if len(value['record']['timeline'])>=160:raise ValueError('La timeline contiene già 160 clip.')
    prompt=body.get('prompt','')
    if not isinstance(prompt,str) or not prompt.strip() or len(prompt)>24000:raise ValueError('Descrivi la nuova clip (massimo 24.000 caratteri).')
    assistant=body.get('assistant',True);lip=body.get('lip_sync',False)
    if type(assistant) is not bool or type(lip) is not bool:raise ValueError('Assistant e lip-sync: scegli On oppure Off.')
    command.update(mode=mode,side=side,duration=duration,prompt=prompt.strip(),lip_sync=lip)
    cut=boundary(value,command);anchors={}
    for key,automatic,exists in (('first','previous',cut>0),('last','next',cut<len(value['record']['timeline']))):
        choice=body.get(key,automatic if exists else 'none') if mode=='frames' else 'none'
        if not isinstance(choice,str):raise ValueError('Fotogramma di raccordo non valido.')
        if choice==automatic:
            if not exists:raise ValueError('Il video adiacente per questo fotogramma non esiste.')
            anchors[key]=choice
        elif choice!='none':
            media=app.validate_media([{'id':choice}])[0]
            if not media['mime'].startswith('image/'):raise ValueError('Il fotogramma deve essere un’immagine.')
            anchors[key]=media
    if mode=='frames' and not anchors:raise ValueError('Scegli almeno un primo o ultimo fotogramma.')
    # Keep only explicitly chosen references; do not inherit all film images.
    media=app.validate_media(body.get('media',[]))
    if any(not m['mime'].startswith('image/') for m in media) or len(media)+len(anchors)>9:
        raise ValueError('Scegli fino a nove immagini complessive, compresi i fotogrammi.')
    audio=None
    if body.get('audio_id'):
        audio=app.validate_media([{'id':body['audio_id']}])[0]
        if not audio['mime'].startswith('audio/'):raise ValueError('La guida audio deve essere una traccia audio.')
    if lip and audio is None:raise ValueError('Per il lip-sync scegli una guida audio.')
    audio_start=body.get('audio_start',0)
    if type(audio_start) not in (int,float) or not math.isfinite(audio_start) or not 0<=audio_start<=3600:
        raise ValueError('Inizio della guida audio: indica un secondo tra 0 e 3600.')
    command.update(anchors=anchors,media=media,audio=audio,audio_start=audio_start)
    settings=app.validate_settings({});selected=body.get('model') or settings['video_model']
    model=app.engine.require_model(selected,'video')
    if model.get('remote_media'):raise ValueError('L’inserimento con continuità richiede MiniMax H3 standalone.')
    from .video_recreate import EDITABLE
    parameters=body.get('parameters',{})
    if not isinstance(parameters,dict) or set(parameters)-set(EDITABLE):raise ValueError('Parametri video non validi.')
    preset=validate(settings.get('video_overrides',{}).get(selected,{})|parameters|{'duration':duration})
    from .video_loras import aligned
    if aligned(preset['loras']):raise ValueError('I LoRA di modifica del video non si applicano a nuove clip. Deselezionali; PDD resta utilizzabile.')
    settings.update(video_model=selected,video_overrides=settings.get('video_overrides',{})|{selected:preset},
                    _assistant=assistant,_rag=False,_video_extend=command,_video_duration=duration,_video_quality='high')
    if audio:settings.update(_video_soundtrack=audio,_video_audio_start=audio_start)
    if assistant:app.engine.require_model(settings['chat_model'],'chat')
    refs=media+[a for a in anchors.values() if isinstance(a,dict)]+([audio] if audio else [])
    refs=list({m['id']:m for m in refs}.values())
    ident=app.store.enqueue(chat_id,f"Nuova clip · {duration} s · {'dopo' if side=='after' else 'prima'} della clip {command['clip']}\n"+prompt.strip(),refs,settings,False)
    app.wake.set();return {'job_id':ident,'canvas':False}


def extract_frames(app,value,index,last,count,folder,cancel,stage,log):
    source=clip_source(value,index);scene=value['record']['timeline'][index]
    # A legacy tail can be shorter than the native context. Repeat its exact
    # boundary still rather than reading outside the selected scene.
    actual=min(count,scene['frames']);start=source['start']+(scene['frames']-actual)/24 if last else source['start']
    result=app.engine.tool_call('video-extension-worker.py',{'op':'frames','source':str(safe_join(app.data,source['path'])),
        'start':start,'frames':actual,'folder':str(folder)},cancel,stage,log,timeout=180)
    paths=result['paths']
    return paths+paths[-1:]*(count-len(paths))


def inserted_record(original, item, plan, index, duration, refs, local_refs, audio, model):
    """Shift clocks and version snapshots together, preserving all old outputs."""
    from .video_versions import remap_prompt
    record=copy.deepcopy(original);offset=sum(s['frames'] for s in record['timeline'][:index])/24
    global_images=[m for m in refs if m['mime'].startswith('image/')];known={m['id']:i for i,m in enumerate(global_images,1)}
    mapping={i:known[m['id']] for i,m in enumerate([r for r in local_refs if r['mime'].startswith('image/')],1)}
    scene={'index':index,'start':offset,'frames':duration*24,'duration':duration,'continuity':'cut',
           'images':[entry|{'index':mapping[entry['index']]} for entry in plan['images']],'lip_sync':any(a['role']=='lipsync' for a in plan['audios'])}
    for key,entry in [('timeline',scene),('outputs',item['path']),('parameters',item['generation']),('prompts',remap_prompt(plan['prompt'],mapping))]:record[key].insert(index,entry)
    record.setdefault('clip_sources',[None]*(len(record['timeline'])-1)).insert(index,None)
    record.setdefault('clip_versions',[[] for _ in range(len(record['timeline'])-1)]).insert(index,[])
    cursor=0
    for i,s in enumerate(record['timeline']):
        s.update(index=i,start=cursor);cursor+=s['duration']
        for version in record['clip_versions'][i]:version['scene'].update(index=i,start=s['start'])
    record['selected_versions']={str(int(k)+(1 if int(k)>index else 0)):v for k,v in record.get('selected_versions',{}).items()}
    record['edited_clips']=[n+(1 if n>index else 0) for n in record.get('edited_clips',[])]
    for key in ('storyboard','recreate_recipes','revision_request','revision_plans','revision_generated','revision_completed','revision_auto_guides','revision_versions'):record.pop(key,None)
    global_plan=copy.deepcopy(original['plan'])
    for image in global_plan['images']:
        if image['role']=='keyframe' and image['seconds']>=offset:image['seconds']+=duration
    used={i['index'] for i in global_plan['images']}
    for ordinal in range(1,len(global_images)+1):
        if ordinal not in used:global_plan['images'].append({'index':ordinal,'role':'reference','seconds':0})
    track=next(a['index'] for a in original['plan']['audios'] if a['role'] in ('reuse','lipsync'))
    for entry in global_plan['audios']:
        if entry['index']==track:entry.update(role='reuse',start=0)
    if track!=1:
        import re
        record['prompts'][index]=re.sub(r'<Audio\s+1>',f'<Audio {track}>',record['prompts'][index],flags=re.I)
    record.update(plan=global_plan,audio_start=0,completed=len(record['timeline']),model=model,
                  working_timeline=True,revision_remount=True,inserted_clip=index+1)
    return record


def render(app,job,payload,settings,cancel,stage,log):
    command=settings['_video_extend'];value,_=target(app,job['chat_id'],command)
    index=boundary(value,command);duration=command['duration'];folder=app.data/'outputs'/job['id'];folder.mkdir(parents=True,exist_ok=True)
    # target() freezes server-owned selected versions; never read another clip.
    refs=list(command['media']);guides=[];context=None
    for key,anchor in command['anchors'].items():
        if isinstance(anchor,str):
            neighbor=index-1 if key=='first' else index
            path=extract_frames(app,value,neighbor,key=='first',1,folder/key,cancel,stage,log)[0]
            anchor={'id':uuid4().hex,'name':f'Raccordo · {key}.png','path':Path(path).relative_to(app.data).as_posix(),'mime':'image/png'}
            app.store.gallery.register([anchor],internal=True)
        if any(m['id']==anchor['id'] for m in refs):ordinal=next(i for i,m in enumerate(refs,1) if m['id']==anchor['id'])
        else:refs.append(anchor);ordinal=len(refs)
        if any(g['index']==ordinal for g in guides):
            # The same image may intentionally anchor both ends (a loop).
            # H3 plans assign one time per image ordinal, so save an alias copy.
            import shutil
            alias=folder/(key+'-anchor'+Path(anchor['path']).suffix)
            shutil.copyfile(safe_join(app.data,anchor['path']),alias)
            anchor=anchor|{'id':uuid4().hex,'path':alias.relative_to(app.data).as_posix()}
            refs.append(anchor);ordinal=len(refs);app.store.gallery.register([anchor],internal=True)
        guides.append({'index':ordinal,'role':'keyframe','seconds':0 if key=='first' else duration-1/24})
    if command['mode']=='extension':
        from .video_extension import CONTEXT_FRAMES
        anchor_index=command['clip']-1
        context={'side':command['side'],'paths':[Path(p).relative_to(app.data).as_posix() for p in extract_frames(app,value,anchor_index,command['side']=='after',CONTEXT_FRAMES,folder/'context',cancel,stage,log)]}
    if command['audio']:refs.append(command['audio'])
    if cancel.is_set():raise Cancelled()
    model=app.engine.require_model(settings['video_model'],'video')
    if command['audio']:
        from .soundtrack import probe
        if probe(app.engine,app.data,command['audio'],cancel,stage,log)['duration']+1e-6<command['audio_start']+duration:raise ValueError('La guida audio è più corta dell’intervallo della nuova clip.')
    plan,_=app.engine.refine_video([],command['prompt'],refs,model,settings,cancel,log,stage)
    by_index={g['index']:g for g in guides}
    plan['images']=[by_index.get(i,{'index':i,'role':'reference','seconds':0}) for i,_ in enumerate([r for r in refs if r['mime'].startswith('image/')],1)]
    plan['audios']=[{'index':1,'role':'lipsync' if command['lip_sync'] else 'reuse','start':command['audio_start']}] if command['audio'] else []
    plan=validate_plan(plan,refs,duration)
    width,height=dimensions(value,command['clip']-1)
    ratio=f'{width//math.gcd(width,height)}:{height//math.gcd(width,height)}'
    canvas=resolve_canvas(options(model,settings,False),{'images':[]},[],ratio)
    canvas={k:canvas[k] for k in ('width','height','output_width','output_height','aspect','aspect_source','format_image')}
    scoped={'duration':duration,'frames':duration*24,'index':0,'sequence':job['id'],'canvas':canvas,'continuity':'cut','last':False}
    if context:scoped['extension_context']=context
    item=app.engine.generate_video(model,settings,plan,refs,job['id']+'/inserted',cancel,stage,prompt=command['prompt'],scene=scoped)
    # Fit only the newly generated clip to the existing timeline's dimensions.
    fitted=folder/'inserted.mp4'
    app.engine.tool_call('video-clip-worker.py',{'source':str(safe_join(app.data,item['path'])),'output':str(fitted),
        'frames':duration*24,'width':width,'height':height},cancel,stage,log,timeout=1800)
    generated_path=item['path'];item=copy.deepcopy(item);item['path']=fitted.relative_to(app.data).as_posix()
    item['generation'].update(width=width,height=height,insert_mode=command['mode'],timeline_label='Clip aggiunta')
    if item.get('batch_variants'):
        for n,take in enumerate(item['batch_variants']):
            if not n:take['path']=item['path']
            else:
                variant_fitted=folder/f'inserted-variant-{n+1:03d}.mp4'
                app.engine.tool_call('video-clip-worker.py',{'source':str(safe_join(app.data,take['path'])),'output':str(variant_fitted),'frames':duration*24,'width':width,'height':height},cancel,stage,log,timeout=1800)
                take['path']=variant_fitted.relative_to(app.data).as_posix()
            take['generation'].update(width=width,height=height)
    cut=sum(s['frames'] for s in value['record']['timeline'][:index])/24
    audio_path=folder/'timeline-audio.wav'
    app.engine.tool_call('video-extension-worker.py',{'op':'audio','original':str(safe_join(app.data,value['audio']['path'])),
        'new':str(safe_join(app.data,command['audio']['path'] if command['audio'] else generated_path)),
        'output':str(audio_path),'new_start':command['audio_start'] if command['audio'] else 0,'audio_start':value['record'].get('audio_start',0),'cut':cut,'total':value['duration'],'duration':duration},cancel,stage,log,timeout=1800)
    audio={'id':uuid4().hex,'name':'Audio della timeline estesa.wav','mime':'audio/wav','path':audio_path.relative_to(app.data).as_posix()}
    images=[r for r in value['refs'] if r['mime'].startswith('image/')]
    for r in refs:
        if r['mime'].startswith('image/') and not any(m['id']==r['id'] for m in images):images.append(r)
    audios=[audio if r['id']==value['audio']['id'] else r for r in value['refs'] if r['mime'].startswith('audio/')]
    all_refs=images+audios;record=inserted_record(value['record'],item,plan,index,duration,all_refs,refs,audio,model['id'])
    from .video_batch import register
    register(record,index,item,all_refs)
    record.update(extension_source=command['source'],extension=command,extension_context=context)
    if context:record['timeline'][index]['extension_context']=context
    save(folder,record);app.store.gallery.register([audio])
    from .video_import import prepare
    prepare(app,value|{'record':record},cancel,stage,log);save(folder,record)
    from .soundtrack import compose
    result=compose(app.engine,[safe_join(app.data,p) for p in record['outputs']],audio_path,folder/'video.mp4',cancel,stage,log,audio_duration=value['duration']+duration)
    from .video_batch import compose_branches
    compose_branches(app.engine,record,folder,audio,cancel,stage,log,0,value['duration']+duration)
    parameters=item['generation']|{'duration':result['duration'],'scenes':len(record['timeline']),'scene_parameters':record['parameters'],
        'engine':'minimax-h3','audio_preserved':True,'audio_start':0,'post_edit':True,'inserted_clip':index+1,'extension_source':command['source']}
    if record.get('batch_movies'):parameters['batch_movies']=record['batch_movies']
    media={'id':job['id'],'name':'Video · clip aggiunta.mp4','path':(folder/'video.mp4').relative_to(app.data).as_posix(),'mime':'video/mp4','generation':parameters}
    app.store.update_answer(job,f"Ho aggiunto una clip di {duration} secondi {'dopo' if command['side']=='after' else 'prima'} della clip {command['clip']}. Le scene esistenti sono conservate; puoi continuare a modificare la nuova timeline.",'done',[media],
        {'intent':'video','references':all_refs,'video_plan':record['plan'],'video_parameters':parameters,'execution_mode':'Standalone · GPU · inserimento clip'})
    app.store.execute("UPDATE jobs SET status='done',stage='Video esteso pronto' WHERE id=?",(job['id'],))

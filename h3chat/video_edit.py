"""Queued replacement of selected saved MiniMax clips, with a new full montage."""
import copy
import json
import math
import re
from .downloads import Cancelled, safe_join
from .video_resume import checkpoint, save
from .video_options import validate_plan


def source(app, chat_id, ident):
    app.store.chat(chat_id)
    if not isinstance(ident,str) or not re.fullmatch(r'[a-f0-9]{32}',ident):
        raise ValueError('Video da modificare non valido.')
    row=app.store.one("SELECT j.payload,m.meta FROM jobs j JOIN messages m ON m.id=j.message_id WHERE j.id=? AND j.chat_id=? AND j.status='done' AND m.status='done'",(ident,chat_id))
    if not row:raise ValueError('Scegli un video completato di questa chat.')
    record=checkpoint(app.data,ident)
    if record['completed']!=len(record['timeline']):raise ValueError('Il video contiene clip incompleti.')
    payload=json.loads(row['payload']);meta=json.loads(row['meta'])
    refs=meta.get('references',payload['media'])
    images=[r for r in refs if r['mime'].startswith('image/')]
    audios=[r for r in refs if r['mime'].startswith('audio/')]
    track=next((a for a in record['plan']['audios'] if a['role'] in ('reuse','lipsync')),None)
    if not track or not 1<=track['index']<=len(audios):raise ValueError('La canzone originale non è disponibile.')
    for item in refs:
        if not safe_join(app.data,item['path']).is_file():raise ValueError('Un riferimento originale non è più disponibile.')
    cursor=0
    for i,scene in enumerate(record['timeline']):
        start=scene.get('start');duration=scene.get('duration');frames=scene.get('frames')
        if type(start) not in (int,float) or not math.isfinite(start) or abs(start-cursor)>1/24 or type(duration) not in (int,float) or not math.isfinite(duration) or not 0<duration<=15 or type(frames) is not int or not 1<=frames<=360 or abs(duration-frames/24)>1e-6:
            raise ValueError('Tempi dei clip salvati non validi.')
        scene['index']=i;cursor=start+duration
    duration=meta.get('video_parameters',{}).get('duration',cursor)
    if type(duration) not in (int,float) or not math.isfinite(duration) or abs(cursor-duration)>1/24+1e-6:
        raise ValueError('La durata salvata non coincide con i clip.')
    return {'record':record,'payload':payload,'meta':meta,'refs':refs,'images':images,'audio':audios[track['index']-1],'duration':duration}


def describe(app,chat_id,ident):
    value=source(app,chat_id,ident);record=value['record']
    return {'source':ident,'duration':value['duration'],
        'images':[{'index':i,'id':r['id'],'name':r['name'],'url':'/media/'+r['path']} for i,r in enumerate(value['images'],1)],
        'clips':[{'clip':i+1,'start':s['start'],'end':s['start']+s['duration'],
            'url':'/media/'+record['outputs'][i],'prompt':record['prompts'][i],
            'images':[x['index'] for x in s.get('images',record['plan']['images'])],
            'lip_sync':s.get('lip_sync',any(a['role']=='lipsync' for a in record['plan']['audios']))}
            for i,s in enumerate(record['timeline'])]}


def validate_edits(patches,value):
    if not isinstance(patches,list) or not 1<=len(patches)<=len(value['record']['timeline']):
        raise ValueError('Seleziona almeno un clip da modificare.')
    result=[];seen=set()
    for item in patches:
        if not isinstance(item,dict) or set(item)-{'clip','prompt','images','lip_sync'}:
            raise ValueError('Modifica clip non valida.')
        clip=item.get('clip');prompt=item.get('prompt');lip=item.get('lip_sync',False)
        if type(clip) is not int or not 1<=clip<=len(value['record']['timeline']) or clip in seen:
            raise ValueError('Numero del clip non valido o ripetuto.')
        if not isinstance(prompt,str) or not prompt.strip() or len(prompt)>6000:
            raise ValueError('Scrivi le modifiche del clip, fino a 6.000 caratteri.')
        if type(lip) is not bool:raise ValueError('Lip-sync: scegli On oppure Off.')
        scene=value['record']['timeline'][clip-1]
        images=item.get('images',[x['index'] for x in scene.get('images',value['record']['plan']['images'])])
        if not isinstance(images,list) or len(images)>9 or any(type(n) is not int or not 1<=n<=len(value['images']) for n in images) or len(set(images))!=len(images):
            raise ValueError('Scegli fino a nove riferimenti validi per il clip.')
        if any(int(n) not in images for n in re.findall(r'<Picture\s+(\d+)>',prompt,re.I)):
            raise ValueError('Il prompt cita una Picture non selezionata per il clip.')
        seen.add(clip);result.append({'clip':clip,'prompt':prompt.strip(),'images':images,'lip_sync':lip})
    return sorted(result,key=lambda x:x['clip'])


def request(app,chat_id,body):
    value=source(app,chat_id,body.get('source'))
    extra=app.validate_media(body.get('media',[]),canvas=True)
    if len(extra)>9 or any(not r['mime'].startswith('image/') for r in extra):raise ValueError('Aggiungi fino a nove nuove immagini.')
    known={r['id'] for r in value['refs']}
    extra=[r for r in extra if r['id'] not in known]
    value['images']+=extra
    patches=validate_edits(body.get('patches'),value)
    assistant=body.get('assistant',True)
    if type(assistant) is not bool:raise ValueError('Assistant: scegli On oppure Off.')
    canvas=body.get('canvas',value['payload'].get('canvas',False))
    if type(canvas) is not bool:raise ValueError('Destinazione canvas non valida.')
    settings=app.validate_settings({})
    settings['video_model']=value['record']['model']
    model=app.engine.require_model(settings['video_model'],'video')
    if model.get('remote_media'):raise ValueError('Modifica clip richiede MiniMax H3 standalone.')
    if assistant:app.engine.require_model(settings['chat_model'],'chat')
    settings.update(_video=True,_assistant=assistant,_rag=False,
        _video_quality=value['payload']['settings'].get('_video_quality','high'),
        _video_edit={'source':body['source'],'patches':patches,'extra':extra})
    prompt='Post-produzione video · clip '+', '.join(str(x['clip']) for x in patches)+'\n'+'\n'.join(f"Clip {x['clip']}: {x['prompt']}" for x in patches)
    if len(prompt)>24000:raise ValueError('Le modifiche insieme superano 24.000 caratteri.')
    refs=value['images']+[r for r in value['refs'] if not r['mime'].startswith('image/')]
    ident=app.store.enqueue(chat_id,prompt,refs,settings,canvas)
    app.wake.set()
    return {'job_id':ident,'canvas':canvas}


def render(app,job,payload,settings,cancel,stage,log):
    edit=settings['_video_edit'];value=source(app,job['chat_id'],edit['source'])
    value['images']+=edit.get('extra',[])
    patches=validate_edits(edit['patches'],value)
    refs=value['images']+[r for r in value['refs'] if not r['mime'].startswith('image/')]
    model=app.engine.require_model(settings['video_model'],'video')
    if model.get('remote_media'):raise ValueError('Modifica clip richiede MiniMax H3 standalone.')
    from .soundtrack import probe,compose
    from .video_timeline import validate_audio_interval
    info=probe(app.engine,app.data,value['audio'],cancel,stage,log)
    original=value['record'];audio_start=original.get('audio_start',0)
    for patch in patches:
        scene=original['timeline'][patch['clip']-1]
        validate_audio_interval(info['duration'],audio_start+scene['start'],scene['duration'],tail=patch['clip']==len(original['timeline']))
    folder=app.data/'outputs'/job['id'];folder.mkdir(parents=True,exist_ok=True)
    record=copy.deepcopy(original)
    record.update(revision_source=edit['source'],revision_request=patches,revision_completed=[],revision_plans={})
    if settings.get('_video_resume'):
        resumed=checkpoint(app.data,settings['_video_resume'])
        if resumed.get('revision_source')!=edit['source'] or resumed.get('revision_request')!=patches:
            raise ValueError('Le modifiche da recuperare non coincidono con questa richiesta.')
        record=resumed
    # Prepare all edits before loading the video model, keeping one batch of GPU work.
    for patch in patches:
        number=patch['clip'];key=str(number);scene=record['timeline'][number-1]
        if key in record['revision_plans']:continue
        if cancel.is_set():raise Cancelled()
        chosen=[value['images'][n-1] for n in patch['images']]
        mapping={n:i for i,n in enumerate(patch['images'],1)}
        change=re.sub(r'<Picture\s+(\d+)>',lambda m:f'<Picture {mapping[int(m[1])]}>',patch['prompt'],flags=re.I)
        inventory='\n'.join(f'<Picture {i}>: {r["name"]}, identity/environment reference.' for i,r in enumerate(chosen,1))
        prior=re.sub(r'<Picture\s+\d+>','the original visual reference',original['prompts'][number-1],flags=re.I)
        context=f'Original scene, for context only: {prior}\n' if settings.get('_assistant',True) else ''
        instruction=(f'Replace ONLY this {scene["duration"]:g}-second generation clip, global film interval {scene["start"]:g}–{scene["start"]+scene["duration"]:g} seconds. '
            'All narrative timestamps must be LOCAL, beginning at 00:00. Keep the original cinematic style, cast identity and wardrobe. '
            'The requested changes override the old framing and camera cuts. Do not repeat the film opening or add a finale.\n'
            f'{context}REQUESTED CHANGES: {change}\n'
            f'{inventory}\nUse <Audio 1> as the original continuous soundtrack, unchanged. '
            +('Synchronize the visible singer mouth to the ORIGINAL supplied vocals. No new singing, dialogue or rewritten lyrics.' if patch['lip_sync'] else 'No additional voices, dialogue or replacement music.'))
        local_refs=chosen+[value['audio']]
        tuning=settings|{'_video_duration':scene['duration'],'_video_audio_start':audio_start+scene['start']}
        stage(f'Post-produzione · istruzioni clip {number}/{len(record["timeline"])}')
        plan,_=app.engine.refine_video([],instruction,local_refs,model,tuning,cancel,log,stage)
        # Reference identity, exact audio offset and lip-sync are explicit UI contracts.
        plan['images']=[{'index':i,'role':'reference','seconds':0} for i in range(1,len(chosen)+1)]
        plan['audios']=[{'index':1,'role':'lipsync' if patch['lip_sync'] else 'reuse','start':audio_start+scene['start']}]
        plan=validate_plan(plan,local_refs,scene['duration'])
        record['revision_plans'][key]=plan
    save(folder,record)
    for patch in patches:
        number=patch['clip']
        if number in record['revision_completed']:continue
        if cancel.is_set():raise Cancelled()
        scene=record['timeline'][number-1];p=original['parameters'][number-1]
        canvas={'width':p.get('canvas_width',math.ceil(p['width']/32)*32),'height':p.get('canvas_height',math.ceil(p['height']/32)*32),
            'output_width':p['width'],'output_height':p['height'],'aspect':p['aspect'],'aspect_source':p.get('aspect_source','saved'),'format_image':None}
        scoped=scene|{'sequence':job['id'],'scene_index':number-1,'index':number-1,'continuity':'cut','canvas':canvas,'last':number==len(record['timeline'])}
        chosen=[value['images'][n-1] for n in patch['images']]+[value['audio']]
        plan=record['revision_plans'][str(number)]
        def report(label):stage(f'Post-produzione · clip {number}/{len(record["timeline"])} · '+label)
        item=app.engine.generate_video(model,settings,plan,chosen,job['id']+f'/scene-{number:03d}',cancel,report,prompt=plan['prompt'],scene=scoped)
        record['outputs'][number-1]=item['path'];record['parameters'][number-1]=item['generation']
        def global_picture(match):return f"<Picture {patch['images'][int(match[1])-1]}>"
        description=re.sub(r'<Picture\s+(\d+)>',global_picture,plan['prompt'],flags=re.I)
        record['prompts'][number-1]=description
        scene.update(prompt=description,images=[{'index':n,'role':'reference'} for n in patch['images']],lip_sync=patch['lip_sync'],continuity='cut')
        if record.get('storyboard'):record['storyboard']['shots'][number-1]=copy.deepcopy(scene)
        record['revision_completed'].append(number);save(folder,record)
    stage('Post-produzione · montaggio della nuova versione')
    result=compose(app.engine,[safe_join(app.data,p) for p in record['outputs']],safe_join(app.data,value['audio']['path']),folder/'video.mp4',cancel,stage,log,audio_start=audio_start,audio_duration=value['duration'])
    parameters=value['meta'].get('video_parameters',{})|{'duration':result['duration'],'scene_parameters':record['parameters'],
        'scenes':len(record['timeline']),'audio_preserved':True,'audio_start':audio_start,'post_edit':True,
        'revision_source':edit['source'],'replaced_clips':[p['clip'] for p in patches],'reused_clips':len(record['timeline'])-len(patches)}
    if record.get('storyboard'):parameters['storyboard']=record['storyboard']
    media={'id':job['id'],'name':'Video MiniMax H3 · nuova versione.mp4','mime':'video/mp4','path':(folder/'video.mp4').relative_to(app.data).as_posix(),'generation':parameters}
    meta={'intent':'video','canvas':bool(payload.get('canvas')),'model':model['name'],'execution_mode':'Standalone · GPU · post-produzione',
        'assistant_on':settings.get('_assistant',True),'references':refs,'video_plan':record['plan'],'video_parameters':parameters}
    if payload.get('canvas'):
        app.save_artifact(job['chat_id'],'Video · nuova versione','',[media]);meta['artifact']={'title':'Video · nuova versione','content':'','media':[media]}
    app.store.update_answer(job,'Ho creato una nuova versione sostituendo i clip '+', '.join(str(p['clip']) for p in patches)+'. La canzone resta continua.','done',[] if payload.get('canvas') else [media],meta)
    app.store.execute("UPDATE jobs SET status='done',stage='Video aggiornato' WHERE id=?",(job['id'],))

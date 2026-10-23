"""Queued MiniMax clip edits, optionally reassembled into the source video."""
import copy
import json
import math
import re
from .store import uid
from .downloads import Cancelled, safe_join
from .video_resume import checkpoint, save
from .video_options import validate_plan, validate_steps, validate, DEFAULTS, options, resolve_canvas


def model_choices(app):
    settings=app.store.settings()
    return [{'id':m['id'],'name':m['name'],'parameters':validate(settings.get('video_overrides',{}).get(m['id'],{}))}
        for m in app.catalog.values() if 'video' in m.get('capabilities',[]) and not m.get('remote_media') and m.get('ready')]


def source(app, chat_id, ident,segment_seconds=None,*,import_layout_version=2):
    if segment_seconds is not None:
        from .video_import import segment_length
        segment_length(segment_seconds)
    app.store.chat(chat_id)
    if not isinstance(ident,str) or not re.fullmatch(r'[a-f0-9]{32}',ident):
        raise ValueError('Video da modificare non valido.')
    row=app.store.one("SELECT j.payload,j.status,m.meta FROM jobs j JOIN messages m ON m.id=j.message_id WHERE j.id=? AND j.chat_id=? AND m.chat_id=? AND j.status IN ('done','cancelled','failed','interrupted')",(ident,chat_id,chat_id))
    if not row or not (app.data/'outputs'/ident/'scenes.json').is_file():
        from .video_import import source as imported_source
        return imported_source(app,ident,15 if segment_seconds is None else segment_seconds,layout_version=import_layout_version)
    record=checkpoint(app.data,ident)
    if row['status']!='done' and not record.get('working_timeline'):
        raise ValueError('Questa generazione è incompleta: usa Riprendi clip mancanti per completarla.')
    if record.get('revision_remount') is False and not record.get('working_timeline'):
        raise ValueError('Scegli lo spezzone generato dalla chat o dalla galleria, non il lavoro completo.')
    if record['completed']!=len(record['timeline']):raise ValueError('Il video contiene clip incompleti.')
    payload=json.loads(row['payload']);meta=json.loads(row['meta'])
    refs=meta.get('references',payload['media'])
    images=[r for r in refs if r['mime'].startswith('image/')]
    audios=[r for r in refs if r['mime'].startswith('audio/')]
    track=next((a for a in record['plan']['audios'] if a['role'] in ('reuse','lipsync')),None)
    if not track:
        # Older storyboard jobs preserved an exact master during composition
        # but left the preliminary plan's audio role at "reference". Recover
        # only the explicitly saved soundtrack identity, never a guessed file.
        master=record.get('request_context',{}).get('settings',{}).get('_video_soundtrack',{})
        ordinal=next((i for i,a in enumerate(audios,1) if a['id']==master.get('id')),None)
        if ordinal is not None:
            track=next((a for a in record['plan']['audios'] if a['index']==ordinal),None)
            if track is not None:track.update(role='reuse',start=record.get('audio_start',0))
    if not track or not 1<=track['index']<=len(audios):raise ValueError('La canzone originale non è disponibile.')
    for item in refs:
        if not safe_join(app.data,item['path']).is_file():raise ValueError('Un riferimento originale non è più disponibile.')
    cursor=0
    for i,scene in enumerate(record['timeline']):
        start=scene.get('start');duration=scene.get('duration');frames=scene.get('frames')
        if type(start) not in (int,float) or not math.isfinite(start) or abs(start-cursor)>1/24 or type(duration) not in (int,float) or not math.isfinite(duration) or not 0<duration<=15 or type(frames) is not int or not 1<=frames<=360 or abs(duration-frames/24)>1e-6:
            raise ValueError('Tempi dei clip salvati non validi.')
        scene['index']=i;cursor=start+duration
    duration=cursor if record.get('working_timeline') else meta.get('video_parameters',{}).get('duration',cursor)
    if type(duration) not in (int,float) or not math.isfinite(duration) or abs(cursor-duration)>1/24+1e-6:
        raise ValueError('La durata salvata non coincide con i clip.')
    return {'record':record,'payload':payload,'meta':meta,'refs':refs,'images':images,'audio':audios[track['index']-1],'duration':duration,'source_size':record.get('imported_size')}


def clip_source(value,index):
    record=value['record'];sources=record.get('clip_sources')
    if sources is not None:
        return sources[index] or {'path':record['outputs'][index],'start':0}
    if value.get('imported'):return {'path':value['imported']['path'],'start':record['timeline'][index]['start']}
    return {'path':record['outputs'][index],'start':0}


def resplit_origin(app,chat_id,ident,value):
    """Find an imported original without carrying edited timeline boundaries."""
    if value.get('imported'):return ident
    record=value['record'];seen={ident}
    for _ in range(64):
        parent=record.get('revision_source')
        if not isinstance(parent,str) or not re.fullmatch(r'[a-f0-9]{32}',parent) or parent in seen:return None
        seen.add(parent)
        row=app.store.one("SELECT j.id FROM jobs j JOIN messages m ON m.id=j.message_id WHERE j.id=? AND j.chat_id=? AND j.status='done' AND m.status='done'",(parent,chat_id))
        if row:
            try:record=checkpoint(app.data,parent)
            except (ValueError,OSError):return None
            continue
        try:
            item=app.store.gallery.get(parent)
            if item['mime'].startswith('video/') and safe_join(app.data,item['path']).is_file():return parent
        except (ValueError,OSError,KeyError):pass
        return None
    return None


def describe(app,chat_id,ident,segment_seconds=None):
    value=source(app,chat_id,ident,segment_seconds);record=value['record']
    from . import video_versions
    video_versions.catalog(app,chat_id,ident,value)
    from .video_editor_drafts import load as load_editor_draft
    draft_error=''
    try:editor_draft=load_editor_draft(app,chat_id,ident,value)
    except ValueError as exc:editor_draft=None;draft_error=str(exc)
    from .video_loras import choices
    from .video_editor_launch import load as load_last_launch
    from .video_edit_memory import describe as describe_memory
    return {'source':ident,'model_id':record['model'],'models':model_choices(app),'loras':choices(app),'duration':value['duration'],'partial_edit':True,
        'last_launch':load_last_launch(app,chat_id,ident,value),'launch_settings':True,'batch_variants':'variants' in DEFAULTS,
        'batch_requested':record.get('batch_requested',1),'batch_mode':record.get('batch_mode','clip'),'batch_id':record.get('batch_id'),
        'batch_movies':[{'variant_index':m['variant_index'],'url':'/media/'+m['path']} for m in record.get('batch_movies',[])],
        'preview_audio':{'url':'/media/'+value['audio']['path'],'start':record.get('audio_start',0)},
        'attention_choices':True,'draft_supported':True,'editor_draft':editor_draft,'draft_error':draft_error,'clip_tools':True,'memory_recovery':True,'end_frame_recovery':True,
        'extension_modes':['extension','clip','frames'],
        'anchor_edit_model':app.store.settings().get('edit_model',''),
        'anchor_edit_models':[{'id':m['id'],'name':m['name'],'max_refs':m.get('max_refs',1)} for m in app.catalog.values() if 'edit' in m.get('capabilities',[]) and m.get('ready')],
        'imported':bool(value.get('imported')), 'working_timeline':bool(record.get('working_timeline')),
        'resplit_source':resplit_origin(app,chat_id,ident,value),
        'segment_seconds':record.get('import_segment_seconds'),
        'import_layout_version':record.get('import_layout_version',1),
        'edited_clips':record.get('edited_clips',[]),
        'images':[{'index':i,'id':r['id'],'name':r['name'],'url':'/media/'+r['path']} for i,r in enumerate(value['images'],1)],
        'clips':[{'clip':i+1,'start':s['start'],'end':s['start']+s['duration'],'edited':i+1 in record.get('edited_clips',[]),
            'url':'/media/'+clip_source(value,i)['path'],'preview_start':clip_source(value,i)['start'],
            'versions':video_versions.describe(value,i),'selected_version':record['selected_versions'][str(i+1)],
            'source_interval':bool(record.get('clip_sources',[None]*len(record['timeline']))[i]) or bool(value.get('imported')),'prompt':record['prompts'][i],
            'images':[x['index'] for x in s.get('images',record['plan']['images'])],
            'mode':s.get('generation_mode','reference'),
            'memory':describe_memory(record,i),
            'start_image':next((x['index'] for x in s.get('images',[]) if x['role']=='keyframe'),None),
            'lip_sync':s.get('lip_sync',any(a['role']=='lipsync' for a in record['plan']['audios']))}
            for i,s in enumerate(record['timeline'])]}


def validate_edits(patches,value):
    if not isinstance(patches,list) or not 1<=len(patches)<=len(value['record']['timeline']):
        raise ValueError('Seleziona almeno un clip da modificare.')
    result=[];seen=set()
    for item in patches:
        if not isinstance(item,dict) or set(item)-{'clip','prompt','images','lip_sync','audio_guide','start','end','mode','start_image','reference_megapixels','anchors','anchor_image','anchor_images','auto_anchors','anchor_edit_model','recover_memory','end_frame'}:
            raise ValueError('Modifica clip non valida.')
        clip=item.get('clip');prompt=item.get('prompt');lip=item.get('lip_sync',False)
        if type(clip) is not int or not 1<=clip<=len(value['record']['timeline']) or clip in seen:
            raise ValueError('Numero del clip non valido o ripetuto.')
        if not isinstance(prompt,str) or not prompt.strip() or len(prompt)>6000:
            raise ValueError('Scrivi le modifiche del clip, fino a 6.000 caratteri.')
        if type(lip) is not bool:raise ValueError('Lip-sync: scegli On oppure Off.')
        audio_guide=item.get('audio_guide',True)
        if type(audio_guide) is not bool:raise ValueError('Guida audio: scegli On oppure Off.')
        if lip and not audio_guide:raise ValueError('Il lip-sync richiede la guida audio.')
        mode=item.get('mode','reference')
        if mode not in ('reference','i2v','video'):raise ValueError('Modalità clip: scegli Modifica video, Rigenera o I2V.')
        if mode!='video' and 'reference_megapixels' in item:raise ValueError('Il dettaglio sorgente richiede Modifica video.')
        auto=item.get('auto_anchors',False);editor=item.get('anchor_edit_model')
        if type(auto) is not bool or (auto and mode!='video'):
            raise ValueError('Modifica automatica dei fotogrammi: disponibile soltanto in Modifica video.')
        if editor is not None and (not auto or not isinstance(editor,str) or not 1<=len(editor)<=100):
            raise ValueError('Scegli un modello immagini valido per modificare i fotogrammi.')
        anchors=item.get('anchors','three' if auto else 'none');anchor_image=item.get('anchor_image')
        anchor_images=item.get('anchor_images',{})
        if auto and (anchors=='none' or anchor_image is not None or anchor_images):
            raise ValueError('Le guide automatiche richiedono fotogrammi attivi e non usano immagini guida manuali.')
        allowed={'first'} if anchors=='first' else {'first','last'} if anchors=='ends' else {'first','middle','last'} if anchors=='three' else set()
        if anchors not in ('none','first','ends','three') or (mode!='video' and (anchors!='none' or anchor_image is not None or anchor_images)):
            raise ValueError('L’ancoraggio della sorgente richiede Modifica video.')
        if anchor_image is not None and (anchors=='none' or type(anchor_image) is not int or not 1<=anchor_image<=len(value['images'])):
            raise ValueError('Scegli un fotogramma iniziale modificato valido.')
        if not isinstance(anchor_images,dict) or set(anchor_images)-allowed or any(type(n) is not int or not 1<=n<=len(value['images']) for n in anchor_images.values()):
            raise ValueError('Scegli immagini valide per i fotogrammi inizio, metà e fine.')
        if anchor_image is not None:
            if 'first' in anchor_images and anchor_images['first']!=anchor_image:raise ValueError('Fotogramma iniziale ripetuto con immagini diverse.')
            anchor_images=dict(anchor_images,first=anchor_image)
        if len(set(anchor_images.values()))!=len(anchor_images):raise ValueError('Usa un’immagine distinta per ogni momento del tratto.')
        guide=item.get('start_image')
        if mode=='i2v':
            if type(guide) is not int or not 1<=guide<=len(value['images']):raise ValueError('I2V: scegli un’immagine iniziale per il tratto da generare.')
            if 'images' in item and item['images'] not in ([],[guide]):raise ValueError('I2V usa soltanto l’immagine iniziale; gli altri riferimenti non sono selezionati.')
            # In I2V there is one image; accept its intuitive local Picture 1
            # label and store the canonical film-wide ordinal for replay.
            if guide!=1:prompt=re.sub(r'<Picture\s+1>',f'<Picture {guide}>',prompt,flags=re.I)
        elif guide is not None:raise ValueError('Il fotogramma iniziale richiede la modalità I2V.')
        scene=value['record']['timeline'][clip-1]
        images=[guide] if mode=='i2v' else item.get('images',[] if mode=='video' else [x['index'] for x in scene.get('images',value['record']['plan']['images'])])
        end_frame=item.get('end_frame','none')
        if type(end_frame) is int and isinstance(images,list) and end_frame not in images:images=[*images,end_frame]
        if isinstance(end_frame,str) and end_frame in ('original','next') and isinstance(images,list) and len(images)>=9:
            raise ValueError('Il fotogramma finale richiede uno dei nove posti immagine: riduci i riferimenti selezionati.')
        if isinstance(images,list):images=list(anchor_images.values())+[n for n in images if n not in anchor_images.values()]
        if not isinstance(images,list) or len(images)>9 or any(type(n) is not int or not 1<=n<=len(value['images']) for n in images) or len(set(images))!=len(images):
            raise ValueError('Scegli fino a nove riferimenti validi per il clip.')
        prompt=re.sub(r'(?<!<)\b(?:immagine|image|picture|foto)\s+(\d+)\b',lambda m:f'<Picture {int(m[1])}>' if int(m[1]) in images else m[0],prompt,flags=re.I)
        if any(int(n) not in images for n in re.findall(r'<Picture\s+(\d+)>',prompt,re.I)):
            raise ValueError('Il prompt cita una Picture non selezionata per il clip.')
        span={}
        if 'start' in item or 'end' in item:
            start=item.get('start');end=item.get('end')
            if any(type(n) not in (int,float) or not math.isfinite(n) for n in (start,end)) or not 0<=start<end<=scene['duration']+1e-6:
                raise ValueError('Indica inizio e fine del tratto, entro la durata del clip.')
            first,last=round(start*24),round(end*24)
            if last-first<24 or last>scene['frames']:
                raise ValueError(f'Clip {clip}: seleziona un tratto di almeno un secondo.')
            if first or last!=scene['frames']:span={'start':first/24,'end':last/24}
        if any(mode!='video' or int(n)!=1 for n in re.findall(r'<Video\s+(\d+)>',prompt,re.I)):
            raise ValueError('Il riferimento <Video 1> richiede Modifica video.')
        mode_values={'mode':'i2v','start_image':guide} if mode=='i2v' else {}
        if mode=='video':
            from .video_reference import REFERENCE_MEGAPIXELS,validate_source
            mp=item.get('reference_megapixels',REFERENCE_MEGAPIXELS)
            selected_frames=round(span['end']*24)-round(span['start']*24) if span else scene['frames']
            if not 24<=selected_frames<=360:
                raise ValueError(f'Clip {clip}: il tratto selezionato dura {selected_frames/24:g} secondi. Per Modifica video scegli da 1 a 15 secondi.')
            validate_source({'path':'validated-at-render','start':0,'frames':selected_frames,'megapixels':mp})
            mode_values={'mode':'video','reference_megapixels':mp}
            if anchors!='none':mode_values['anchors']=anchors
            if anchor_image is not None:mode_values['anchor_image']=anchor_image
            if anchor_images:mode_values['anchor_images']=anchor_images
            if auto:
                mode_values['auto_anchors']=True
                if editor is not None:mode_values['anchor_edit_model']=editor
        resolved={'clip':clip,'prompt':prompt.strip(),'images':images,'lip_sync':lip}|({'audio_guide':audio_guide} if 'audio_guide' in item else {})|span|mode_values
        if 'recover_memory' in item:resolved['recover_memory']=item['recover_memory']
        from .video_edit_memory import validate as validate_memory
        validate_memory(resolved,scene,clip-1)
        if resolved.get('recover_memory'):resolved['mode']='reference'
        from .video_edit_end_frame import validate as validate_end_frame
        validate_end_frame(end_frame,resolved,scene,clip-1,len(value['record']['timeline']),len(value['images']))
        if 'end_frame' in item:resolved['end_frame']=end_frame
        if end_frame!='none':resolved['mode']='reference'
        seen.add(clip);result.append(resolved)
    return sorted(result,key=lambda x:x['clip'])


def interval(patch,scene):
    return round(patch.get('start',0)*24),round(patch.get('end',scene['duration'])*24)


def edited_anchors(patch,scene):
    """Image ordinals mapped to interval-local, unpadded source-frame times."""
    first,last=interval(patch,scene);count=last-first
    positions={'first':0,'middle':count//2,'last':count-1}
    images=dict(patch.get('anchor_images',{}))
    if type(patch.get('end_frame')) is int:images['last']=patch['end_frame']
    if patch.get('anchor_image'):images['first']=patch['anchor_image']
    return {image:positions[name]/24 for name,image in images.items()}


def source_interval(value,patch):
    """Use the exact source movie interval, never a previously extracted still."""
    scene=value['record']['timeline'][patch['clip']-1];first,last=interval(patch,scene)
    source=clip_source(value,patch['clip']-1);path=source['path'];start=source['start']+first/24
    from .video_reference import REFERENCE_MEGAPIXELS,validate_source
    return validate_source({'path':path,'start':start,'frames':last-first,
        'megapixels':patch.get('reference_megapixels',REFERENCE_MEGAPIXELS)}|({'anchors':patch['anchors']} if patch.get('anchors','none')!='none' else {}))


def supplied_plans(value,patches,plans):
    """Replay directions against new media without changing explicit edit contracts."""
    if not isinstance(plans,dict) or set(plans)-{str(p['clip']) for p in patches}:
        raise ValueError('Istruzioni salvate: scegli soltanto i clip da modificare.')
    result={}
    for patch in patches:
        key=str(patch['clip'])
        if key not in plans:continue
        if patch.get('auto_anchors'):raise ValueError('Le guide automatiche richiedono nuove istruzioni per i fotogrammi modificati.')
        if patch.get('end_frame','none') in ('original','next'):raise ValueError('Prepara nuove istruzioni per il fotogramma finale estratto dalla timeline.')
        scene=value['record']['timeline'][patch['clip']-1];first,last=interval(patch,scene)
        chosen=[value['images'][n-1] for n in patch['images']]+([value['audio']] if patch.get('audio_guide',True) else [])
        plan=validate_plan(plans[key],chosen,(last-first)/24,source_video=patch.get('mode')=='video')
        anchors=edited_anchors(patch,scene)
        images=[{'index':i,'role':'keyframe' if patch.get('mode')=='i2v' or n in anchors else 'reference','seconds':anchors.get(n,0)} for i,n in enumerate(patch['images'],1)]
        audios=[{'index':1,'role':'lipsync' if patch['lip_sync'] else 'reuse','start':value['record'].get('audio_start',0)+scene['start']+first/24}] if patch.get('audio_guide',True) else []
        if plan['images']!=images or plan['audios']!=audios:
            raise ValueError('Le istruzioni salvate devono rispettare immagini, fotogrammi e intervallo audio selezionati.')
        result[key]=plan
    return result


def request(app,chat_id,body):
    remount=body.get('remount',True)
    if type(remount) is not bool:raise ValueError('Rimonta nel video: scegli attivo oppure disattivo.')
    value=source(app,chat_id,body.get('source'),body.get('segment_seconds'))
    from . import video_versions
    selected_versions=video_versions.choices(app,chat_id,body['source'],value,body.get('versions'))
    video_versions.apply(value,selected_versions,app.data)
    extra=app.validate_media(body.get('media',[]),canvas=True)
    if len(extra)>9 or any(not r['mime'].startswith('image/') for r in extra):raise ValueError('Aggiungi fino a nove nuove immagini.')
    known={r['id'] for r in value['refs']}
    extra=[r for r in extra if r['id'] not in known]
    value['images']+=extra
    patches=validate_edits(body.get('patches'),value)
    if value.get('imported'):
        from .video_import import interval_guide
        for patch in patches:
            scene=value['record']['timeline'][patch['clip']-1]
            if patch.get('mode')=='i2v' and patch.get('start',0)>0 and patch['start_image']==scene['images'][0]['index']:
                guide=interval_guide(app,value,scene,patch['start']);extra.append(guide);value['images'].append(guide)
                index=len(value['images']);old=patch['start_image']
                patch['prompt']=re.sub(r'<Picture\s+(\d+)>',lambda m:f'<Picture {index}>' if int(m[1])==old else m[0],patch['prompt'],flags=re.I)
                patch.update(start_image=index,images=[index])
    assistant=body.get('assistant',True)
    if type(assistant) is not bool:raise ValueError('Assistant: scegli On oppure Off.')
    plans=supplied_plans(value,patches,body.get('plans',{}))
    canvas=body.get('canvas',value['payload'].get('canvas',False))
    if type(canvas) is not bool:raise ValueError('Destinazione canvas non valida.')
    settings=app.validate_settings({})
    selected=body.get('model') or value['record']['model']
    if not isinstance(selected,str):raise ValueError('Selezione modello video non valida.')
    settings['video_model']=selected
    model=app.engine.require_model(settings['video_model'],'video')
    if model.get('remote_media'):raise ValueError('Modifica clip richiede MiniMax H3 standalone.')
    from .video_auto_guides import validate_models
    validate_models(app,patches,settings)
    if assistant and len(plans)!=len(patches):app.engine.require_model(settings['chat_model'],'chat')
    parameters=body.get('parameters',{})
    from .video_recreate import EDITABLE
    if isinstance(parameters,dict):parameters={k:v for k,v in parameters.items() if k!='longtake_enabled'}
    if not isinstance(parameters,dict) or set(parameters)-set(EDITABLE):raise ValueError('Parametri di modifica video non validi.')
    preset=validate(settings.get('video_overrides',{}).get(selected,{})|parameters)
    from .video_loras import aligned,profile
    if aligned(preset['loras']) and any(p.get('mode')!='video' for p in patches):raise ValueError('I LoRA di editing richiedono Modifica video per tutte le clip selezionate.')
    if any(x['weight'] and profile(x['path'])=='character_swap' for x in preset['loras']) and any(not p['images'] for p in patches):raise ValueError('Character Swap: seleziona il riferimento del personaggio in ogni clip.')
    settings['video_overrides']=copy.deepcopy(settings.get('video_overrides',{}))
    settings['video_overrides'][selected]=preset
    settings.update(_video=True,_assistant=assistant,_rag=False,
        _video_quality=value['payload']['settings'].get('_video_quality','high'),
        _video_steps=validate_steps(body.get('video_steps')),
        _video_edit={'source':body['source'],'patches':patches,'extra':extra,'remount':remount,'parameters':parameters,'versions':selected_versions}|({'segment_seconds':value['record']['import_segment_seconds']} if 'import_segment_seconds' in value['record'] else {})|({'plans':plans} if plans else {}))
    prompt='Post-produzione video · '+('rimontaggio' if remount else 'solo spezzoni')+' · clip '+', '.join(str(x['clip']) for x in patches)+'\n'+'\n'.join(f"Clip {x['clip']}"+(f" · tratto {x['start']:g}–{x['end']:g} s" if 'start' in x else '')+f": {x['prompt']}" for x in patches)
    if len(prompt)>24000:raise ValueError('Le modifiche insieme superano 24.000 caratteri.')
    refs=value['images']+[r for r in value['refs'] if not r['mime'].startswith('image/')]
    ident=app.store.enqueue(chat_id,prompt,refs,settings,canvas)
    app.wake.set()
    return {'job_id':ident,'canvas':canvas}


def install_clip(app,value,record,patch,item,generated_path,folder,cancel,stage,log,*,complete=True):
    """Commit an already generated interval to a new timeline, never its source."""
    original=value['record'];number=patch['clip'];scene=record['timeline'][number-1]
    first,last=interval(patch,scene);p={k:v for k,v in original['parameters'][number-1].items() if not k.startswith('variant_') and k not in ('variants','variants_mode')}
    with generated_path.open('rb') as stream:
        if stream.read(12)[4:8]!=b'ftyp':raise ValueError('Il tratto salvato non è un MP4 valido.')
    if 'start' in patch:
        branch=item['generation'].get('variant_index',1)
        merged=folder/f'scene-{number:03d}'/(f'variant-{branch:03d}/edited.mp4' if branch>1 else 'edited.mp4');merged.parent.mkdir(parents=True,exist_ok=True)
        splice=app.engine.tool_call('video-splice-worker.py',{'original':str(safe_join(app.data,original['outputs'][number-1])),
            'replacement':str(generated_path),'output':str(merged),'start_frame':first,'end_frame':last,'total_frames':scene['frames']},cancel,stage,log,timeout=600)
        if splice['frames']!=scene['frames']:raise ValueError('Il montaggio ha cambiato la durata del clip.')
        record['outputs'][number-1]=merged.relative_to(app.data).as_posix()
        record['parameters'][number-1]=p|{k:v for k,v in item['generation'].items() if k.startswith('variant_') or k in ('seed','steps','variants','variants_mode')}|{'duration':scene['duration'],'output_frames':scene['frames'],'post_edit_interval':{'start':first/24,'end':last/24,'generation':item['generation']}}
    else:
        record['outputs'][number-1]=item['path'];record['parameters'][number-1]=p|item['generation']
    if record.get('clip_sources') is not None:record['clip_sources'][number-1]=None
    plan=record['revision_plans'][str(number)]
    def global_picture(match):return f"<Picture {patch['images'][int(match[1])-1]}>"
    description=re.sub(r'<Picture\s+(\d+)>',global_picture,plan['prompt'],flags=re.I)
    if 'start' in patch:description=original['prompts'][number-1]+f'\nUPDATED INTERVAL (clip-local {first/24:g}–{last/24:g} seconds; the following direction uses interval-local clocks):\n'+description
    record['prompts'][number-1]=description
    anchors=edited_anchors(patch,scene)
    scene.update(prompt=description,images=[{'index':n,'role':'keyframe' if patch.get('mode')=='i2v' or n in anchors else 'reference','seconds':(first/24+anchors.get(n,0)) if patch.get('mode')=='i2v' or n in anchors else 0} for n in patch['images']],lip_sync=patch['lip_sync'],continuity='continue' if patch.get('recover_memory') else 'cut',generation_mode=patch.get('mode','reference'),recover_memory=bool(patch.get('recover_memory')))
    record.pop('recreate_recipes',None)
    if record.get('storyboard'):record['storyboard']['shots'][number-1]=copy.deepcopy(scene)
    record['edited_clips']=sorted(set(record.get('edited_clips',[]))|{number})
    from .video_versions import remember
    remember(value,record,number-1)
    if complete and number not in record['revision_completed']:record['revision_completed'].append(number)
    save(folder,record)


def install_variants(app,value,record,patch,item,canvas,p,folder,cancel,report,log):
    """Every interval alternative is spliced against the same selected source."""
    takes=item.get('batch_variants',[item]);primary=None;number=patch['clip'];index=number-1
    for ordinal,take in enumerate(takes):
        if cancel.is_set():raise Cancelled()
        take=copy.deepcopy(take);generated_path=safe_join(app.data,take['path'])
        changed_size=(canvas['output_width'],canvas['output_height'])!=(p['width'],p['height'])
        if value.get('source_size') or changed_size:
            suffix=f'-v{ordinal+1:03d}' if ordinal else ''
            fitted=folder/f'fitted-{number:03d}{suffix}.mp4';shape=value.get('source_size') or p
            app.engine.tool_call('video-remix-worker.py',{'op':'fit_video','runtime':{'backend':'cpu','threads':4},'folder':str(folder),
                'source':str(generated_path),'output':str(fitted),'width':shape['width']//2*2,'height':shape['height']//2*2},cancel,report,log,timeout=600)
            generated_path=fitted;take['path']=fitted.relative_to(app.data).as_posix()
            if not value.get('source_size'):take['generation'].update({k:p[k] for k in ('width','height','canvas_width','canvas_height','aspect') if k in p})
        install_clip(app,value,record,patch,take,generated_path,folder,cancel,report,log,complete=len(takes)==1)
        if primary is None:
            primary={k:copy.deepcopy(record[k][index]) for k in ('outputs','parameters','prompts','timeline')}
            primary['selected']=record['selected_versions'][str(number)]
    if len(takes)>1:
        for k in ('outputs','parameters','prompts','timeline'):record[k][index]=primary[k]
        record['selected_versions'][str(number)]=primary['selected']
        if record.get('storyboard'):record['storyboard']['shots'][index]=copy.deepcopy(primary['timeline'])
        record.update(batch_requested=len(takes),batch_mode=takes[0]['generation']['variants_mode'],batch_id=takes[0]['generation'].get('variant_batch_id'))
        if number not in record['revision_completed']:record['revision_completed'].append(number)
        save(folder,record)


def render(app,job,payload,settings,cancel,stage,log):
    edit=settings['_video_edit']
    resumed=checkpoint(app.data,settings['_video_resume']) if settings.get('_video_resume') else None
    settings=settings|{'_video_batch_id':(resumed or {}).get('batch_id') or job['id']}
    # Resuming must retain original frame boundaries, thumbnail identities and
    # source offsets even when the importer has since gained a newer layout.
    layout=resumed.get('import_layout_version',1) if resumed and resumed.get('imported_size') else 2
    value=source(app,job['chat_id'],edit['source'],edit.get('segment_seconds'),import_layout_version=layout)
    from . import video_versions
    selected_versions=video_versions.choices(app,job['chat_id'],edit['source'],value,edit.get('versions'))
    video_versions.apply(value,selected_versions,app.data)
    remount=edit.get('remount',True)
    value['images']+=edit.get('extra',[])
    patches=validate_edits(edit['patches'],value)
    plans=supplied_plans(value,patches,edit.get('plans',{}))
    refs=value['images']+[r for r in value['refs'] if not r['mime'].startswith('image/')]
    model=app.engine.require_model(settings['video_model'],'video')
    if model.get('remote_media'):raise ValueError('Modifica clip richiede MiniMax H3 standalone.')
    from .soundtrack import probe,compose
    from .video_timeline import validate_audio_interval
    from .video_import import repair_import_audio
    repair_import_audio(app,value,cancel,stage,log)
    info=probe(app.engine,app.data,value['audio'],cancel,stage,log)
    original=value['record'];audio_start=original.get('audio_start',0)
    for patch in patches:
        if not patch.get('audio_guide',True):continue
        scene=original['timeline'][patch['clip']-1]
        first,last=interval(patch,scene)
        validate_audio_interval(info['duration'],audio_start+scene['start']+first/24,(last-first)/24,tail=patch['clip']==len(original['timeline']) and last==scene['frames'])
    from .video_import import prepare
    from .video_edit_memory import source_indices as memory_indices
    memory_sources=set()
    for patch in patches:
        if patch.get('recover_memory'):
            anchor,recent=memory_indices(original,patch['clip']-1)
            memory_sources.update([anchor+1,*[i+1 for i in recent]])
    prepare(app,value,cancel,stage,log,clips=sorted(memory_sources|{p['clip'] for p in patches if 'start' in p}))
    folder=app.data/'outputs'/job['id'];folder.mkdir(parents=True,exist_ok=True)
    record=copy.deepcopy(original)
    record.pop('revision_resolved_request',None)
    record['model']=model['id']
    record.update(working_timeline=True,revision_source=edit['source'],revision_request=patches,revision_remount=remount,revision_completed=[],revision_plans={},revision_generated={},revision_exports={},revision_export_errors={},revision_versions=selected_versions,revision_auto_guides={})
    if resumed is not None:
        if resumed.get('revision_source')!=edit['source'] or resumed.get('revision_request')!=patches or resumed.get('revision_remount',True)!=remount or resumed.get('revision_versions',{})!=selected_versions:
            raise ValueError('Le modifiche da recuperare non coincidono con questa richiesta.')
        record=resumed
    from .video_auto_guides import prepare as prepare_guides
    patches=prepare_guides(app,job,value,record,patches,settings,cancel,stage,log,folder)
    from .video_edit_end_frame import prepare as prepare_end_frames
    patches=prepare_end_frames(app,value,record,patches,folder,cancel,stage,log)
    refs=value['images']+[r for r in value['refs'] if not r['mime'].startswith('image/')]
    # Prepare all edits before loading the video model, keeping one batch of GPU work.
    for patch in patches:
        number=patch['clip'];key=str(number);scene=record['timeline'][number-1]
        if key in record['revision_plans']:continue
        if cancel.is_set():raise Cancelled()
        if key in plans:
            stage(f'Post-produzione · istruzioni salvate clip {number}')
            record['revision_plans'][key]=copy.deepcopy(plans[key])
            continue
        chosen=[value['images'][n-1] for n in patch['images']]
        first,last=interval(patch,scene);duration=(last-first)/24;start=scene['start']+first/24
        mapping={n:i for i,n in enumerate(patch['images'],1)}
        change=re.sub(r'<Picture\s+(\d+)>',lambda m:f'<Picture {mapping[int(m[1])]}>',patch['prompt'],flags=re.I)
        i2v=patch.get('mode')=='i2v'
        video_edit=patch.get('mode')=='video'
        anchors=edited_anchors(patch,scene)
        inventory='\n'.join(f'<Picture {i}>: {r["name"]}, '+('EXACT INITIAL FRAME at local 00:00: use its composition and edited appearance.' if i2v else f'EDITED TARGET KEYFRAME at local {anchors[patch["images"][i-1]]:g} seconds: preserve its exact composition and edited appearance at that time.' if patch['images'][i-1] in anchors else 'identity/environment reference.') for i,r in enumerate(chosen,1))
        prior=re.sub(r'<Picture\s+\d+>','the original visual reference',original['prompts'][number-1],flags=re.I)
        context=f'Original scene, for context only: {prior}\n' if settings.get('_assistant',True) and not video_edit else ''
        instruction=(f'Replace ONLY this {duration:g}-second generation interval, global film interval {start:g}–{start+duration:g} seconds. '
            'All narrative timestamps must be LOCAL, beginning at 00:00. Keep the original cinematic style, cast identity and wardrobe. '
            'The requested changes override the old framing and camera cuts. Do not repeat the film opening or add a finale.\n'
            +(f'This replaces only local seconds {first/24:g}–{last/24:g} of the original clip. The surrounding footage stays unchanged; avoid introductory or concluding transitions.\n' if 'start' in patch else '')
            +f'{context}REQUESTED CHANGES: {change}\n'
            +('I2V: Begin from <Picture 1> at the first frame of this generation interval. Preserve its composition, camera position, subjects and lighting, then animate according to the requested motion. Do not use it only as an identity reference. The older scene must not override this supplied first frame.\n' if i2v else '')
            +f'{inventory}\nUse <Audio 1> as the original continuous soundtrack, unchanged. '
            +('Synchronize the visible singer mouth to the ORIGINAL supplied vocals. No new singing, dialogue or rewritten lyrics.' if patch['lip_sync'] else 'No additional voices, dialogue or replacement music.'))
        if video_edit:
            instruction=(f'The target is an edited version of <Video 1>, the actual {duration:g}-second source clip. '
                'Apply ONLY the requested attribute changes. Preserve its original movements, performances, poses, camera, '
                'framing, shot cuts, timing and all unrequested attributes. The request overrides identity/clothing/background '
                'preservation ONLY where explicitly requested. Never invent a new action or a turntable.\n'
                f'REQUESTED CHANGES: {change}\n{inventory}\n'
                'Reference pictures supply only the requested identity, outfit, background or object. '
                'Use <Audio 1> as the original soundtrack unchanged. '+
                ('Preserve original mouth motion synchronized to that soundtrack.' if patch['lip_sync'] else 'No new dialogue or music.'))
            initial=next((n for n,t in anchors.items() if t==0),None)
            if initial is not None:
                label=mapping[initial]
                instruction+=f'\n<Picture {label}> is the EDITED TARGET FIRST FRAME at 00:00. Begin from its composition and appearance, then follow the original actions of <Video 1> in their original chronological order. Do not start at a later source moment.'
            elif patch.get('anchors','none')!='none':
                instruction+='\nBegin from the actual FIRST FRAME of <Video 1>, at source-local 00:00. Follow its original chronological order; do not select a later moment as the opening.'
        if not patch.get('audio_guide',True):
            instruction=re.sub(r'Use <Audio 1>.*', 'No audio is supplied to the model. Preserve the source visual performance; the original soundtrack is applied separately after generation.',instruction,flags=re.S)
        local_refs=chosen+([value['audio']] if patch.get('audio_guide',True) else [])
        tuning=settings|{'_video_duration':duration,'_video_audio_start':audio_start+start,'_video_source':video_edit}
        stage(f'Post-produzione · istruzioni clip {number} · {len(patches)} selezionati')
        plan,_=app.engine.refine_video([],instruction,local_refs,model,tuning,cancel,log,stage)
        if video_edit:
            # Retain the source relationship even if an Assistant drops its label.
            plan['prompt']='SOURCE VIDEO EDIT: The target is an edited version of <Video 1>. Preserve its movements, camera, cuts and timing; change only the requested attributes.\n'+plan['prompt']
        # Reference identity, exact audio offset and lip-sync are explicit UI contracts.
        plan['images']=[{'index':i,'role':'keyframe' if i2v or patch['images'][i-1] in anchors else 'reference','seconds':anchors.get(patch['images'][i-1],0)} for i in range(1,len(chosen)+1)]
        if type(patch.get('end_frame')) is int:
            label=mapping[patch['end_frame']]
            plan['prompt']+=f'\n<Picture {label}> is the requested FINAL FRAME at local {(scene["frames"]-1)/24:g} seconds. Progress naturally toward its composition and pose; do not start from this ending image. The previous visual memory, when supplied, guides the opening.'
        plan['audios']=[{'index':1,'role':'lipsync' if patch['lip_sync'] else 'reuse','start':audio_start+start}] if patch.get('audio_guide',True) else []
        plan=validate_plan(plan,local_refs,duration,source_video=video_edit)
        record['revision_plans'][key]=plan
    save(folder,record)
    for patch in patches:
        number=patch['clip']
        if number in record['revision_completed']:continue
        if cancel.is_set():raise Cancelled()
        scene=record['timeline'][number-1];p=original['parameters'][number-1]
        canvas={'width':p.get('canvas_width',math.ceil(p['width']/32)*32),'height':p.get('canvas_height',math.ceil(p['height']/32)*32),
            'output_width':p['width'],'output_height':p['height'],'aspect':p['aspect'],'aspect_source':p.get('aspect_source','saved'),'format_image':None}
        if 'megapixels' in edit.get('parameters',{}):
            resolved=resolve_canvas(options(model,settings,False),{'images':[]},[],p['aspect'])
            canvas={k:resolved[k] for k in canvas}
        first,last=interval(patch,scene);duration=(last-first)/24
        scoped=scene|{'start':scene['start']+first/24,'duration':duration,'frames':last-first,'sequence':job['id'],'scene_index':number-1,'index':number-1,'continuity':'cut','canvas':canvas,'last':number==len(record['timeline']) and last==scene['frames']}
        if patch.get('mode')=='video':
            scoped['source_video']=source_interval(value,patch)
            if not safe_join(app.data,scoped['source_video']['path']).is_file():raise ValueError('Il video sorgente non è più disponibile.')
        chosen=[value['images'][n-1] for n in patch['images']]+([value['audio']] if patch.get('audio_guide',True) else [])
        plan=record['revision_plans'][str(number)]
        def report(label):stage(f'Post-produzione · clip {number} · modifica {patches.index(patch)+1}/{len(patches)}'+(f' · tratto {first/24:g}–{last/24:g} s' if 'start' in patch else '')+' · '+label)
        generated=record.setdefault('revision_generated',{})
        item=generated.get(str(number))
        if item is None:
            memory_info=None
            if patch.get('recover_memory'):
                from .video_edit_memory import restore as restore_edit_memory
                memory,memory_info=restore_edit_memory(app.data,record,number-1)
                scoped.update(continuity='continue',resume_memory=memory)
                batch=options(model,settings,False)
                if batch['variants']>1:
                    from .video_batch import memory_for
                    scoped['batch_memories']={str(n):memory_for(record,number-1,n,batch['variants_mode'],app.data) for n in range(1,batch['variants']+1)}
                plan=copy.deepcopy(plan)
                plan['prompt']+='\nContinue from the supplied previous ending. Internal visual memory preserves identity, clothing and established props; develop the requested new action instead of replaying earlier actions. Do not copy the opening location if the new direction changes it.'
                report('Recupero memoria precedente · apertura e ultime due clip disponibili')
            item=app.engine.generate_video(model,settings,plan,chosen,job['id']+f'/scene-{number:03d}',cancel,report,prompt=plan['prompt'],scene=scoped)
            item['generation']['audio_guide']=patch.get('audio_guide',True)
            if memory_info:item['generation']['visual_memory_recovered']=memory_info
            generated[str(number)]=item;save(folder,record)
        install_variants(app,value,record,patch,item,canvas,p,folder,cancel,report,log)
        if not remount:
            try:
                exported=export_segment(app,job,value,record,patch,folder,cancel,report,log)
                app.store.gallery.register([exported],chat_id=job['chat_id'])
            except Cancelled:raise
            except (OSError,ValueError,RuntimeError) as exc:
                # Keep all committed footage if a temporary audio/export error
                # occurs. Finalization retries and reports a persistent failure.
                record.setdefault('revision_export_errors',{})[str(number)]=str(exc);save(folder,record)
    if not remount:
        finish_segments(app,job,payload,settings,value,record,patches,refs,model,folder,cancel,stage,log)
        return
    stage('Post-produzione · montaggio della nuova versione')
    prepare(app,value|{'record':record},cancel,stage,log);save(folder,record)
    result=compose(app.engine,[safe_join(app.data,p) for p in record['outputs']],safe_join(app.data,value['audio']['path']),folder/'video.mp4',cancel,stage,log,audio_start=audio_start,audio_duration=value['duration'])
    from .video_batch import compose_branches
    compose_branches(app.engine,record,folder,value['audio'],cancel,stage,log,audio_start,value['duration'])
    parameters=value['meta'].get('video_parameters',{})|{'duration':result['duration'],'scene_parameters':record['parameters'],
        'scenes':len(record['timeline']),'audio_preserved':True,'audio_start':audio_start,'post_edit':True,
        'revision_source':edit['source'],'replaced_clips':[p['clip'] for p in patches],'reused_clips':len(record['timeline'])-len(patches),
        'replaced_intervals':[{'clip':p['clip'],'start':p['start'],'end':p['end']} for p in patches if 'start' in p]}
    for key in ('clip_only','timeline_id','source_intervals','source_interval'):parameters.pop(key,None)
    parameters.update(remount=True,engine='minimax-h3',imported_video=bool(record.get('imported_size')))
    if record.get('batch_requested'):parameters.update(variants=record['batch_requested'],variants_mode=record['batch_mode'])
    if record.get('batch_movies'):parameters['batch_movies']=record['batch_movies']
    if record.get('storyboard'):parameters['storyboard']=record['storyboard']
    parameters['edited_steps']=sorted({record['parameters'][p['clip']-1].get('post_edit_interval',{}).get('generation',record['parameters'][p['clip']-1]).get('steps',12) for p in patches})
    media={'id':job['id'],'name':'Video MiniMax H3 · nuova versione.mp4','mime':'video/mp4','path':(folder/'video.mp4').relative_to(app.data).as_posix(),'generation':parameters}
    meta={'intent':'video','canvas':bool(payload.get('canvas')),'model':model['name'],'execution_mode':'Standalone · GPU · post-produzione',
        'assistant_on':settings.get('_assistant',True),'references':refs,'video_plan':record['plan'],'video_parameters':parameters}
    if edit.get('plans'):meta['assistant_plans_reused']=sorted(int(n) for n in edit['plans'])
    if record.get('revision_auto_guides'):meta['video_auto_guides']=record['revision_auto_guides']
    if payload.get('canvas'):
        app.save_artifact(job['chat_id'],'Video · nuova versione','',[media]);meta['artifact']={'title':'Video · nuova versione','content':'','media':[media]}
    app.store.update_answer(job,'Ho creato una nuova versione sostituendo i clip '+', '.join(str(p['clip']) for p in patches)+'. La canzone resta continua.','done',[] if payload.get('canvas') else [media],meta)
    app.store.execute("UPDATE jobs SET status='done',stage='Video aggiornato' WHERE id=?",(job['id'],))


def export_segment(app,job,value,record,patch,folder,cancel,stage,log):
    """Commit one finished interval and original audio before the next GPU clip."""
    from .soundtrack import compose
    number=patch['clip'];key=str(number);exports=record.setdefault('revision_exports',{})
    cached=exports.get(key)
    if cached and cached.get('generation',{}).get('timeline_id')==job['id'] and safe_join(app.data,cached['path']).is_file():return copy.deepcopy(cached)
    scene=value['record']['timeline'][number-1];first,last=interval(patch,scene);duration=(last-first)/24
    start=scene['start']+first/24;audio_start=value['record'].get('audio_start',0)+start
    item=record['revision_generated'][key];target=folder/f'clip-{number:03d}.mp4'
    stage(f'Post-produzione · audio originale dello spezzone {number}')
    result=compose(app.engine,[safe_join(app.data,item['path'])],safe_join(app.data,value['audio']['path']),target,cancel,stage,log,audio_start=audio_start,audio_duration=duration)
    generation=item['generation']|{'duration':result['duration'],'audio_start':audio_start,'audio_preserved':True,
        'post_edit':True,'remount':False,'clip_only':True,'revision_source':record['revision_source'],'timeline_id':job['id'],
        'source_interval':{'clip':number,'start':start,'end':start+duration}}
    exported={'id':uid(),'name':f'Video MiniMax H3 · spezzone {number}.mp4','mime':'video/mp4',
        'path':target.relative_to(app.data).as_posix(),'generation':generation}
    exports[key]=exported;record.get('revision_export_errors',{}).pop(key,None);save(folder,record)
    return copy.deepcopy(exported)


def interrupted_exports(app,job):
    """Expose only already committed exports; never start composition on Stop."""
    record=checkpoint(app.data,job['id']);ready=set(record.get('revision_completed',[]))
    media=[copy.deepcopy(item) for n,item in record.get('revision_exports',{}).items()
        if n.isdigit() and int(n) in ready and safe_join(app.data,item['path']).is_file()]
    return media,{'video_parameters':{'timeline_id':job['id'],'clip_only':True,'post_edit':True,'remount':False,
        'replaced_clips':sorted(ready),'scenes':len(media)}}


def finish_segments(app,job,payload,settings,value,record,patches,refs,model,folder,cancel,stage,log,*,recovered=False):
    """Return separate generated intervals, with only their original audio slices."""
    media=[];intervals=[]
    for patch in patches:
        if cancel.is_set():raise Cancelled()
        item=export_segment(app,job,value,record,patch,folder,cancel,stage,log)
        media.append(item);intervals.append(item['generation']['source_interval'])
    parameters={'remount':False,'clip_only':True,'audio_preserved':True,'post_edit':True,'timeline_id':job['id'],
        'revision_source':record['revision_source'],'replaced_clips':[p['clip'] for p in patches],
        'reused_clips':0,'duration':sum(m['generation']['duration'] for m in media),'source_intervals':intervals,
        'scene_parameters':[m['generation'] for m in media],'scenes':len(media),
        'edited_steps':sorted({m['generation'].get('steps',12) for m in media})}
    meta={'intent':'video','canvas':bool(payload.get('canvas')),'model':model['name'],
        'execution_mode':'Standalone · CPU · recupero timeline' if recovered else 'Standalone · GPU · solo spezzoni','assistant_on':settings.get('_assistant',True),
        'references':refs,'video_parameters':parameters}
    if settings.get('_video_edit',{}).get('plans'):meta['assistant_plans_reused']=sorted(int(n) for n in settings['_video_edit']['plans'])
    if record.get('revision_auto_guides'):meta['video_auto_guides']=record['revision_auto_guides']
    if payload.get('canvas'):
        title='Video · spezzoni generati';app.save_artifact(job['chat_id'],title,'',media)
        meta['artifact']={'title':title,'content':'','media':media}
    text='Ho recuperato gli spezzoni già generati nella timeline, senza rigenerarli.' if recovered else 'Ho generato '+('lo spezzone richiesto' if len(media)==1 else 'gli spezzoni richiesti, come file separati')+' con il relativo audio originale.'
    app.store.update_answer(job,text+' La timeline aggiornata è salvata: premi Riprendi timeline per modificare altri tratti o montare il video completo.','done',[] if payload.get('canvas') else media,meta)
    app.store.execute("UPDATE jobs SET status='done',stage='Spezzoni pronti' WHERE id=?",(job['id'],))

"""Replay saved MiniMax directions and assets without replanning the film."""
import copy
import json
import math
import re
from .downloads import Cancelled, safe_join
from .video_options import DEFAULTS, ACCELERATION_KEYS, options, resolve_canvas, validate, validate_plan
from .video_resume import checkpoint, save

EDITABLE = ('megapixels','steps','cfg','sampler','scheduler','seed','offload','attention','pdd_enabled','pdd_lora','experimental_resolution','loras','source_conditioning','attention_chunks','attention_chunks_mode','veda_predictor','veda_sparsity','veda_reference_sparsity','shift_video','shift_audio','variants','variants_mode')


def load(app, chat_id, ident):
    app.store.chat(chat_id)
    if not isinstance(ident,str) or not re.fullmatch('[a-f0-9]{32}',ident):
        raise ValueError('Scegli un video MiniMax generato e conservato in H3-Chat.')
    # This store belongs to the authenticated workspace, including for gallery use.
    row=app.store.one("SELECT j.payload,m.meta FROM jobs j JOIN messages m ON m.id=j.message_id WHERE j.id=? AND j.status='done' AND m.status='done'",(ident,))
    if not row:raise ValueError('Il video non è completato o non è nella tua area. Un MP4 esterno non contiene prompt e riferimenti originali.')
    payload=json.loads(row['payload']);meta=json.loads(row['meta'])
    if meta.get('intent')!='video' or meta.get('upscale') or payload['settings'].get('_upscale'):
        raise ValueError('Ricrea video richiede una generazione MiniMax originale.')
    folder=safe_join(app.data,'outputs/'+ident)
    refs=meta.get('references',payload['media'])
    for item in refs:
        if not safe_join(app.data,item['path']).is_file():raise ValueError('Un riferimento originale non è più disponibile.')
    if (folder/'scenes.json').is_file():
        record=checkpoint(app.data,ident)
        if record.get('revision_remount') is False:raise ValueError('Questa richiesta ha prodotto spezzoni separati. Scegli un singolo spezzone per modificarlo.')
        if record.get('imported_size'):raise ValueError('Un video importato non contiene le istruzioni originali di tutte le scene. Usa Modifica clip per cambiare altri tratti.')
        if record['completed']!=len(record['timeline']):raise ValueError('Il video contiene clip incompleti.')
    else:
        try:value=json.loads((folder/'video-plan.json').read_text(encoding='utf-8'))
        except (OSError,ValueError):raise ValueError('Le istruzioni originali MiniMax non sono disponibili.')
        p=value['parameters'];frames=p.get('output_frames',p.get('frames'))
        if type(frames) is not int or not 1<=frames<=360:raise ValueError('Durata del video salvato non valida.')
        record={'timeline':[{'index':0,'start':0,'duration':frames/24,'frames':frames}],
            'prompts':[value['plan']['prompt']],'plan':value['plan'],'completed':1,'parameters':[p],
            'outputs':['outputs/'+ident+'/video.mp4'],'model':payload['settings']['video_model'],'audio_start':0}
    model=app.engine.require_model(record['model'],'video')
    if model.get('remote_media'):raise ValueError('Ricrea video richiede MiniMax H3 standalone e i suoi piani salvati.')
    images=[r for r in refs if r['mime'].startswith('image/')]
    audios=[r for r in refs if r['mime'].startswith('audio/')]
    cursor=0;recipes=[];partial=False
    for i,scene in enumerate(record['timeline']):
        frames=scene.get('frames');start=scene.get('start');seconds=scene.get('duration')
        if type(frames) is not int or not 1<=frames<=360 or any(type(x) not in (int,float) or not math.isfinite(x) for x in (start,seconds)) or abs(start-cursor)>1e-6 or abs(seconds-frames/24)>1e-6:
            raise ValueError('Tempi dei clip salvati non validi.')
        cursor=start+seconds
        scene['index']=i
        if record.get('recreate_recipes'):
            recipe=copy.deepcopy(record['recreate_recipes'][i])
        else:
            path=safe_join(app.data,record['outputs'][i])
            with path.open('rb') as stream:
                if stream.read(12)[4:8]!=b'ftyp':raise ValueError('Un clip originale non è un MP4 valido.')
            local_refs=[images[x['index']-1] for x in scene['images']]+audios if 'images' in scene else refs
            # Edited clip files contain plans in their own, inherited output folder.
            # Interval edits save a merged clip and need the combined direction.
            plan_path=path.parent/'video-plan.json'
            is_partial=bool(record['parameters'][i].get('post_edit_interval'))
            if plan_path.is_file() and not is_partial:
                plan=json.loads(plan_path.read_text(encoding='utf-8'))['plan']
                # Post-production generation supplies exactly its selected song.
                if i+1 in record.get('revision_completed',[]) and str(i+1) in record.get('revision_plans',{}):
                    track=next(a for a in record['plan']['audios'] if a['role'] in ('reuse','lipsync'))
                    local_refs=[images[x['index']-1] for x in scene['images']]+[audios[track['index']-1]]
            else:
                from .video_timeline import scene_plan
                text=record['prompts'][i]
                if 'images' in scene:
                    # Full-clips reconstructed from saved global Picture labels.
                    chosen=copy.deepcopy(scene['images'])
                    if is_partial:
                        used={x['index'] for x in chosen}|{int(x) for x in re.findall(r'<Picture\s+(\d+)>',text,re.I)}
                        current={x['index']:x for x in chosen}
                        chosen=[copy.deepcopy(current.get(n,{'index':n,'role':'reference'})) for n in sorted(used)]
                        if len(chosen)>9:raise ValueError('La regia combinata contiene più di nove riferimenti nel clip.')
                        local_refs=[images[x['index']-1] for x in chosen]+audios
                    mapping={x['index']:n for n,x in enumerate(chosen,1)}
                    def remap(match):
                        number=int(match[1])
                        if number not in mapping:raise ValueError('Riferimento della regia salvata non disponibile.')
                        return '<Picture '+str(mapping[number])+'>'
                    plan={'prompt':re.sub(r'<Picture\s+(\d+)>',remap,text,flags=re.I),
                        'images':[{'index':n,'role':x['role'],'seconds':x.get('seconds',0)} for n,x in enumerate(chosen,1)],
                        'audios':copy.deepcopy(record['plan']['audios'])}
                else:plan=scene_plan(record['plan'],scene|{'last':i==len(record['timeline'])-1},0,text,normalize=False)
                for a in plan['audios']:
                    if a['role'] in ('reuse','lipsync'):
                        a['start']=record.get('audio_start',0)+start
                        if 'lip_sync' in scene:a['role']='lipsync' if scene['lip_sync'] else 'reuse'
            partial|=is_partial
            if record.get('extension'):
                # The new soundtrack uses the shifted timeline's clock.
                for a in plan['audios']:
                    if a['role'] in ('reuse','lipsync'):a['start']=record.get('audio_start',0)+start
            recipe={'plan':plan,'refs':local_refs}
            if scene.get('extension_context'):recipe['extension_context']=scene['extension_context']
            if scene.get('generation_mode')=='video':
                params=record['parameters'][i]
                if is_partial:
                    # A combined interval edit is replayed against its complete
                    # saved clip, whose unchanged surrounding motion is intact.
                    recipe['source_video']={'path':record['outputs'][i],'start':0,'frames':frames,'megapixels':.35}
                elif params.get('source_video_recipe'):recipe['source_video']=copy.deepcopy(params['source_video_recipe'])
                else:raise ValueError('La modifica salvata non contiene la clip sorgente per la ricreazione.')
        if recipe.get('source_video'):
            from .video_reference import validate_source
            recipe['source_video']=validate_source(recipe['source_video'])
            if not safe_join(app.data,recipe['source_video']['path']).is_file():raise ValueError('Video sorgente della modifica non più disponibile.')
        recipe['plan']=validate_plan(recipe['plan'],recipe['refs'],seconds,source_video=bool(recipe.get('source_video')))
        for item in recipe['refs']:
            if not safe_join(app.data,item['path']).is_file():raise ValueError('Un riferimento del clip non è più disponibile.')
        recipes.append(recipe)
    soundtrack=next((a for a in record['plan']['audios'] if a['role'] in ('reuse','lipsync')),None)
    audio=audios[soundtrack['index']-1] if soundtrack else None
    duration=meta.get('video_parameters',{}).get('duration',cursor)
    if type(duration) not in (int,float) or not math.isfinite(duration) or abs(duration-cursor)>1/24+1e-6:raise ValueError('La durata originale non coincide con i clip.')
    return {'record':record,'recipes':recipes,'refs':refs,'audio':audio,'duration':duration,
        'partial':partial,'payload':payload,'meta':meta,'model':model}


def tuning(value, changes=None):
    p=value['record']['parameters'][0]
    saved={k:p[k] for k in DEFAULTS if k in p}
    # Nonstandard source-image aspect ratios are preserved by the saved canvas.
    if saved.get('aspect') not in ('16:9','9:16','1:1','4:3','3:4'):saved['aspect']='16:9'
    saved['duration']=max(1,min(15,saved.get('duration',15)))
    return validate(saved|(changes or {}))


def describe(app,chat_id,ident):
    value=load(app,chat_id,ident);p=tuning(value)
    from .video_edit import model_choices
    from .video_loras import choices
    return {'attention_choices':True,'batch_variants':'variants' in DEFAULTS,'source':ident,'model':value['model']['name'],'model_id':value['model']['id'],'models':model_choices(app),'loras':choices(app),'duration':value['duration'],
        'aspect':value['record']['parameters'][0].get('aspect','16:9'),
        'parameters':{k:min(p[k],.98) if k=='megapixels' and not p.get('experimental_resolution') else p[k] for k in EDITABLE},'clips':len(value['recipes']),
        'references':[{'name':x['name'],'mime':x['mime']} for x in value['refs']],
        'audio':value['audio']['name'] if value['audio'] else None,
        'partial_edit':value['partial'],
        'directions':[{'clip':i+1,'prompt':r['plan']['prompt']} for i,r in enumerate(value['recipes'])]}


def request(app,chat_id,body):
    if not isinstance(body,dict) or set(body)-{'source','parameters','canvas','model'}:raise ValueError('Richiesta di ricreazione non valida.')
    value=load(app,chat_id,body.get('source'));changes=body.get('parameters',{})
    if isinstance(changes,dict):changes={k:v for k,v in changes.items() if k!='longtake_enabled'}
    original_model=value['model']['id']
    if not isinstance(body.get('model',''),str):raise ValueError('Selezione modello video non valida.')
    if body.get('model'):
        selected=app.engine.require_model(body['model'],'video')
        if selected.get('remote_media'):raise ValueError('Il confronto richiede un modello MiniMax H3 standalone.')
        value['model']=selected
    if not isinstance(changes,dict) or set(changes)-set(EDITABLE):raise ValueError('Puoi cambiare i parametri di generazione; formato, durata e riferimenti restano quelli salvati.')
    if value['model']['id']!=original_model:
        preset=app.store.settings().get('video_overrides',{}).get(value['model']['id'],{})
        changes={key:preset[key] for key in ACCELERATION_KEYS if key in preset}|changes
    tuning(value,changes)
    canvas=body.get('canvas',value['payload'].get('canvas',False))
    if type(canvas) is not bool:raise ValueError('Destinazione canvas non valida.')
    settings=copy.deepcopy(value['payload']['settings'])
    for k in list(settings):
        if k.startswith('_'):settings.pop(k)
    settings.update(_video=True,_assistant=False,_rag=False,_video_quality='high',
        video_model=value['model']['id'],_video_recreate={'source':body['source'],'parameters':changes})
    prompt=f"Ricrea video · {len(value['recipes'])} clip · {value['duration']:g} s · stessa regia, riferimenti e audio\n"+json.dumps(changes,ensure_ascii=False)
    ident=app.store.enqueue(chat_id,prompt,value['refs'],settings,canvas)
    app.wake.set()
    return {'job_id':ident,'canvas':canvas}


def render(app,job,payload,settings,cancel,stage,log):
    command=settings['_video_recreate'];value=load(app,job['chat_id'],command['source'])
    value['model']=app.engine.require_model(settings['video_model'],'video')
    from .soundtrack import probe,compose
    from .video_timeline import validate_audio_interval
    durations={}
    for i,recipe in enumerate(value['recipes']):
        audios=[r for r in recipe['refs'] if r['mime'].startswith('audio/')]
        for a in recipe['plan']['audios']:
            if a['role'] not in ('reuse','lipsync'):continue
            audio=audios[a['index']-1]
            if audio['id'] not in durations:durations[audio['id']]=probe(app.engine,app.data,audio,cancel,stage,log)['duration']
            validate_audio_interval(durations[audio['id']],a['start'],value['record']['timeline'][i]['duration'],tail=i==len(value['recipes'])-1)
    folder=app.data/'outputs'/job['id'];folder.mkdir(parents=True,exist_ok=True)
    original=value['record']
    record={'timeline':copy.deepcopy(original['timeline']),'prompts':list(original['prompts']),
        'plan':copy.deepcopy(original['plan']),'model':value['model']['id'],'audio_start':original.get('audio_start',0),
        'completed':0,'parameters':[],'outputs':[],'recreate_recipes':value['recipes'],'recreate_source':command['source'],
        'recreate_parameters':command['parameters']}
    if original.get('storyboard'):record['storyboard']=copy.deepcopy(original['storyboard'])
    if settings.get('_video_resume'):
        resumed=checkpoint(app.data,settings['_video_resume'])
        if resumed.get('recreate_source')!=command['source'] or resumed.get('recreate_parameters')!=command['parameters']:raise ValueError('La richiesta da recuperare non coincide con la ricreazione.')
        record=resumed
    settings=settings|{'_video_batch_id':record.get('batch_id') or job['id']}
    save(folder,record)
    completed=record['completed'];canvas=None
    for i,scene in enumerate(record['timeline']):
        if cancel.is_set():raise Cancelled()
        if i<completed:continue
        p=original['parameters'][i]
        presets=tuning({'record':{'parameters':[p]}},command['parameters'])
        local=settings|{'video_overrides':{value['model']['id']:presets}}
        resolved=resolve_canvas(options(value['model'],local,False),{'images':[]},[],p.get('aspect','16:9'))
        canvas={k:resolved[k] for k in ('width','height','output_width','output_height','aspect','aspect_source','format_image')}
        scoped=scene|{'index':i,'sequence':job['id'],'canvas':canvas,'last':i==len(record['timeline'])-1}
        if presets['variants']>1 and i and scene.get('continuity')!='cut':
            from .video_batch import memory_for
            scoped['batch_memories']={str(n):memory_for(record,i,n,presets['variants_mode'],app.data) for n in range(1,presets['variants']+1)}
        if completed and i==completed and scene.get('continuity')!='cut':
            anchor=max((n for n in range(i) if record['timeline'][n].get('continuity')=='cut'),default=0)
            scoped['resume_memory']={'opening':str(safe_join(app.data,record['outputs'][anchor])),
                'recent':[str(safe_join(app.data,p)) for p in record['outputs'][anchor:][-2:]]}
        recipe=value['recipes'][i]
        if recipe.get('source_video'):scoped['source_video']=recipe['source_video']
        if recipe.get('extension_context'):scoped['extension_context']=recipe['extension_context']
        def report(label):stage(f'Ricreazione · clip {i+1}/{len(value["recipes"])} · '+label)
        media=app.engine.generate_video(value['model'],local,recipe['plan'],recipe['refs'],job['id']+f'/scene-{i+1:03d}',cancel,report,prompt=canvas['aspect'],scene=scoped)
        record['outputs'].append(media['path']);record['parameters'].append(media['generation']);record['completed']=i+1
        from .video_batch import register
        register(record,i,media,value['refs']);save(folder,record)
    paths=[safe_join(app.data,p) for p in record['outputs']]
    if value['audio']:
        result=compose(app.engine,paths,safe_join(app.data,value['audio']['path']),folder/'video.mp4',cancel,stage,log,audio_start=record['audio_start'],audio_duration=value['duration'])
        from .video_batch import compose_branches
        compose_branches(app.engine,record,folder,value['audio'],cancel,stage,log,record['audio_start'],value['duration'])
        path=folder/'video.mp4';duration=result['duration']
    elif len(paths)==1:path=paths[0];duration=value['duration']
    else:raise ValueError('Questo montaggio non contiene una traccia audio originale recuperabile.')
    params=record['parameters'][0]|{'duration':duration,'scenes':len(paths),'scene_parameters':record['parameters'],
        'audio_preserved':bool(value['audio']),'audio_start':record['audio_start'],'recreated_from':command['source'],'recovered_scenes':completed}
    if record.get('batch_movies'):params['batch_movies']=record['batch_movies']
    media={'id':job['id'],'name':'Video MiniMax H3 · ricreato.mp4','mime':'video/mp4','path':path.relative_to(app.data).as_posix(),'generation':params}
    meta={'intent':'video','canvas':bool(payload.get('canvas')),'model':value['model']['name'],
        'execution_mode':'Standalone · GPU · ricreazione','assistant_on':False,'references':value['refs'],'video_plan':record['plan'],'video_parameters':params}
    if payload.get('canvas'):
        app.save_artifact(job['chat_id'],'Video · ricreato','',[media]);meta['artifact']={'title':'Video · ricreato','content':'','media':[media]}
    app.store.update_answer(job,'Ho ricreato il video con la regia salvata e i nuovi parametri.','done',[] if payload.get('canvas') else [media],meta)
    app.store.execute("UPDATE jobs SET status='done',stage='Video ricreato' WHERE id=?",(job['id'],))

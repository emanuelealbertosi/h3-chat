"""Audio-only post production, serialized by the same queue as video generation."""
import copy
import json
import math
from pathlib import Path
from uuid import uuid4
from .downloads import safe_join,Cancelled
from . import remix_runtime

MODES=('audio','voice','music','singing','clone','instrumental')

def validate(body):
    if not isinstance(body,dict):raise ValueError('Richiesta Remix non valida.')
    mode=body.get('mode','audio')
    if mode not in MODES:raise ValueError('Scegli audio, voce, musica, canto oppure clona voce.')
    result={'mode':mode}
    for key,default,lo,hi in (('start',0,0,600),('end',0,0,600),('reference_start',0,0,600),('reference_duration',10,1,30),('audio_start',0,0,86400),('gain_db',0,-18,12)):
        value=body.get(key,default)
        if type(value) not in (int,float) or not math.isfinite(value) or not lo<=value<=hi:raise ValueError('Tempo o volume Remix non valido: '+key)
        result[key]=float(value)
    for key,default in (('preserve_base',False),('clone_voice',False)):
        value=body.get(key,default)
        if type(value) is not bool:raise ValueError('Scelta Remix non valida: '+key)
        result[key]=value
    result['fit']=body.get('fit','pad')
    if result['fit'] not in ('pad','stretch','loop'):raise ValueError('Adattamento audio non valido.')
    from .voice import validate_fields
    result['voice_fields']=validate_fields(body.get('voice_fields',{}))
    for key,limit in (('text',24000),('style',4000),('abc',30000),('reference_transcript',5000)):
        text=body.get(key,'')
        if not isinstance(text,str) or len(text)>limit:raise ValueError('Testo Remix troppo lungo o non valido.')
        result[key]=text.strip()
    if mode in ('voice','music','singing') and not result['text']:raise ValueError('Scrivi il testo da pronunciare o cantare; per musica strumentale usa [Instrumental].')
    if mode in ('music','singing') and len(result['text'])>16000:raise ValueError('Il testo musicale può contenere fino a 16.000 caratteri.')
    if mode in ('clone','singing','instrumental'):result['preserve_base']=True
    if result['preserve_base'] and mode=='music':raise ValueError('Per mantenere la base originale scegli Canto.')
    if result['clone_voice'] and mode not in ('voice','singing'):raise ValueError('Clona voce richiede Voce oppure Canto.')
    return result

def request(app,chat_id,body):
    app.store.chat(chat_id)
    config=validate(body)
    files=app.validate_media(body.get('media',[]),canvas=True)
    video=[x for x in files if x['mime'].startswith('video/')]
    if len(video)!=1:raise ValueError('Scegli un solo video da remixare.')
    audios=[x for x in files if x['mime'].startswith('audio/')]
    if len(files)!=len(video)+len(audios) or len(audios)>2:raise ValueError('Scegli il video, una traccia audio e al massimo un campione vocale.')
    by_id={x['id']:x for x in audios}
    for key in ('audio','reference'):
        ident=body.get(key)
        if ident is not None and ident not in by_id:raise ValueError('Audio Remix non disponibile.')
        config[key]=by_id.get(ident)
    if config['mode']=='audio' and not config['audio']:raise ValueError('Scegli la nuova traccia audio.')
    if config['mode']=='clone' and not config['reference']:raise ValueError('Scegli il campione della nuova voce.')
    options=remix_runtime.settings(app.root);available=remix_runtime.ready(app.root,options)
    if not available['media']:raise ValueError('Installa il motore Remix nelle impostazioni.')
    if config['preserve_base'] and not available['separation']:raise ValueError('Configura HTDemucs nelle impostazioni Remix.')
    if (config['mode']=='clone' or config['mode']=='singing' and config['clone_voice']) and not available['conversion']:raise ValueError('Configura SeedVC nelle impostazioni Remix.')
    if config['mode']=='singing' and not available['score'] and not config['abc']:raise ValueError('Configura SheetSage2 e MERT oppure fornisci uno spartito ABC nelle opzioni avanzate.')
    settings=app.store.settings()
    if config['mode'] in ('music','singing'):
        model=app.engine.require_model(settings['music_model'],'music')
        if config['mode']=='singing' and model.get('remote_media'):raise ValueError('Il nuovo canto sulla base originale richiede YuE2 standalone.')
    if config['mode']=='voice':
        from .voice import runtime_ready
        if not runtime_ready(app.root):raise ValueError('Installa Higgs dal Setup Voice.')
    canvas=body.get('canvas',False)
    if type(canvas) is not bool:raise ValueError('Destinazione canvas non valida.')
    config.update(video=video[0],runtime=options)
    settings.update(_video_remix=config,_assistant=False,_rag=False)
    ident=app.store.enqueue(chat_id,'Remix video · '+config['mode']+'\n'+(config['text'] or video[0]['name']),files,settings,canvas)
    app.wake.set();return {'job_id':ident,'canvas':canvas}

def render(app,job,payload,settings,cancel,stage,log):
    config=copy.deepcopy(settings['_video_remix']);validate(config)
    runtime=remix_runtime.validate(config['runtime'])
    folder=app.data/'outputs'/job['id'];folder.mkdir(parents=True,exist_ok=True)
    source=safe_join(app.data,config['video']['path'])
    def call(op,**kw):
        if cancel.is_set():raise Cancelled()
        return app.engine.tool_call('video-remix-worker.py',{'op':op,'runtime':runtime,'folder':str(folder),'source':str(source),**kw},cancel,stage,log,timeout=14400)
    stage('Remix · preparazione e rilascio dei modelli')
    app.engine.stop()
    info=call('probe');duration=info['duration'];start=config['start'];end=config['end'] or duration
    if not 0<=start<end<=duration+.05 or end-start<.25:raise ValueError('Scegli un tratto di almeno 0,25 secondi entro il video.')
    end=min(end,duration);span=end-start
    if duration>600:raise ValueError('Remix supporta video fino a 10 minuti.')
    if not info['has_audio'] and (config['preserve_base'] or config['clone_voice'] and not config['reference']):raise ValueError('Il video non contiene una traccia da separare o clonare.')
    config.update(start=start,end=end)
    device='CPU · montaggio audio'
    if config['mode']=='voice':device=('GPU' if settings['voice_device']=='gpu' else 'CPU')+' · Higgs e montaggio audio'
    elif config['mode']=='music':
        from .music_runtime import backend
        device=('Server esterno' if app.engine.require_model(settings['music_model'],'music').get('remote_media') else backend(settings).upper())+' · musica e montaggio audio'
    if config['preserve_base'] or config['mode'] in ('clone','singing','instrumental'):device+=(' · GPU' if runtime['backend']=='cuda' else ' · CPU')+' · separazione e remix'
    meta={'intent':'video','canvas':bool(payload.get('canvas')),'execution_mode':('' if device.startswith('Server esterno') else 'Standalone · ')+device,'remix':{k:v for k,v in config.items() if k not in ('runtime','reference','audio')}}
    app.store.update_answer(job,'',meta=meta)
    reference=safe_join(app.data,config['reference']['path']) if config['reference'] else None
    if config['mode']=='voice':
        from .voice import synthesize,controls
        synth_settings=copy.deepcopy(settings)
        synth_settings['_voice_fields']=config['voice_fields']
        if config['clone_voice']:
            prepared=call('reference',reference=str(reference) if reference else None,start=config['reference_start'],duration=config['reference_duration'],separate=config['preserve_base'])
            gender=controls(synth_settings,'')[0]['gender']
            synth_settings['voice_references'][gender]={'path':prepared['path'],'transcript':config['reference_transcript']}
        result,media=synthesize(app,folder/'speech',[{'text':config['text']}],synth_settings,'',cancel,stage,log,{})
        replacement=folder/'speech/audio.wav'
        # The Voice worker's manifest is authoritative about its output filename.
        replacement=safe_join(app.data,next(m['path'] for m in media if m['mime']=='audio/wav'))
    elif config['mode']=='music':
        model=app.engine.require_model(settings['music_model'],'music')
        composition={'title':'Musica remix','style':config['style'] or 'Italian, clear vocals','lyrics':config['text'],'abc':config['abc'],'instrumental':config['text']=='[Instrumental]'}
        media=app.engine.generate_music(model,settings,composition,job['id']+'/music',cancel,stage)
        replacement=safe_join(app.data,media['path']);app.engine.stop()
    elif config['mode'] in ('clone','singing','instrumental'):
        music={}
        if config['mode']=='singing':
            from .music_options import options,worker_options
            model=app.engine.require_model(settings['music_model'],'music')
            music={'files':app.engine.model_files(model),'options':worker_options(options(model,settings))}
        result=call('vocal',config=config,reference=str(reference) if reference else None,music=music)
        replacement=Path(result['path']);config['preserve_base']=False # Already combined with the original accompaniment.
    else:replacement=safe_join(app.data,config['audio']['path'])
    result=call('render',replacement=str(replacement),config=config)
    if cancel.is_set():raise Cancelled()
    media=[{'id':job['id'],'name':'Video remix.mp4','path':(folder/'remix.mp4').relative_to(app.data).as_posix(),'mime':'video/mp4','remix':meta['remix']},
           {'id':uuid4().hex,'name':'Traccia remix.wav','path':(folder/'audio.wav').relative_to(app.data).as_posix(),'mime':'audio/wav'}]
    meta['remix'].update(duration=result['duration'],video_stream_copied=True,lip_sync_updated=False)
    text='Ho creato una nuova versione modificando soltanto l’audio del tratto scelto. Il video conserva immagini, durata e formato. Il movimento delle labbra resta quello originale.'
    if payload.get('canvas'):
        app.save_artifact(job['chat_id'],'Video remix','',media);meta['artifact']={'title':'Video remix','content':'','media':media}
    app.store.update_answer(job,text,'done',[] if payload.get('canvas') else media,meta)
    app.store.execute("UPDATE jobs SET status='done',stage='Remix pronto' WHERE id=?",(job['id'],))
    stage('Remix completato')

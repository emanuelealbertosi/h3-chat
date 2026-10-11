"""Video upscale is deterministic media work, queued alongside all GPU generation."""
import math
import re
from pathlib import Path
from .downloads import Cancelled,safe_join
from . import upscale_runtime as runtime

OPTION_KEYS=set(runtime.DEFAULTS)

def options(root,body):
    supplied=body.get('options',{})
    if isinstance(supplied,dict) and supplied.get('engine')=='seed':raise ValueError(runtime.REMOVED)
    if not isinstance(supplied,dict) or set(supplied)-OPTION_KEYS:raise ValueError('Opzioni upscale non valide.')
    result=runtime.validate(runtime.settings(root)|supplied)
    preview=body.get('preview',False);start=body.get('start',0)
    if type(preview) is not bool or type(start) not in (int,float) or not math.isfinite(start) or not 0<=start<=86400:raise ValueError('Intervallo anteprima non valido.')
    result.update(preview=preview,start=float(start) if preview else 0,duration=10 if preview else None)
    return result

def request(app,chat_id,body):
    app.store.chat(chat_id)
    media=app.validate_media(body.get('media',[]),canvas=True)
    if len(media)!=1 or not media[0]['mime'].startswith('video/'):raise ValueError('Scegli un solo video da elaborare.')
    config=options(app.root,body)
    if not runtime.describe(app.root)['ready']['base']:raise ValueError('Installa il runtime CUDA Python nelle impostazioni upscale.')
    if not runtime.ready(app.root,'upscale_rtx'):raise ValueError('Installa il motore RTX VSR nelle impostazioni.')
    canvas=body.get('canvas',False)
    if type(canvas) is not bool:raise ValueError('Destinazione canvas non valida.')
    settings=app.store.settings()|{'_upscale':config,'_assistant':False,'_rag':False}
    name='RTX VSR'
    prompt=f"Upscale video · {name} · {config['target']}"+(' · prova di 10 secondi' if config['preview'] else '')+'\n'+media[0]['name']
    job=app.store.enqueue(chat_id,prompt,media,settings,canvas);app.wake.set()
    return {'job_id':job,'canvas':canvas}

def render(app,job,payload,settings,cancel,stage,log):
    config=settings['_upscale'];source=payload['media'][0]
    runtime.validate({k:v for k,v in config.items() if k not in ('preview','start','duration')})
    origin=safe_join(app.data,source['path'])
    folder=app.data/'outputs'/job['id'];folder.mkdir(parents=True,exist_ok=True)
    cache=folder/'upscale'
    resume=settings.get('_upscale_resume')
    if resume:
        if not isinstance(resume,str) or not re.fullmatch('[a-f0-9]{32}',resume):raise ValueError('Recupero upscale non valido.')
        cache=safe_join(app.data,'outputs/'+resume+'/upscale')
    if cancel.is_set():raise Cancelled()
    stage('Upscale · liberazione dei modelli di generazione')
    app.engine.stop()
    request={'source':str(origin),'output':str(folder/'upscale.mp4'),'cache':str(cache),'config':config}
    meta={'intent':'video','canvas':bool(payload.get('canvas')),'execution_mode':'Standalone · GPU · upscale'}
    app.store.update_answer(job,'',meta=meta)
    result=app.engine.tool_call('upscale-worker.py',request,cancel,stage,log,timeout=86400)
    if cancel.is_set():raise Cancelled()
    name=('Prova upscale' if config['preview'] else 'Video upscale')+' · RTX VSR.mp4'
    media={'id':job['id'],'name':name,'mime':'video/mp4','path':(folder/'upscale.mp4').relative_to(app.data).as_posix(),
           'upscale':{k:v for k,v in result.items() if k!='path'}}
    text=f"Ho creato una nuova versione a {result['width']} × {result['height']}. Il video originale resta disponibile."
    if payload.get('canvas'):
        app.save_artifact(job['chat_id'],name,'',[media]);meta['artifact']={'title':name,'content':'','media':[media]}
    app.store.update_answer(job,text,'done',[] if payload.get('canvas') else [media],meta)
    app.store.execute("UPDATE jobs SET status='done' WHERE id=?",(job['id'],))
    stage('Upscale completato')

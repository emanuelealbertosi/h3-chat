"""Import external footage for the existing clip editor, within its user's area."""
import json,subprocess,threading
from pathlib import Path
from .downloads import safe_join
from .video_options import options,resolve_canvas
LOCK=threading.Lock()

def invoke(app,request):
    process=subprocess.run([str(app.root/'runtime/python/python.exe'),'-X','utf8',str(app.root/'native/video-remix-worker.py')],input=json.dumps(request)+'\n',text=True,encoding='utf-8',capture_output=True,timeout=120,cwd=app.root,creationflags=0x08000000)
    events=[json.loads(line) for line in process.stdout.splitlines() if line.startswith('{')]
    result=next((e['result'] for e in events if e.get('event')=='result'),None)
    if result is None:raise ValueError(next((e.get('message') for e in events if e.get('event')=='error'),'Il video esterno non è leggibile.'))
    return result

def metadata(app,item):
    from .remix_runtime import ready
    if not ready(app.root)['media']:raise ValueError('Installa il montaggio Remix nelle impostazioni prima di importare un video.')
    source=safe_join(app.data,item['path']);cache=safe_join(app.data,'outputs/video-imports/'+item['id'])
    cache.mkdir(parents=True,exist_ok=True)
    with LOCK:
        manifest=cache/'import.json';stat=source.stat()
        if manifest.is_file():
            result=json.loads(manifest.read_text(encoding='utf-8'))
            if result.get('fingerprint')==[stat.st_size,stat.st_mtime_ns] and all(Path(x['path']).is_file() for x in result['images']) and (cache/'audio.wav').is_file():return cache,result
        result=invoke(app,{'op':'import_manifest','runtime':{'backend':'cpu','threads':4},'folder':str(cache),'source':str(source)})
    return cache,result

def interval_guide(app,value,scene,start):
    item=value['imported'];cache=safe_join(app.data,'outputs/video-imports/'+item['id'])
    result=invoke(app,{'op':'import_frame','runtime':{'backend':'cpu','threads':4},'folder':str(cache),
        'source':str(safe_join(app.data,item['path'])),'seconds':scene['start']+start})
    media={'id':result['id'],'name':f"Video originale · fotogramma {scene['start']+start:g} s",'mime':'image/png','path':Path(result['path']).relative_to(app.data).as_posix()}
    app.store.gallery.register([media]);return media

def source(app,ident):
    item=app.store.gallery.get(ident)
    if not item['mime'].startswith('video/'):raise ValueError('Scegli un video dalla tua galleria.')
    model=app.engine.require_model(app.store.settings()['video_model'],'video')
    if model.get('remote_media'):raise ValueError('La modifica del video esterno richiede MiniMax standalone.')
    cache,info=metadata(app,item)
    if not 1<=info['duration']<=600:raise ValueError('Per modificare clip importa un video da 1 secondo a 10 minuti.')
    total=round(info['duration']*24);scenes=[];images=[];params=[]
    base=options(model,app.store.settings(),False)
    canvas=resolve_canvas(base,{'images':[{'index':1,'role':'keyframe','seconds':0}]},[(info['width'],info['height'])])
    for i,frame in enumerate(range(0,total,360)):
        frames=min(360,total-frame)
        guide={'id':info['images'][i]['id'],'name':f'Video originale · fotogramma clip {i+1}','mime':'image/png','path':Path(info['images'][i]['path']).relative_to(app.data).as_posix()}
        images.append(guide)
        scenes.append({'index':i,'start':frame/24,'duration':frames/24,'frames':frames,'images':[{'index':i+1,'role':'keyframe','seconds':0}],'generation_mode':'i2v','lip_sync':False,'continuity':'cut'})
        params.append(base|{'canvas_width':canvas['width'],'canvas_height':canvas['height'],
            'width':canvas['output_width'],'height':canvas['output_height'],
            'aspect':canvas['aspect'],'aspect_source':'image','fps':24,'seed':base['seed']})
    audio={'id':info['audio_id'],'name':'Audio originale del video.wav','mime':'audio/wav','path':(cache/'audio.wav').relative_to(app.data).as_posix()}
    app.store.gallery.register(images+[audio],'generated')
    shape={'width':info['width']//2*2,'height':info['height']//2*2}
    record={'imported_size':shape,'timeline':scenes,'outputs':[(cache/f'clip-{i+1:03d}.mp4').relative_to(app.data).as_posix() for i in range(len(scenes))],
            'prompts':['Scena originale importata dal video.']*len(scenes),'parameters':params,'completed':len(scenes),'model':model['id'],'audio_start':0,
            'plan':{'prompt':'Modifica di un video esterno','images':[],'audios':[{'index':1,'role':'reuse','start':0}]}}
    refs=images+[audio]
    return {'record':record,'payload':{'media':refs,'settings':{},'canvas':False},'meta':{'video_parameters':shape|{'duration':total/24,'fps':24,'imported_video':True,'aspect':canvas['aspect']}},
            'refs':refs,'images':images,'audio':audio,'duration':total/24,'imported':item,'source_size':shape}

def prepare(app,value,cancel,stage,log):
    cache=safe_join(app.data,'outputs/video-imports/'+value['imported']['id'])
    result=app.engine.tool_call('video-remix-worker.py',{'op':'import_clips','runtime':{'backend':'cpu','threads':4},'folder':str(cache),
        'source':str(safe_join(app.data,value['imported']['path'])),'timeline':value['record']['timeline']},cancel,stage,log,timeout=3600)
    return result

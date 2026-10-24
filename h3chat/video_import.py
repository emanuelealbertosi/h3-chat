"""Import external footage for the existing clip editor, within its user's area."""
import json,math,os,subprocess,threading
from .platform_runtime import python_executable

from pathlib import Path
from .downloads import safe_join
from .video_options import options,resolve_canvas
from .video_import_windows import windows
LOCK=threading.Lock()


def progress(app,chat_id,ident,segment_seconds=15):
    app.store.chat(chat_id)
    item=app.store.gallery.get(ident)
    if not item['mime'].startswith('video/'):raise ValueError('Scegli un video.')
    segment_seconds=segment_length(segment_seconds)
    cache=safe_join(app.data,'outputs/video-imports/'+item['id'])
    if segment_seconds!=15:cache=cache/f'segments-{segment_seconds}'
    from .video_conversion_progress import read
    return read(cache/'layout-v2'/'progress.json')

def segment_length(value=15):
    if type(value) is not int or value not in (10,15):raise ValueError('Segmenti del video esterno: scegli 10 o 15 secondi.')
    return value

def validate_metadata(info):
    duration=info.get('duration')
    if type(duration) not in (int,float) or not math.isfinite(duration) or duration<1 or not math.isfinite(duration*24):
        raise ValueError('Il video deve avere una durata leggibile di almeno un secondo.')
    if not info.get('width') or not info.get('height'):raise ValueError('Il file non contiene una traccia video leggibile.')
    return info

def import_timeout(info,segment_seconds=15):
    """Scale CPU thumbnail/audio preparation time with the actual footage."""
    validate_metadata(info);segment_length(segment_seconds)
    return max(120,math.ceil(info['duration']/segment_seconds)*2+math.ceil(info['duration']/10))

def invoke(app,request,*,timeout=120):
    process=subprocess.run([str(python_executable(app.root)),'-X','utf8',str(app.root/'native/video-remix-worker.py')],input=json.dumps(request)+'\n',text=True,encoding='utf-8',capture_output=True,timeout=timeout,cwd=app.root,creationflags=0x08000000 if os.name=="nt" else 0)
    events=[json.loads(line) for line in process.stdout.splitlines() if line.startswith('{')]
    result=next((e['result'] for e in events if e.get('event')=='result'),None)
    if result is None:raise ValueError(next((e.get('message') for e in events if e.get('event')=='error'),'Il video esterno non è leggibile.'))
    return result

def metadata(app,item,segment_seconds=15,*,layout_version=2):
    segment_seconds=segment_length(segment_seconds)
    from .remix_runtime import ready
    if not ready(app.root)['media']:raise ValueError('Installa il montaggio Remix nelle impostazioni prima di importare un video.')
    source=safe_join(app.data,item['path']);cache=safe_join(app.data,'outputs/video-imports/'+item['id'])
    if segment_seconds!=15:cache=cache/f'segments-{segment_seconds}'
    # Keep old timelines and extracted clips immutable when boundaries change.
    if layout_version not in (1,2):raise ValueError('Versione della suddivisione video non valida.')
    if layout_version==2:cache=cache/'layout-v2'
    cache.mkdir(parents=True,exist_ok=True)
    from .video_conversion_progress import write
    progress_file=cache/'progress.json'
    manifest=cache/'import.json';stat=source.stat()
    def cached():
        try:
            result=json.loads(manifest.read_text(encoding='utf-8'))
            if result.get('fingerprint')==[stat.st_size,stat.st_mtime_ns] and result.get('segment_seconds',15)==segment_seconds and result.get('segmentation_version',1)==layout_version and all(Path(x['path']).is_file() for x in result['images']) and (cache/'audio.wav').is_file():return result
        except (OSError,ValueError,KeyError,TypeError):pass
    # Reopening a prepared timeline must not queue behind another video's
    # conversion. The manifest is published atomically by the CPU worker.
    result=cached()
    if result is not None:return cache,result
    with LOCK:
        write(progress_file,'In attesa della preparazione')
        result=cached()
        if result is not None:
            write(progress_file,'Suddivisione già pronta',status='done',done=1,total=1);return cache,result
        try:
            write(progress_file,'Lettura del video originale')
            info=validate_metadata(invoke(app,{'op':'probe','runtime':{'backend':'cpu','threads':4},'folder':str(cache),'source':str(source)}))
            result=invoke(app,{'op':'import_manifest','runtime':{'backend':'cpu','threads':4},'folder':str(cache),'source':str(source),'segment_seconds':segment_seconds,'segmentation_version':layout_version},timeout=import_timeout(info,segment_seconds))
            write(progress_file,'Suddivisione pronta',status='done',done=1,total=1)
        except Exception:
            write(progress_file,'Preparazione non riuscita',status='failed');raise
    return cache,result

def interval_guide(app,value,scene,start):
    item=value['imported'];cache=safe_join(app.data,'outputs/video-imports/'+item['id'])
    result=invoke(app,{'op':'import_frame','runtime':{'backend':'cpu','threads':4},'folder':str(cache),
        'source':str(safe_join(app.data,item['path'])),'seconds':scene['start']+start})
    media={'id':result['id'],'name':f"Video originale · fotogramma {scene['start']+start:g} s",'mime':'image/png','path':Path(result['path']).relative_to(app.data).as_posix()}
    app.store.gallery.register([media],internal=True);return media

def source(app,ident,segment_seconds=15,*,layout_version=2):
    segment_seconds=segment_length(segment_seconds)
    item=app.store.gallery.get(ident)
    if not item['mime'].startswith('video/'):raise ValueError('Scegli un video dalla tua galleria.')
    model=app.engine.require_model(app.store.settings()['video_model'],'video')
    if model.get('remote_media'):raise ValueError('La modifica del video esterno richiede MiniMax standalone.')
    cache,info=metadata(app,item,segment_seconds,layout_version=layout_version)
    validate_metadata(info)
    total=round(info['duration']*24);scenes=[];images=[];params=[]
    base=options(model,app.store.settings(),False)
    canvas=resolve_canvas(base,{'images':[{'index':1,'role':'keyframe','seconds':0}]},[(info['width'],info['height'])])
    parts=windows(total,segment_seconds) if layout_version==2 else [(f,min(segment_seconds*24,total-f)) for f in range(0,total,segment_seconds*24)]
    for i,(frame,frames) in enumerate(parts):
        guide={'id':info['images'][i]['id'],'name':f'Video originale · fotogramma clip {i+1}','mime':'image/png','path':Path(info['images'][i]['path']).relative_to(app.data).as_posix()}
        images.append(guide)
        scenes.append({'index':i,'start':frame/24,'duration':frames/24,'frames':frames,'images':[{'index':i+1,'role':'keyframe','seconds':0}],'generation_mode':'i2v','lip_sync':False,'continuity':'cut'})
        params.append(base|{'canvas_width':canvas['width'],'canvas_height':canvas['height'],
            'width':canvas['output_width'],'height':canvas['output_height'],
            'aspect':canvas['aspect'],'aspect_source':'image','fps':24,'seed':base['seed']})
    audio={'id':info['audio_id'],'name':'Audio originale del video.wav','mime':'audio/wav','path':(cache/'audio.wav').relative_to(app.data).as_posix()}
    app.store.gallery.register(images,'generated',internal=True)
    app.store.gallery.register([audio],'generated')
    shape={'width':info['width']//2*2,'height':info['height']//2*2}
    record={'imported_size':shape,'import_segment_seconds':segment_seconds,'import_layout_version':layout_version,'timeline':scenes,'clip_sources':[{'path':item['path'],'start':s['start']} for s in scenes],
            'outputs':[(cache/f'clip-{i+1:03d}.mp4').relative_to(app.data).as_posix() for i in range(len(scenes))],
            'prompts':['Scena originale importata dal video.']*len(scenes),'parameters':params,'completed':len(scenes),'model':model['id'],'audio_start':0,
            'plan':{'prompt':'Modifica di un video esterno','images':[],'audios':[{'index':1,'role':'reuse','start':0}]}}
    refs=images+[audio]
    return {'record':record,'payload':{'media':refs,'settings':{},'canvas':False},'meta':{'video_parameters':shape|{'duration':total/24,'fps':24,'imported_video':True,'aspect':canvas['aspect']}},
            'refs':refs,'images':images,'audio':audio,'duration':total/24,'imported':item,'source_size':shape}

def repair_import_audio(app,value,cancel,stage,log):
    """Pad only derived import soundtracks; containers can outlast audio by ms."""
    path=value['audio']['path']
    if not path.startswith('outputs/video-imports/'):return
    target=safe_join(app.data,path)
    app.engine.tool_call('video-remix-worker.py',{'op':'pad_import_audio','runtime':{'backend':'cpu','threads':4},
        'folder':str(target.parent),'source':str(target),'duration':value['duration']+value['record'].get('audio_start',0)},cancel,stage,log,timeout=300)


def prepare(app,value,cancel,stage,log,*,clips=None):
    """Extract only required source intervals; untouched clips remain lazy."""
    record=value['record'];sources=record.get('clip_sources')
    if sources is None:
        if not value.get('imported'):return {'clips':0}
        sources=[{'path':value['imported']['path'],'start':s['start']} for s in record['timeline']]
        record['clip_sources']=sources
    selected=set(clips) if clips is not None else set(range(1,len(sources)+1));groups={}
    for i,source in enumerate(sources):
        if source is None or i+1 not in selected:continue
        target=safe_join(app.data,record['outputs'][i]);key=(source['path'],str(target.parent))
        # An insertion changes timeline indices, not immutable cache filenames.
        groups.setdefault(key,[]).append(record['timeline'][i]|{'start':source['start'],'output':str(target)})
    prepare_total=sum(len(scenes) for scenes in groups.values());prepare_offset=0
    if prepare_total:stage(f"Timeline · {len(record['timeline'])} clip totali · {prepare_total} tratti originali da preparare")
    for (path,folder),scenes in groups.items():
        app.engine.tool_call('video-remix-worker.py',{'op':'import_clips','runtime':{'backend':'cpu','threads':4},'folder':folder,
            'stage_prefix':'Post-produzione','source':str(safe_join(app.data,path)),'timeline':scenes,
            'timeline_total':len(record['timeline']),'prepare_total':prepare_total,'prepare_offset':prepare_offset},cancel,stage,log,timeout=3600)
        for scene in scenes:sources[scene['index']]=None
        prepare_offset+=len(scenes)
    return {'clips':sum(len(scenes) for scenes in groups.values())}

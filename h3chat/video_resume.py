"""Validate saved scene checkpoints without loading models or modifying jobs."""
import copy,json,re,math
from .downloads import safe_join

def checkpoint(data,ident):
    if not isinstance(ident,str) or not re.fullmatch(r'[a-f0-9]{32}',ident):raise ValueError('Lavoro video da recuperare non valido.')
    folder=safe_join(data,'outputs/'+ident)
    try:value=json.loads((folder/'scenes.json').read_text(encoding='utf-8'))
    except (OSError,ValueError):raise ValueError('Nessuna scena video salvata da recuperare.')
    scenes=value.get('timeline');completed=value.get('completed');scripts=value.get('prompts');parameters=value.get('parameters')
    if not isinstance(scenes,list) or not 1<=len(scenes)<=160 or type(completed) is not int or not 0<=completed<=len(scenes) or not isinstance(scripts,list) or len(scripts)!=len(scenes) or any(not isinstance(p,str) or not p.strip() for p in scripts) or not isinstance(parameters,list) or len(parameters)!=completed:raise ValueError('Checkpoint video incompleto.')
    outputs=value.get('outputs') or [f'outputs/{ident}/scene-{i+1:03d}/video.mp4' for i in range(completed)]
    if not isinstance(outputs,list) or len(outputs)!=completed:raise ValueError('Elenco scene salvate incompleto.')
    # Clip-only revisions may reference imported footage that was deliberately
    # never split. Only their newly generated files are needed for recovery.
    if value.get('revision_remount') is False and not value.get('working_timeline'):
        if not isinstance(value.get('revision_source'),str) or not re.fullmatch(r'[a-f0-9]{32}',value['revision_source']):raise ValueError('Origine della revisione non valida.')
        generated=value.get('revision_generated',{})
        if not isinstance(generated,dict):raise ValueError('Spezzoni da recuperare non validi.')
        checked=[item['path'] for item in generated.values()]
    elif value.get('clip_sources') is not None:
        sources=value['clip_sources']
        if not isinstance(sources,list) or len(sources)!=completed:raise ValueError('Origini dei clip salvati non valide.')
        for item in sources:
            if item is not None and (not isinstance(item,dict) or set(item)!={'path','start'} or not isinstance(item['path'],str) or type(item['start']) not in (int,float) or not math.isfinite(item['start']) or item['start']<0):raise ValueError('Intervallo sorgente del clip non valido.')
        checked=[item['path'] if item else output for item,output in zip(sources,outputs)]
    else:checked=outputs
    for output in dict.fromkeys(checked):
        path=safe_join(data,output)
        with path.open('rb') as stream:
            if stream.read(12)[4:8]!=b'ftyp':raise ValueError('Una scena salvata non è un MP4 valido.')
    plan=value.get('plan')
    if plan is None:
        # Older versions saved only local clip plans. Recover the final clip
        # exactly; earlier checkpoints need the original global keyframe plan.
        if completed!=len(scenes)-1:raise ValueError('Questo vecchio checkpoint non contiene il piano globale del video.')
        try:plan=copy.deepcopy(json.loads((folder/f'scene-{completed+1:03d}/video-plan.json').read_text(encoding='utf-8'))['plan'])
        except (OSError,ValueError,KeyError):raise ValueError('Il piano dell’ultima scena non è disponibile.')
        for image in plan['images']:
            if image['role']=='keyframe':image['seconds']+=scenes[completed]['start']
        for audio in plan['audios']:audio['start']=0
    return value|{'plan':plan,'outputs':outputs,'source':ident}

def save(folder,value):
    target=folder/'scenes.json';part=folder/'scenes.writing'
    part.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8');part.replace(target)

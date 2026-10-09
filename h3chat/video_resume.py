"""Validate saved scene checkpoints without loading models or modifying jobs."""
import copy,json,re
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
    for output in outputs:
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

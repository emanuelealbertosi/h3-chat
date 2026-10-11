"""Pinned standalone NVIDIA video upscale runtime and shared admin options."""
import json
import os
import threading
from pathlib import Path
from .downloads import safe_join

LOCK=threading.Lock()
DEFAULTS={'engine':'rtx','target':'2x','rtx_quality':'high','crf':18}
REMOVED='SeedVR2 è stato rimosso. Apri Upscale e avvia una nuova richiesta con RTX VSR.'

def manifests(root):
    path=Path(root)/'upscale-runtimes.json'
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}

def validate(value):
    if isinstance(value,dict) and value.get('engine')=='seed':raise ValueError(REMOVED)
    if not isinstance(value,dict) or set(value)-set(DEFAULTS):raise ValueError('Impostazioni upscale non valide.')
    result=DEFAULTS|value
    for key,choices in {'engine':('rtx',),'target':('2x','4x','1080p','1440p','2160p'),'rtx_quality':('high','ultra')}.items():
        if result[key] not in choices:raise ValueError('Scelta upscale non valida: '+key)
    if type(result['crf']) is not int or not 14<=result['crf']<=24:raise ValueError('Compressione MP4: CRF da 14 a 24.')
    return result

def settings(root):
    try:value=json.loads((Path(root)/'data/upscale.json').read_text(encoding='utf-8'))
    except FileNotFoundError:return DEFAULTS.copy()
    # Saved defaults from the old two-engine release migrate without breaking Setup.
    if not isinstance(value,dict):raise ValueError('Impostazioni upscale non valide.')
    value={k:v for k,v in value.items() if k in DEFAULTS}
    if value.get('engine')=='seed':value['engine']='rtx'
    return validate(value)

def save_settings(root,body):
    value=validate(body)
    path=Path(root)/'data/upscale.json';path.parent.mkdir(parents=True,exist_ok=True)
    with LOCK:
        part=path.with_suffix('.tmp');part.write_text(json.dumps(value,indent=2),encoding='utf-8');os.replace(part,path)
    return describe(root,admin=True)

def prepare(root,key):
    if key!='upscale_rtx':raise ValueError('Motore upscale non disponibile.')
    marker=Path(root)/('runtime/upscale/'+key+'.ready.json')
    marker.parent.mkdir(parents=True,exist_ok=True)
    marker.write_text(json.dumps(manifests(root)[key],sort_keys=True),encoding='utf-8')

def ready(root,key):
    if key!='upscale_rtx':return False
    try:
        expected=manifests(root)[key]
        actual=json.loads((Path(root)/('runtime/upscale/'+key+'.ready.json')).read_text(encoding='utf-8'))
        if actual!=expected:return False
        return (Path(root)/'runtime/upscale/packages/nvvfx/__init__.py').is_file() and all(safe_join(root,e['path']).stat().st_size==e['size'] for e in expected['files'])
    except (KeyError,OSError,ValueError):return False

def describe(root,admin=False):
    from .vision_runtime import status as vision_status
    return {'settings':settings(root),'ready':{'base':vision_status(root)['ready'],'rtx':ready(root,'upscale_rtx')},
            'sizes':{k:sum(e['size'] for e in v['files']) for k,v in manifests(root).items()}}

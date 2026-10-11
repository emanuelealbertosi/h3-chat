"""Optional, pinned standalone video restoration runtimes and shared admin options."""
import json
import os
import tarfile
import threading
from pathlib import Path
from .downloads import safe_join

LOCK=threading.Lock()
DEFAULTS={'engine':'rtx','target':'2x','rtx_quality':'high','seed_model':'models/seedvr2/seedvr2_ema_3b_fp8_e4m3fn.safetensors',
          'seed_vae':'models/seedvr2/ema_vae_fp16.safetensors','seed_batch':9,'seed':42,'seed_tile':512,'seed_swap':0,'seed_color':'lab','crf':18}

def manifests(root):
    path=Path(root)/'upscale-runtimes.json'
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}

def resolve(root,path):
    value=Path(path)
    return value.resolve() if value.is_absolute() else safe_join(root,path)

def validate(value):
    if not isinstance(value,dict) or set(value)-set(DEFAULTS):raise ValueError('Impostazioni upscale non valide.')
    result=DEFAULTS|value
    for key,choices in {'engine':('rtx','seed'),'target':('2x','4x','1080p','1440p','2160p'),
                         'rtx_quality':('high','ultra'),'seed_color':('lab','wavelet','hsv','adain','none')}.items():
        if result[key] not in choices:raise ValueError('Scelta upscale non valida: '+key)
    for key,lo,hi in [('seed_batch',5,33),('seed',0,2147483647),('seed_tile',256,1024),('seed_swap',0,32),('crf',14,24)]:
        if type(result[key]) is not int or not lo<=result[key]<=hi:raise ValueError('Parametro upscale fuori intervallo: '+key)
    if result['seed_batch']%4!=1:raise ValueError('Il batch SeedVR2 deve essere 5, 9, 13, 17, 21, 25, 29 o 33.')
    if result['seed_tile']%64:raise ValueError('Le tile devono essere multipli di 64.')
    for key in ('seed_model','seed_vae'):
        if not isinstance(result[key],str) or not result[key].strip() or len(result[key])>4096:raise ValueError('Scegli il file '+key)
    return result

def settings(root):
    try:return validate(json.loads((Path(root)/'data/upscale.json').read_text(encoding='utf-8')))
    except FileNotFoundError:return DEFAULTS.copy()

def save_settings(root,body):
    value=validate(body)
    for key in ('seed_model','seed_vae'):
        if value[key]!=DEFAULTS[key] and (not resolve(root,value[key]).is_file() or resolve(root,value[key]).suffix.lower()!='.safetensors'):
            raise ValueError('Scegli un file safetensors esistente: '+key)
    path=Path(root)/'data/upscale.json';path.parent.mkdir(parents=True,exist_ok=True)
    with LOCK:
        part=path.with_suffix('.tmp');part.write_text(json.dumps(value,indent=2),encoding='utf-8');os.replace(part,path)
    return describe(root,admin=True)

def prepare(root,key):
    """Extract only the Python antlr4 package, never execute a downloaded setup script."""
    if key=='upscale_seed':
        entry=next(e for e in manifests(root)[key]['files'] if e['path'].endswith('.tar.gz'))
        with tarfile.open(safe_join(root,entry['path']),'r:gz') as archive:
            pending=[]
            for item in archive.getmembers():
                parts=item.name.split('/')[1:]
                if not parts or parts[0]!='src' or len(parts)<3 or parts[1]!='antlr4':continue
                if item.isdir():continue
                if not item.isfile():raise ValueError('Link non consentito nel runtime upscale.')
                pending.append((item,safe_join(Path(root)/'runtime/upscale/packages','/'.join(parts[1:]))))
            if not pending:raise ValueError('Runtime antlr4 incompleto.')
            for item,target in pending:
                target.parent.mkdir(parents=True,exist_ok=True)
                with archive.extractfile(item) as src:target.write_bytes(src.read())
    marker=Path(root)/('runtime/upscale/'+key+'.ready.json')
    marker.parent.mkdir(parents=True,exist_ok=True)
    marker.write_text(json.dumps(manifests(root)[key],sort_keys=True),encoding='utf-8')

def ready(root,key):
    try:
        expected=manifests(root)[key]
        actual=json.loads((Path(root)/('runtime/upscale/'+key+'.ready.json')).read_text(encoding='utf-8'))
        if actual!=expected:return False
        package=Path(root)/'runtime/upscale/packages'
        required=[package/'nvvfx/__init__.py'] if key=='upscale_rtx' else [package/'antlr4/__init__.py',package/'omegaconf/__init__.py',Path(root)/'runtime/upscale/seedvr2/inference_cli.py',Path(root)/'runtime/upscale/seedvr2/configs_3b/main.yaml',Path(root)/'runtime/upscale/seedvr2/pos_emb.pt',Path(root)/'runtime/upscale/seedvr2/neg_emb.pt']
        return all(p.is_file() for p in required) and all(safe_join(root,e['path']).stat().st_size==e['size'] for e in expected['files'])
    except (KeyError,OSError,ValueError):return False

def describe(root,admin=False):
    value=settings(root)
    from .vision_runtime import status as vision_status
    status={'base':vision_status(root)['ready'],'rtx':ready(root,'upscale_rtx'),'seed':ready(root,'upscale_seed'),
            'seed_model':resolve(root,value['seed_model']).is_file() and resolve(root,value['seed_vae']).is_file()}
    if not admin:value={k:v for k,v in value.items() if k not in ('seed_model','seed_vae')}
    return {'settings':value,'ready':status,'sizes':{k:sum(e['size'] for e in v['files']) for k,v in manifests(root).items()}}

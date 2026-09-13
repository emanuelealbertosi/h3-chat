"""References to existing model files. Never copy, move, download or delete weights."""
from __future__ import annotations
import hashlib
import json
import os
import re
import struct
from functools import lru_cache
from pathlib import Path
from .models import metadata

PROFILES = {
    'chat': {'label':'Chat / vision · GGUF','main':'model','required':['model'],'optional':['mmproj'],
             'capabilities':['chat'],'max_refs':4},
    'sd': {'label':'Stable Diffusion / SDXL · checkpoint completo','main':'model','required':['model'],'optional':['vae'],
           'architecture':'sd','capabilities':['create','edit'],'max_refs':1},
    'flux2': {'label':'FLUX.2 klein · diffusore + encoder + VAE','main':'diffusion','required':['diffusion','llm','vae'],'optional':[],
              'architecture':'flux2','capabilities':['create','edit'],'max_refs':4,'steps':4,'cfg':1},
    'qwen-edit': {'label':'Qwen Image Edit · diffusore + componenti','main':'diffusion','required':['diffusion','llm','llm_vision','vae'],'optional':[],
                  'architecture':'qwen-edit','capabilities':['create','edit'],'max_refs':3,'cfg':2.5},
}
ROLE_LABELS = {'model':'Pesi del modello','diffusion':'Diffusore','mmproj':'Proiettore vision (mmproj)',
               'vae':'VAE','llm':'Encoder testo (LLM)','llm_vision':'Encoder vision'}
EXTENSIONS = {'.gguf','.safetensors'}


def absolute_path(value):
    if not isinstance(value,str) or not value.strip() or '\0' in value or len(value)>4096:
        raise ValueError('Indica un percorso assoluto valido sul computer.')
    value=value.strip().strip('"')
    # Reject device namespaces and alternate data streams, while allowing drive letters and UNC shares.
    if value.startswith(('\\\\.\\','\\\\?\\')) or (os.name=='nt' and ':' in value[2:]):
        raise ValueError('Usa un normale percorso di file o cartella.')
    path=Path(value).expanduser()
    if not path.is_absolute():raise ValueError('Inserisci il percorso completo, per esempio D:\\Modelli\\modello.gguf.')
    return path.resolve()


@lru_cache(maxsize=128)
def _safetensors_valid(path,size,stamp):
    try:
        with open(path,'rb') as stream:
            header_size=struct.unpack('<Q',stream.read(8))[0]
            if not 2<=header_size<=min(16*1024**2,size-8):return False
            header=json.loads(stream.read(header_size))
        if not isinstance(header,dict) or len(header)>100000:return False
        tensors=[v for k,v in header.items() if k!='__metadata__']
        return bool(tensors) and all(isinstance(v,dict) and isinstance(v.get('data_offsets'),list)
            and len(v['data_offsets'])==2 and all(type(x) is int for x in v['data_offsets'])
            and 0<=v['data_offsets'][0]<=v['data_offsets'][1]<=size-8-header_size for v in tensors)
    except (OSError,ValueError,struct.error,TypeError):return False


def valid_weight(path):
    try:
        path=Path(path);st=path.stat()
        if not path.is_file() or st.st_size==0:return False
        if path.suffix.lower()=='.gguf':return bool(metadata(path))
        if path.suffix.lower()=='.safetensors':return _safetensors_valid(str(path),st.st_size,st.st_mtime_ns)
    except OSError:pass
    return False


def entry(role,path):
    try:size=path.stat().st_size if path.is_file() else 0
    except OSError:size=0
    return {'role':role,'path':str(path),'filename':path.name,'size':size,'valid':valid_weight(path)}


def build_model(config):
    profile=PROFILES[config['profile']]
    files=[entry(role,Path(path)) for role,path in config['files'].items() if path]
    main=Path(config['files'][profile['main']])
    info=metadata(main) if config['profile']=='chat' else {}
    shard=re.search(r'-(\d{5})-of-(\d{5})\.gguf$',main.name,re.I)
    if config['profile']=='chat' and shard:
        for i in range(2,int(shard[2])+1):
            files.append(entry('shard',main.with_name(main.name[:shard.start()]+f'-{i:05d}-of-{int(shard[2]):05d}.gguf')))
    problems=[]
    for f in files:
        if not f['valid'] and f['role']!='mmproj':
            problems.append(f"{ROLE_LABELS.get(f['role'],'Parte GGUF')}: file assente, non leggibile o formato non valido ({f['path']}).")
    if config['profile']=='chat' and info.get('general.architecture')=='clip':
        problems.append('Il file principale è un proiettore/encoder, non un modello chat.')
    if config['profile']=='chat' and int(info.get('split.count',1))>sum(f['role'] in ('model','shard') for f in files):
        problems.append('Mancano alcune parti del modello GGUF suddiviso.')
    size=sum(f['size'] for f in files)
    defaults={k:v for k,v in profile.items() if k in ('capabilities','architecture','max_refs','steps','cfg')}
    if 'steps' in config:
        defaults.pop('steps',None)
        if config['steps']:defaults['steps']=config['steps']
    if 'cfg' in config:defaults['cfg']=config['cfg']
    return defaults | {
        'id':config['id'],'name':config['name'] or str(info.get('general.name') or main.stem),
        'local':True,'external':True,'external_config':config,'files':files,'size':size,'ram_gb':round(size/1024**3+2,1),
        'description':'Collegato al percorso originale. I pesi restano nella cartella scelta.',
        'license':'Vedi la licenza dei file originali. File locali non verificati contro un hash del catalogo.',
        'external_problems':problems,'projector_mode':config.get('projector_mode','auto')}


def validate_config(body, model_id=None):
    if not isinstance(body,dict) or set(body)-{'id','profile','name','files','projector_mode','steps','cfg'}:
        raise ValueError('Collegamento modello non valido.')
    kind=body.get('profile')
    if kind not in PROFILES:raise ValueError('Scegli il tipo di modello.')
    profile=PROFILES[kind];paths=body.get('files')
    if not isinstance(paths,dict) or set(paths)-set(profile['required']+profile['optional']):
        raise ValueError('Componenti non validi per questo tipo di modello.')
    name=body.get('name','')
    if not isinstance(name,str) or len(name)>150:raise ValueError('Nome del modello troppo lungo.')
    mode=body.get('projector_mode','auto')
    if mode not in ('auto','manual','off'):raise ValueError('Selezione mmproj non valida.')
    resolved={}
    for role in profile['required']+profile['optional']:
        if role=='mmproj' and mode!='manual':continue
        value=paths.get(role,'')
        if not value:
            if role in profile['required'] or (role=='mmproj' and mode=='manual'):
                raise ValueError('Seleziona il componente: '+ROLE_LABELS[role]+'.')
            continue
        p=absolute_path(value)
        if not valid_weight(p):raise ValueError(f'{ROLE_LABELS[role]}: scegli un file GGUF o safetensors leggibile e valido.')
        if kind=='chat' and p.suffix.lower()!='.gguf':raise ValueError('Il motore chat richiede file GGUF.')
        if role=='mmproj' and metadata(p).get('general.architecture')!='clip':raise ValueError('Il mmproj non contiene metadati di un proiettore vision.')
        resolved[role]=str(p)
    main=Path(resolved[profile['main']])
    shard=re.search(r'-(\d{5})-of-(\d{5})\.gguf$',main.name,re.I)
    if shard and (int(shard[1])!=1 or not 1<=int(shard[2])<=256):
        raise ValueError('Seleziona la prima parte GGUF (00001); sono supportate fino a 256 parti.')
    ident=model_id or 'external-'+hashlib.sha256((kind+'\0'+os.path.normcase(str(main))).encode()).hexdigest()[:20]
    config={'id':ident,'profile':kind,'name':name.strip(),'files':resolved,'projector_mode':mode}
    if kind!='chat':
        steps=body.get('steps',profile.get('steps',0));cfg=body.get('cfg',profile.get('cfg',7))
        if type(steps) is not int or not 0<=steps<=100 or type(cfg) not in (int,float) or not 0<=cfg<=30:
            raise ValueError('Passi o CFG non validi.')
        config.update(steps=steps,cfg=cfg)
    model=build_model(config)
    if model['external_problems']:raise ValueError(' '.join(model['external_problems']))
    return config


def browse(body):
    """Explicit, authenticated, single-directory browsing; never recursively crawl a disk."""
    raw=body.get('path','')
    if not raw:
        roots=[Path(f'{letter}:/') for letter in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ' if Path(f'{letter}:/').exists()] if os.name=='nt' else [Path('/')]
        return {'path':'','parent':None,'entries':[{'name':str(p),'path':str(p),'directory':True} for p in roots],'truncated':False}
    p=absolute_path(raw)
    if p.is_file():p=p.parent
    if not p.is_dir():raise ValueError('Cartella non trovata o unità non disponibile.')
    items=[];truncated=False
    try:
        with os.scandir(p) as scan:
            for i,f in enumerate(scan):
                if i>=10000 or len(items)>=1000:truncated=True;break
                try:
                    is_dir=f.is_dir()
                    if is_dir or Path(f.name).suffix.lower() in EXTENSIONS:
                        items.append({'name':f.name,'path':str(p/f.name),'directory':is_dir,'size':0 if is_dir else f.stat().st_size})
                except OSError:continue
    except OSError as exc:raise ValueError('Impossibile leggere questa cartella.') from exc
    return {'path':str(p),'parent':str(p.parent) if p.parent!=p else '',
            'entries':sorted(items,key=lambda f:(not f['directory'],f['name'].casefold())),'truncated':truncated}


def suggest(body):
    kind=body.get('profile')
    if kind not in PROFILES:raise ValueError('Scegli il tipo di modello.')
    main=absolute_path(body.get('path',''))
    if not valid_weight(main):raise ValueError('Scegli un file modello GGUF o safetensors valido.')
    candidates={role:[] for role in PROFILES[kind]['required']+PROFILES[kind]['optional']}
    for i,p in enumerate(main.parent.iterdir()):
        if i>=2000:break
        if p==main or not p.is_file() or p.suffix.lower() not in EXTENSIONS:continue
        name=p.name.lower()
        role='mmproj' if 'mmproj' in name else 'llm_vision' if 'vision' in name and kind!='chat' else 'vae' if 'vae' in name else 'llm' if any(s in name for s in ('qwen','encoder','llm')) else None
        if role in candidates and valid_weight(p):candidates[role].append(str(p.resolve()))
    info=metadata(main) if kind=='chat' else {}
    return {'name':str(info.get('general.name') or main.stem),'candidates':candidates,
            'files':{k:v[0] for k,v in candidates.items() if len(v)==1 and k not in ('model','diffusion','mmproj')}}

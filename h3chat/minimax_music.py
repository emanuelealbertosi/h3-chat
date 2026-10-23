"""MiniMax Music 3 controls, separate from YuE2's score/token controls."""
import math
import secrets
from functools import lru_cache
from pathlib import Path
from .vision_runtime import SAMPLERS,SCHEDULERS

DEFAULTS={'seed':0,'max_duration':120.0,'cfg_scale':1.5,'top_k':50,
          'num_inference_steps':30,'diffusion_cfg':1.0,'sampler':'euler','scheduler':'simple'}
NUMBERS={'cfg_scale':(0,100,1.5),'top_k':(1,16384,50),'num_inference_steps':(1,128,30),'diffusion_cfg':(0,20,1.0)}
INTEGER={'top_k','num_inference_steps'}

def validate(value,*,partial=False):
    if not isinstance(value,dict) or set(value)-set(DEFAULTS):raise ValueError('Parametri MiniMax Music 3 non riconosciuti.')
    result=DEFAULTS|value
    if type(result['seed']) is not int or not -1<=result['seed']<2**53:raise ValueError('Seed musica non valido.')
    for k,(lo,hi,_) in NUMBERS.items():
        v=result[k]
        if type(v) not in (int,float) or not math.isfinite(v) or not lo<=v<=hi or (k in INTEGER and type(v) is not int):raise ValueError('MiniMax Music: parametro fuori intervallo '+k)
    seconds=result['max_duration']
    if seconds is not None and (type(seconds) not in (int,float) or not math.isfinite(seconds) or not .04<=seconds<=360):raise ValueError('MiniMax Music: durata massima da 0,04 a 360 secondi.')
    if result['sampler'] not in SAMPLERS or result['scheduler'] not in SCHEDULERS or result['scheduler']=='qwen21_turbo':raise ValueError('Sampler o scheduler musica non valido.')
    return dict(value) if partial else result

def options(model,settings,*,randomize=True):
    value=validate(settings.get('music_overrides',{}).get(model['id'],{}))
    if value['max_duration'] is None:value['max_duration']=DEFAULTS['max_duration']
    if value['sampler']=='auto':value['sampler']='euler'
    if value['scheduler']=='auto':value['scheduler']='simple'
    if randomize and value['seed']==-1:value['seed']=secrets.randbelow(2**31)
    return value

@lru_cache(maxsize=32)
def weight_names(path,size,stamp):
    import json,struct
    try:
        with open(path,'rb') as stream:
            count=struct.unpack('<Q',stream.read(8))[0]
            header=json.loads(stream.read(count)) if 0<count<32*1024**2 else {}
        return frozenset(header)
    except (OSError,ValueError,struct.error):return frozenset()

def weight_problems(files):
    anchors={'diffusion':'cond_layer_logits','llm':'model.audio_decoder.projection.weight','vae':'dec_in_proj.weight'}
    problems=[]
    for role,anchor in anchors.items():
        try:
            stat=Path(files[role]).stat();header=weight_names(files[role],stat.st_size,stat.st_mtime_ns)
        except OSError:header={}
        if anchor not in header:problems.append('MiniMax Music 3: componente non riconosciuto ('+role+').')
    return problems

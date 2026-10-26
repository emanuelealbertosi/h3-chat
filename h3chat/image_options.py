"""Image controls supported by the pinned stable-diffusion.cpp 7f410a3 ABI."""
import secrets
import math
import re
from .vision_runtime import SAMPLERS as VISION_SAMPLERS, SCHEDULERS as VISION_SCHEDULERS, validate_options

SAMPLERS = ('auto','euler','euler_a','heun','dpm2','dpm++2s_a','dpm++2m','dpm++2mv2',
            'ipndm','ipndm_v','lcm','ddim_trailing','tcd','res_multistep','res_2s','er_sde',
            'euler_cfg_pp','euler_a_cfg_pp','euler_ge','dpm++2m_sde','dpm++2m_sde_bt','lms')
SCHEDULERS = ('auto','discrete','karras','exponential','ays','gits','sgm_uniform','simple',
              'smoothstep','kl_optimal','lcm','bong_tangent','logit_normal','flux2','flux','beta')


NATIVE_SAMPLERS, NATIVE_SCHEDULERS = SAMPLERS, SCHEDULERS
SAMPLERS = tuple(dict.fromkeys(SAMPLERS + VISION_SAMPLERS))
SCHEDULERS = tuple(dict.fromkeys(SCHEDULERS + VISION_SCHEDULERS))

ASPECTS=('auto','1:1','16:9','9:16','4:3','3:4','3:2','2:3')
IMAGE_DEFAULT_KEYS=('width','height','steps','image_cfg','image_sampler','image_scheduler','seed','negative_prompt','strength','image_aspect')
OVERRIDE_KEYS=('width','height','steps','cfg','sampler','scheduler','seed','negative_prompt','strength','aspect','megapixels','moss_turbo','moss_turbo_previous')
MOSS_NEGATIVE_PROMPT = 'low quality, blurry, jpeg artifacts, bad anatomy, malformed hands, extra fingers, missing fingers, extra limbs, distorted face'


def configured(model, settings):
    sampler=model.get('sampler','auto')
    scheduler=model.get('scheduler','auto')
    if sampler=='auto':sampler=settings.get('image_sampler','auto')
    if scheduler=='auto':scheduler=settings.get('image_scheduler','auto')
    result={'width':model.get('width',settings['width']),'height':model.get('height',settings['height']),'steps':model.get('steps',settings['steps']),
            'cfg':model.get('cfg',settings.get('image_cfg',7)),'sampler':sampler,'scheduler':scheduler,
            'seed':settings.get('seed',-1),'negative_prompt':settings.get('negative_prompt','') or (MOSS_NEGATIVE_PROMPT if model.get('architecture')=='moss' else ''),
            'strength':model.get('strength',settings['strength']),'aspect':settings.get('image_aspect','auto')}
    if model.get('architecture')=='qwen-edit':result['flow_shift']=3
    result.update(settings.get('image_overrides',{}).get(model.get('id',''),{}))
    return result


def capture_request(model,settings,value):
    """Snapshot chat-local image controls without saving global preferences."""
    value=dict(value)
    for key,choices in (('sampler',SAMPLERS),('scheduler',SCHEDULERS)):
        supplied=value.get(key)
        if isinstance(supplied,str) and supplied.casefold() in choices:value[key]=supplied.casefold()
    validate_overrides({model['id']:value},{model['id']:model})
    overrides=settings.get('image_overrides',{})
    captured=settings|{'image_overrides':overrides|{model['id']:overrides.get(model['id'],{})|dict(value)}}
    options(model,captured)
    return captured|{'_image_request_parameters':{k:v for k,v in configured(model,captured).items() if k in OVERRIDE_KEYS}}


def apply_aspect(result,prompt='',model=None):
    moss=(model or {}).get('architecture')=='moss'
    limit=4096 if moss else 1536
    grid=1 if moss else 64
    # Explicit canvas dimensions also override an editing reference's shape.
    dimensions=re.findall(r'(?<!\d)(\d{3,4})\s*[x×*]\s*(\d{3,4})(?!\d)',prompt,re.I)
    if dimensions:
        width,height=map(int,dimensions[-1])
        if any(n<256 or n>limit or n%grid for n in (width,height)) or (moss and width*height>4_194_304):
            if moss:raise ValueError('MOSS: dimensioni tra 256 e 4096 pixel e massimo circa 4,2 MP. La richiesta non viene ridotta automaticamente.')
            raise ValueError('Dimensioni immagine: scegli da 256 a 1536 pixel, in multipli di 64 (es. 1024x576).')
        divisor=math.gcd(width,height);aspect=f'{width//divisor}:{height//divisor}'
        result.update(width=width,height=height,megapixels=width*height/1_000_000,aspect=aspect if aspect in ASPECTS else 'auto',preserve_reference_aspect=False)
        return result
    aspect=result.get('aspect','auto')
    matches=re.findall(r'(?<!\d)(16|9|4|3|2|1)\s*[:/]\s*(16|9|4|3|2|1)(?!\d)',prompt)
    requested=next((f'{a}:{b}' for a,b in reversed(matches) if f'{a}:{b}' in ASPECTS),None)
    if requested:aspect=requested
    elif re.search(r'\b(quadrat[ao]|square)\b',prompt,re.I):aspect='1:1'
    elif re.search(r'\b(verticale|vertical|portrait format)\b',prompt,re.I):aspect='9:16'
    elif re.search(r'\b(orizzontale|horizontal|landscape format)\b',prompt,re.I):aspect='16:9'
    if aspect not in ASPECTS:raise ValueError('Formato immagine non valido.')
    result['aspect']=aspect;result['preserve_reference_aspect']=aspect=='auto'
    mp=re.findall(r'(?<![\d.])(\d+(?:[.,]\d+)?)\s*(?:MP|megapixel(?:s)?)\b',prompt,re.I)
    target=float(mp[-1].replace(',','.')) if mp else result.get('megapixels')
    if target is not None and (not isinstance(target,(int,float)) or not math.isfinite(target) or not .25<=target<=4):raise ValueError('Megapixel immagine: scegli da 0,25 a 4 MP.')
    if moss or target is not None:
        area=target*1_000_000 if target is not None else result['width']*result['height']
        a,b=map(int,aspect.split(':')) if aspect!='auto' else (result['width'],result['height'])
        ratio=a/b
        width=math.ceil(math.sqrt(area*ratio)/grid)*grid;height=math.ceil(area/width/grid)*grid
        if moss and aspect!='auto':
            k=math.ceil(math.sqrt(area/(a*b)));width,height=a*k,b*k
        if max(width,height)>4096:raise ValueError('Formato troppo estremo per i megapixel scelti.')
        result.update(width=width,height=height,megapixels=area/1_000_000)
        return result
    if aspect!='auto':
        a,b=map(int,aspect.split(':'));area=result['width']*result['height']
        pairs=[(a*k*64,b*k*64) for k in range(1,25) if 256<=a*k*64<=1536 and 256<=b*k*64<=1536]
        result['width'],result['height']=min(pairs,key=lambda p:abs(math.log(p[0]*p[1]/area)))
    return result


def options(model, settings,prompt=''):
    result=configured(model,settings)
    from .moss_dmd2 import effective,requested as requested_turbo
    turbo=requested_turbo(prompt,moss=model.get('architecture')=='moss')
    if turbo is not None:
        if turbo and model.get('architecture')!='moss':raise ValueError('È stato richiesto MOSS Turbo, ma il modello scelto non è MOSS. Nessuna sostituzione automatica.')
        if not turbo and result.get('moss_turbo') and result.get('moss_turbo_previous'):result.update(result['moss_turbo_previous'])
        result['moss_turbo']=turbo
    result=effective(result)
    requested={}
    for key,pattern in (
        ('steps',r'\b(?:steps?|passi)\s*[:=]?\s*(\d+)\b|\b(\d+)\s*(?:steps?|passi)\b(?!\s*[:=]?\s*\d)'),
        ('seed',r'\bseed\s*[:=]?\s*(?:(?:fisso|fixed)\s*[:=]?\s*)?(-?\d+|casuale|casuali|random(?:ico|ica|ized)?)\b'),
        ('cfg',r'\bCFG\s*[:=]?\s*(\d+(?:[.,]\d+)?)\b'),
        ('strength',r'\b(?:strength|denoise|intensit[aà])\s*[:=]?\s*(\d+(?:[.,]\d+)?)\b'),
        ('sampler',r'\bsampler\s*[:=]?\s*([a-z0-9_+.-]+)'),
        ('scheduler',r'\bscheduler\s*[:=]?\s*([a-z0-9_+.-]+)')):
        matches=list(re.finditer(pattern,prompt,re.I))
        if matches:
            value=next(x for x in matches[-1].groups() if x is not None)
            requested[key]=(-1 if key=='seed' and not re.fullmatch(r'-?\d+',value) else int(value)) if key in ('steps','seed') else float(value.replace(',','.')) if key in ('cfg','strength') else value.lower().rstrip('.')
    if requested:
        validate_overrides({'prompt':requested});result.update(requested)
    if result['sampler']=='auto' and model.get('architecture') in ('flux2','qwen-edit','anima'):result['sampler']='euler'
    if model.get('engine')=='vision':
        if result['sampler']=='auto':result['sampler']='euler'
        if result['scheduler']=='auto':result['scheduler']=model.get('scheduler') if model.get('scheduler') in VISION_SCHEDULERS and model.get('scheduler')!='auto' else 'simple'
    validate_options(model,result)
    if model.get('engine')!='vision' and (result['sampler'] not in NATIVE_SAMPLERS or result['scheduler'] not in NATIVE_SCHEDULERS):
        raise ValueError('Sampler o scheduler non supportato dal motore immagini selezionato.')
    if result['seed']<0:result['seed']=secrets.randbits(31)
    return apply_aspect(result,prompt,model)


def validate_overrides(value,models=None):
    import math
    if not isinstance(value,dict) or len(value)>100:raise ValueError('Troppe personalizzazioni immagini.')
    for ident,settings in value.items():
        if not isinstance(ident,str) or not 1<=len(ident)<=100 or not isinstance(settings,dict) or set(settings)-set(OVERRIDE_KEYS):raise ValueError('Personalizzazione immagine non valida.')
        moss=(models or {}).get(ident,{}).get('architecture')=='moss'
        from .moss_dmd2 import validate as validate_turbo
        validate_turbo(settings,moss if models is not None else None)
        limit=4096 if moss else 1536
        for key,lo,hi in (('width',256,limit),('height',256,limit),('steps',1,100),('seed',-1,2147483647)):
            if key in settings and (type(settings[key]) is not int or not lo<=settings[key]<=hi):raise ValueError(f'{key}: intero tra {lo} e {hi}.')
        for key in ('width','height'):
            if key in settings and not moss and settings[key]%64:raise ValueError('Le dimensioni devono essere multipli di '+'64.')
        for key,lo,hi in (('cfg',0,30),('strength',.05,1),('megapixels',.25,4)):
            if key in settings and (type(settings[key]) not in (int,float) or not math.isfinite(settings[key]) or not lo<=settings[key]<=hi):raise ValueError(key+' fuori intervallo.')
        if settings.get('sampler','auto') not in SAMPLERS or settings.get('scheduler','auto') not in SCHEDULERS:raise ValueError('Sampler o scheduler non supportato.')
        if settings.get('aspect','auto') not in ASPECTS:raise ValueError('Formato immagine non valido.')
        if 'negative_prompt' in settings and (not isinstance(settings['negative_prompt'],str) or len(settings['negative_prompt'])>8000):raise ValueError('Negative prompt non valido.')


def family(model):
    arch=model.get('architecture','')
    if model.get('lora_family'):return model['lora_family']
    if model.get('id')=='sd15':return 'sd15'
    if model.get('external_config',{}).get('profile')=='krea2':return 'krea2'
    if model.get('external_config',{}).get('profile')=='sdxl':return 'sdxl'
    return 'qwen-image' if arch=='qwen-edit' else arch


def compatible(lora_family, model):
    target=family(model)
    if not lora_family:return False
    if target=='sd':return False
    return lora_family==target

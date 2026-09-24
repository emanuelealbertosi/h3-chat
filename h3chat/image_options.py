"""Image controls supported by the pinned stable-diffusion.cpp 7f410a3 ABI."""
import secrets
from .vision_runtime import SAMPLERS as VISION_SAMPLERS, SCHEDULERS as VISION_SCHEDULERS, validate_options

SAMPLERS = ('auto','euler','euler_a','heun','dpm2','dpm++2s_a','dpm++2m','dpm++2mv2',
            'ipndm','ipndm_v','lcm','ddim_trailing','tcd','res_multistep','res_2s','er_sde',
            'euler_cfg_pp','euler_a_cfg_pp','euler_ge','dpm++2m_sde','dpm++2m_sde_bt','lms')
SCHEDULERS = ('auto','discrete','karras','exponential','ays','gits','sgm_uniform','simple',
              'smoothstep','kl_optimal','lcm','bong_tangent','logit_normal','flux2','flux','beta')


NATIVE_SAMPLERS, NATIVE_SCHEDULERS = SAMPLERS, SCHEDULERS
SAMPLERS = tuple(dict.fromkeys(SAMPLERS + VISION_SAMPLERS))
SCHEDULERS = tuple(dict.fromkeys(SCHEDULERS + VISION_SCHEDULERS))

IMAGE_DEFAULT_KEYS=('width','height','steps','image_cfg','image_sampler','image_scheduler','seed','negative_prompt','strength')
OVERRIDE_KEYS=('width','height','steps','cfg','sampler','scheduler','seed','negative_prompt','strength')


def configured(model, settings):
    sampler=model.get('sampler','auto')
    scheduler=model.get('scheduler','auto')
    if sampler=='auto':sampler=settings.get('image_sampler','auto')
    if scheduler=='auto':scheduler=settings.get('image_scheduler','auto')
    result={'width':model.get('width',settings['width']),'height':model.get('height',settings['height']),'steps':model.get('steps',settings['steps']),
            'cfg':model.get('cfg',settings.get('image_cfg',7)),'sampler':sampler,'scheduler':scheduler,
            'seed':settings.get('seed',-1),'negative_prompt':settings.get('negative_prompt',''),
            'strength':model.get('strength',settings['strength'])}
    if model.get('architecture')=='qwen-edit':result['flow_shift']=3
    result.update(settings.get('image_overrides',{}).get(model.get('id',''),{}))
    return result


def options(model, settings):
    result=configured(model,settings)
    if result['sampler']=='auto' and model.get('architecture') in ('flux2','qwen-edit','anima'):result['sampler']='euler'
    if model.get('engine')=='vision':
        if result['sampler']=='auto':result['sampler']='euler'
        if result['scheduler']=='auto':result['scheduler']='simple'
    validate_options(model,result)
    if model.get('engine')!='vision' and (result['sampler'] not in NATIVE_SAMPLERS or result['scheduler'] not in NATIVE_SCHEDULERS):
        raise ValueError('Sampler o scheduler non supportato dal motore immagini selezionato.')
    if result['seed']<0:result['seed']=secrets.randbits(31)
    return result


def validate_overrides(value):
    import math
    if not isinstance(value,dict) or len(value)>100:raise ValueError('Troppe personalizzazioni immagini.')
    for ident,settings in value.items():
        if not isinstance(ident,str) or not 1<=len(ident)<=100 or not isinstance(settings,dict) or set(settings)-set(OVERRIDE_KEYS):raise ValueError('Personalizzazione immagine non valida.')
        for key,lo,hi in (('width',256,1536),('height',256,1536),('steps',1,100),('seed',-1,2147483647)):
            if key in settings and (type(settings[key]) is not int or not lo<=settings[key]<=hi):raise ValueError(f'{key}: intero tra {lo} e {hi}.')
        for key in ('width','height'):
            if key in settings and settings[key]%64:raise ValueError('Le dimensioni devono essere multipli di 64.')
        for key,lo,hi in (('cfg',0,30),('strength',.05,1)):
            if key in settings and (type(settings[key]) not in (int,float) or not math.isfinite(settings[key]) or not lo<=settings[key]<=hi):raise ValueError(key+' fuori intervallo.')
        if settings.get('sampler','auto') not in SAMPLERS or settings.get('scheduler','auto') not in SCHEDULERS:raise ValueError('Sampler o scheduler non supportato.')
        if 'negative_prompt' in settings and (not isinstance(settings['negative_prompt'],str) or len(settings['negative_prompt'])>8000):raise ValueError('Negative prompt non valido.')


def family(model):
    arch=model.get('architecture','')
    if model.get('id')=='sd15':return 'sd15'
    if model.get('external_config',{}).get('profile')=='sdxl':return 'sdxl'
    return 'qwen-image' if arch=='qwen-edit' else arch


def compatible(lora_family, model):
    target=family(model)
    if not lora_family:return True
    if target=='sd':return lora_family in ('sd15','sdxl','sd2')
    return lora_family==target

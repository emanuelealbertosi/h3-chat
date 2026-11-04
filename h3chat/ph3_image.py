"""P-H3-Image's published eight-step recipe and isolated optional runtime."""
from pathlib import Path

CORE_REVISION='edc480ac44de8714b4008810bc68393a5c22f937'
SIGMAS=(1.0,.984753,.967905,.951688,.925372,.881923,.810083,.528718,0.0)
SCHEDULER='ph3_image'


def ready(root):
    import json
    folder=Path(root)/'runtime/ph3'
    try:revision=json.loads((folder/'provenance.json').read_text())['revision']
    except (OSError,ValueError,KeyError):return False
    return revision==CORE_REVISION and all((folder/p).is_file() for p in (
        'core/comfy_extras/nodes_minimax_h3.py','core/comfy/text_encoders/minimax.py',
        'packages/comfy_kitchen/__init__.py','packages/comfy_aimdo/control.py'))


def validate(model,value):
    if model.get('architecture')!='ph3':
        if value.get('scheduler')==SCHEDULER:raise ValueError('Lo scheduler P-H3 richiede il modello P-H3-Image.')
        return
    if value.get('steps')!=8 or value.get('cfg')!=1 or value.get('sampler')!='euler' or value.get('scheduler')!=SCHEDULER:
        raise ValueError('P-H3-Image usa la ricetta ufficiale: 8 passi, CFG 1, Euler, scheduler P-H3.')
    if value.get('negative_prompt'):value['negative_prompt']=''


def upsample_input(prompt,width,height):
    from math import gcd
    d=gcd(width,height)
    return f'Aspect ratio: {width//d}:{height//d}\nRequest: {prompt}'


def apply_loras(model,adapters,comfy):
    """Patch a request-local clone, reject zero matches and report actual patches."""
    applied=[]
    for adapter in adapters:
        if not adapter['weight']:continue
        weights,metadata=comfy.utils.load_torch_file(adapter['path'],safe_load=True,return_metadata=True)
        before=sum(len(v) for v in model.patches.values())
        model,_=comfy.sd.load_lora_for_models(model,None,weights,adapter['weight'],0,metadata)
        count=sum(len(v) for v in model.patches.values())-before
        if count<=0:raise ValueError('LoRA senza tensori compatibili con P-H3: '+Path(adapter['path']).name)
        applied.append({'name':Path(adapter['path']).name,'weight':adapter['weight'],'applied_patches':count})
    return model,applied

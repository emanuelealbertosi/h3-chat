"""Pinned optional MOSS plugin; no changes to the shared Comfy core."""
from pathlib import Path
import importlib
import sys
import types
import json
import math
import re

REVISION='c1355e6b1986dfe8fba3c0455783a05899212342'

def loaders(root):
    folder=Path(root)/'runtime/vision/moss_image'
    if not all((folder/name).is_file() for name in ('loaders.py','model.py','text_encoder.py')):
        raise ValueError('Installa il componente opzionale MOSS-Image prima di usare questo modello.')
    # The upstream __init__ registers UI nodes. Headless inference only needs
    # its inspected model/encoder modules, not the external app entrypoint.
    name='h3_moss_image_plugin'
    if name not in sys.modules:
        package=types.ModuleType(name);package.__path__=[str(folder)];sys.modules[name]=package
    return importlib.import_module(name+'.loaders')

def unpack_qkv(state):
    """Losslessly unpack Comfy's fused QKV, including per-output INT8 scales."""
    state=dict(state)
    for key in list(state):
        if key.endswith('.comfy_attention.config'):
            annotation=json.loads(bytes(state.pop(key).tolist()))
            if set(annotation)!={'attention'}:raise ValueError('Metadati attenzione MOSS non riconosciuti.')
        if not re.fullmatch(r'layers\.\d+\.proj\.qkv\.weight',key):continue
        stem=key.removesuffix('weight');weight=state.pop(key)
        if len(weight.shape)!=2 or weight.shape[0]!=3*weight.shape[1]:raise ValueError('Proiezione QKV MOSS non valida.')
        dim=weight.shape[1];descriptor=state.pop(stem+'comfy_quant',None);scale=state.pop(stem+'weight_scale',None);bias=state.pop(stem+'bias',None)
        if descriptor is not None:
            spec=json.loads(bytes(descriptor.tolist()))
            if spec.get('format')!='int8_tensorwise' or scale is None:raise ValueError('QKV MOSS quantizzato non supportato: scegli INT8 o FP16/BF16.')
            if math.prod(scale.shape)!=1 and scale.shape[0]!=3*dim:raise ValueError('Scale QKV MOSS non valide.')
        for index,name in enumerate(('q','k','v')):
            target=stem.removesuffix('qkv.')+name+'.'
            state[target+'weight']=weight[index*dim:(index+1)*dim]
            if descriptor is not None:state[target+'comfy_quant']=descriptor
            if scale is not None:state[target+'weight_scale']=scale if math.prod(scale.shape)==1 else scale[index*dim:(index+1)*dim]
            if bias is not None:state[target+'bias']=bias[index*dim:(index+1)*dim]
    return state

def load_diffuser(root,path,dtype='default'):
    import comfy.model_base
    import comfy.utils
    plugin=loaders(root)
    state,metadata=comfy.utils.load_torch_file(path,safe_load=True,return_metadata=True)
    state=unpack_qkv(state)
    original=comfy.model_base.BaseModel.load_model_weights
    def strict(model,weights,unet_prefix='',assign=False):
        selected={k[len(unet_prefix):]:weights.pop(k) for k in list(weights) if k.startswith(unet_prefix)}
        selected=model.model_config.process_unet_state_dict(selected)
        # Never produce an image with silently missing/random projection weights.
        model.diffusion_model.load_state_dict(selected,strict=True,assign=assign)
        return model
    comfy.model_base.BaseModel.load_model_weights=strict
    try:return plugin.load_model_state(state,plugin.DTYPES[dtype],True,metadata=metadata)
    finally:comfy.model_base.BaseModel.load_model_weights=original

def sampling(model,turbo=False):
    import comfy.model_sampling
    import comfy.model_patcher
    import comfy.samplers
    class Sampling(comfy.model_sampling.ModelSamplingDiscreteFlow,comfy.model_sampling.CONST):pass
    configured=model.clone();flow=Sampling(model.model.model_config);flow.set_parameters(shift=5,multiplier=1000)
    configured.add_object_patch('model_sampling',flow)
    if turbo:return configured
    # Official workflow: Simple SLG, only the negative branch skips block 22.
    # Adapted from ComfyUI nodes_slg.py (GPL-3.0).
    def skip(args,extra):return args
    def calc(args):
        positive,negative=args['conds'];options=args['model_options']
        sigma=args['sigma'][0].item()
        if negative is None or sigma<flow.percent_to_sigma(1) or sigma>flow.percent_to_sigma(0):return comfy.samplers.calc_cond_batch(args['model'],args['conds'],args['input'],args['sigma'],options)
        modified=comfy.model_patcher.set_model_options_patch_replace(options.copy(),skip,'dit','single_block',22)
        pos,_=comfy.samplers.calc_cond_batch(args['model'],[positive,None],args['input'],args['sigma'],options)
        _,neg=comfy.samplers.calc_cond_batch(args['model'],[None,negative],args['input'],args['sigma'],modified)
        return [pos,neg]
    configured.set_model_sampler_calc_cond_batch_function(calc)
    return configured

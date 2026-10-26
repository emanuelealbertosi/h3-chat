"""The optional image runtime belongs entirely to this application directory."""
import json
import os
from pathlib import Path

REVISION = '3b4c0b0e457cf0a51cf3038e0a6750d8f96ce251'
SAMPLERS = ('auto', 'euler', 'euler_ancestral', 'heun', 'dpm_2', 'dpmpp_2m', 'dpmpp_2m_sde', 'dpmpp_sde', 'res_multistep', 'lcm')
SCHEDULERS = ('auto', 'simple', 'normal', 'karras', 'exponential', 'sgm_uniform', 'ddim_uniform', 'beta', 'linear_quadratic', 'kl_optimal', 'qwen21_turbo')


def status(root):
    folder = Path(root) / 'runtime/vision'
    try:
        marker = json.loads((folder / 'ready.json').read_text(encoding='utf-8'))
        required=['core/comfy/sd.py','core/comfy/text_encoders/ming_image.py','core/comfy_extras/nodes_minimax_h3.py','core/comfy/text_encoders/minimax.py','packages/torch/__init__.py','packages.json']
        if os.name=='nt':required+=['dlls/msvcp140.dll']
        ready = marker.get('core_revision') == REVISION and all((folder / name).is_file() for name in required)
    except (OSError, ValueError):
        ready = False
    headers=['runtime/python/include/Python.h','runtime/python/libs/python313.lib'] if os.name=='nt' else ['runtime/python/include/python3.13/Python.h']
    accelerated=ready and all((Path(root)/name).is_file() for name in ('runtime/vision/packages/sageattention/__init__.py','runtime/vision/packages/triton/__init__.py',*headers))
    return {'ready':ready, 'accelerated':accelerated, 'backends':['cuda','cpu'], 'revision':REVISION,
            'note':'Motore integrato Ming / Qwen Image 2.1 / Krea 2 · NVIDIA CUDA o CPU. Nessun server esterno.'}


def validate_options(model, options):
    if model.get('engine') != 'vision':
        return
    if options['sampler'] not in SAMPLERS or options['scheduler'] not in SCHEDULERS:
        raise ValueError('Sampler o scheduler non supportato da Ming / Qwen Image 2.1 / Krea 2. Usa Euler e Simple oppure i valori disponibili per questo modello.')
    from .qwen_image21 import validate_schedule
    validate_schedule(model.get('architecture'),options)
    # MOSS uses actual img2img latent blending. Other native Edit models use
    # reference-conditioned generation and retain their full denoise schedule.
    if model.get('architecture')=='moss':
        value=options.get('strength',.65)
        if type(value) not in (int,float) or not .05<=value<=1:raise ValueError('Intensità MOSS img2img: scegli da 0,05 a 1.')
    else:options['strength'] = 1.0

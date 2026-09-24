"""The optional image runtime belongs entirely to this application directory."""
import json
from pathlib import Path

REVISION = '3b4c0b0e457cf0a51cf3038e0a6750d8f96ce251'
SAMPLERS = ('auto', 'euler', 'euler_ancestral', 'heun', 'dpm_2', 'dpmpp_2m', 'dpmpp_2m_sde', 'dpmpp_sde', 'lcm')
SCHEDULERS = ('auto', 'simple', 'normal', 'karras', 'exponential', 'sgm_uniform', 'ddim_uniform', 'beta', 'linear_quadratic', 'kl_optimal')


def status(root):
    folder = Path(root) / 'runtime/vision'
    try:
        marker = json.loads((folder / 'ready.json').read_text(encoding='utf-8'))
        ready = marker.get('core_revision') == REVISION and all((folder / name).is_file() for name in (
            'core/comfy/sd.py', 'core/comfy/text_encoders/ming_image.py', 'packages/torch/__init__.py', 'packages.json', 'dlls/msvcp140.dll'))
    except (OSError, ValueError):
        ready = False
    return {'ready':ready, 'backends':['cuda','cpu'], 'revision':REVISION,
            'note':'Motore integrato Ming / Qwen Image 2.1 · NVIDIA CUDA o CPU. Nessun server esterno.'}


def validate_options(model, options):
    if model.get('engine') != 'vision':
        return
    if options['sampler'] not in SAMPLERS or options['scheduler'] not in SCHEDULERS:
        raise ValueError('Sampler o scheduler non supportato da Ming / Qwen Image 2.1. Usa Euler e Simple oppure i valori disponibili per questo modello.')
    # Native editing is reference-conditioned generation, not latent blending.
    options['strength'] = 1.0

"""Optional, pinned VEDA adapter. No Torch imports in the web process."""
import json
import hashlib
import struct
import sys
from pathlib import Path
from .vision_runtime import status as vision_status

REVISION = '60bfae688897dc41bc8685ca9f3130d7ed8f3b0c'
PREDICTOR = 'minimax_h3_t2va_veda_8nfe_600step_preview_fp8.safetensors'

def manifest_digest(root):
    files=json.loads((Path(root)/'runtimes.json').read_text(encoding='utf-8'))['veda']['files']
    return hashlib.sha256(json.dumps(files,sort_keys=True).encode()).hexdigest()

def mark_ready(root):
    marker=Path(root)/'runtime/veda/ready.json';marker.parent.mkdir(parents=True,exist_ok=True)
    part=marker.with_suffix('.writing');part.write_text(json.dumps({'manifest':manifest_digest(root)}),encoding='utf-8');part.replace(marker)

def status(root):
    folder = Path(root)/'runtime/veda'/REVISION
    try:verified=json.loads((Path(root)/'runtime/veda/ready.json').read_text(encoding='utf-8')).get('manifest')==manifest_digest(root)
    except (OSError,ValueError,KeyError):verified=False
    ready = verified and vision_status(root)['accelerated'] and all((folder/name).is_file() for name in (
        'veda_comfy/comfy_patch.py', 'veda_comfy/core/bundle.py',
        'veda_comfy/kernels/sage/sparse_int8.py', 'LICENSE', 'NOTICE.md'))
    return {'ready':ready, 'revision':REVISION,
            'predictor':str(Path(root)/'models/veda'/PREDICTOR),
            'predictor_ready':(Path(root)/'models/veda'/PREDICTOR).is_file()}

def predictor_path(root, value=''):
    if value:
        from .external_models import absolute_path
        path = absolute_path(value)
    else:path = Path(root)/'models/veda'/PREDICTOR
    try:
        if path.suffix.lower()!='.safetensors':raise ValueError('Scegli un predictor VEDA safetensors.')
        with path.open('rb') as source:
            prefix=source.read(8)
            if len(prefix)!=8:raise ValueError('Predictor VEDA incompleto.')
            size=struct.unpack('<Q',prefix)[0]
            if not 0<size<=4_000_000 or size+8>path.stat().st_size:raise ValueError('Header predictor VEDA non valido.')
            metadata=json.loads(source.read(size)).get('__metadata__',{})
        if metadata.get('format')!='miowtion-veda-predictor-v1':raise ValueError('Il file scelto non è un predictor VEDA.')
    except OSError as error:raise ValueError('Predictor VEDA mancante. Installa VEDA dalle impostazioni video oppure collega il file originale.') from error
    except (AttributeError,TypeError) as error:raise ValueError('Header predictor VEDA non valido.') from error
    return path.resolve()

def preflight(root, opts):
    if opts.get('attention')!='veda':return
    if not status(root)['ready']:raise ValueError('VEDA non installato. Usa «Installa VEDA» nelle impostazioni video, oppure scegli Auto / Sage.')
    predictor_path(root,opts.get('veda_predictor',''))

def attach(root, model, opts, chunks, emit):
    """Clone only the patcher; VEDA groups sparse and declined dense calls."""
    sys.path.insert(0,str(Path(root)/'runtime/veda'/REVISION))
    from veda_comfy import comfy_patch, settings, backends
    from veda_comfy.core.bundle import load_bundle
    import torch
    bundle=load_bundle(str(predictor_path(root,opts.get('veda_predictor',''))))
    diffusion=model.get_model_object('diffusion_model');attention=diffusion.blocks[0].attn
    if (len(diffusion.blocks),attention.heads,attention.head_dim)!=(bundle.num_layers,bundle.num_heads,bundle.head_dim):
        raise ValueError('Il predictor VEDA non corrisponde ai blocchi e alle teste di questo modello MiniMax H3.')
    config=settings.VedaSettings(
        generated=settings.parse_sparsity(str(opts.get('veda_sparsity',90))+'%','video'),
        reference=settings.parse_sparsity(str(opts.get('veda_reference_sparsity',90))+'%','riferimenti'))
    patched,patch=comfy_patch.apply(model,bundle,config,None)
    # The upstream engine owns the sparse head splitting; do not feed it a
    # partial set of heads. VEDA also groups calls declined to plain Sage.
    patched.model_options['transformer_options']['veda_held_head_chunks']=chunks
    patch.h3_result={'sparse_calls':0,'dense_calls':0,'fallback_reason':'','summary':''}
    original_cleanup=patch.on_cleanup
    def cleanup():
        calls=patch.run.calls
        if calls:
            patch.h3_result['sparse_calls']+=calls.get('sparse',0)
            patch.h3_result['dense_calls']+=sum(v for k,v in calls.items() if k not in ('sparse','other attention'))
            patch.h3_result['summary']=patch._summary() or ''
            if patch.run.failed:patch.h3_result['fallback_reason']=patch.run.failed
            elif not calls.get('sparse'):patch.h3_result['fallback_reason']=', '.join(k for k in calls if k!='other attention')
        original_cleanup()
    patch.on_cleanup=cleanup
    resolution=backends.resolve(torch.device('cuda:0'))
    if resolution.backend is None:
        patch.h3_result['fallback_reason']=resolution.report()
        emit('stage',message='Video · VEDA non disponibile su questa GPU · uso attenzione standard')
    else:emit('stage',message='Video · VEDA pronta · '+resolution.backend.display)
    return patched,patch

def report(patch):
    if patch is None:return {}
    result=dict(patch.h3_result)
    # Sampling normally invokes ON_CLEANUP. Capture a remaining run for callers
    # that omit cleanup, without mislabelling a skipped override as active.
    calls=patch.run.calls
    if calls:
        result['sparse_calls']+=calls.get('sparse',0)
        result['dense_calls']+=sum(v for k,v in calls.items() if k not in ('sparse','other attention'))
        result['summary']=patch._summary() or result['summary']
        result['fallback_reason']=patch.run.failed or result['fallback_reason']
    result['active']=result['sparse_calls']>0
    if not result['active'] and not result['fallback_reason']:result['fallback_reason']='Nessuna chiamata MiniMax H3 compatibile ha usato VEDA.'
    return result

def release(patch):
    """Free predictor/workspaces immediately, including resident-mode switches."""
    if patch is None:return
    patch._engines.clear();patch._timers.clear();patch.bundle=None
    patch.installed.clear()

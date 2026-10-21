"""Opt-in LongTakeNoCuts: bounded motion context and a latent refine pass.

No Torch import on the HTTP host. Context comes from the *delivered* tail,
never the model's padded, undisplayed frames. It sits before the next clip's
origin so soundtrack offsets and the editable timeline remain unchanged.
"""
import hashlib
import json
from pathlib import Path

VERSION = 1
CONTEXT_FRAMES = 22
REFINE_STEPS = 5
DENOISE = .55
UPSTREAM = '0cad00ab92e4ad8de3d54ddd5254142bccb702d9'


def validate(parameters):
    enabled=parameters.get('longtake_enabled',False)
    if type(enabled) is not bool:raise ValueError('LongTakeNoCuts: scegli attivo o disattivo.')
    if enabled and parameters.get('pdd_enabled'):
        raise ValueError('LongTakeNoCuts sperimentale richiede passi standard: disattiva PDD.')


def signature(files,opts):
    # LoRA/seed/prompt can change intentionally at a join; the base model and
    # native canvas cannot. File signatures prevent context after replacement.
    assets=[]
    for key in ('diffusion','vae'):
        path=Path(files[key]);stat=path.stat()
        assets.append([key,str(path.resolve()),stat.st_size,stat.st_mtime_ns])
    return hashlib.sha256(json.dumps([VERSION,assets,opts['width'],opts['height']],sort_keys=True).encode()).hexdigest()


def fingerprint(path):
    path=Path(path);stat=path.stat()
    return {'path':str(path.resolve()),'size':stat.st_size,'mtime_ns':stat.st_mtime_ns}


def predecessor(data,parameters):
    """Resolve only the selected version's immutable context, never neighbours."""
    report=parameters.get('longtake') or {}
    relative=report.get('context_file')
    if not relative:return None
    from .downloads import safe_join
    path=safe_join(data,relative)
    if path.suffix!='.safetensors' or not path.is_file():return None
    return str(path)


def attach(data,scoped,parameters):
    path=predecessor(data,parameters)
    if path:scoped['longtake_context']=path
    return scoped


def stale_contexts(data,record):
    """Advisory only: version changes never regenerate adjacent clips."""
    result=[]
    for i,parameters in enumerate(record.get('parameters',[])):
        used=(parameters.get('longtake') or {}).get('context_source')
        if used and (not i or predecessor(data,record['parameters'][i-1])!=used):result.append(i+1)
    return result


def context_guides(video):
    """A native 22-frame VAE run is seven steps: 1,4,4,4,4,1,4.

    Native PackedLayout accepts signed frame coordinates. Placing each block
    separately preserves the nonuniform VAE clock (a single 7-step keyframe
    shifted by -22 would have the wrong phase after the fifth step).
    """
    if video.ndim!=5 or video.shape[2]!=7:raise ValueError('Contesto LongTake non compatibile con la griglia H3.')
    offsets=(0,1,5,9,13,17,18)
    return [{'resolved_frame_index':offset-CONTEXT_FRAMES,'latent':video[:,:,i:i+1]}
            for i,offset in enumerate(offsets)]


def load_context(path,expected,torch):
    from safetensors import safe_open
    with safe_open(path,framework='pt',device='cpu') as source:
        meta=json.loads((source.metadata() or {}).get('h3_longtake','{}'))
        if meta.get('version')!=VERSION or meta.get('signature')!=expected:
            raise ValueError('modello o canvas diverso')
        original=meta.get('video',{})
        if not original or fingerprint(original['path'])!=original:
            raise ValueError('versione video modificata o mancante')
        video=source.get_tensor('video_tail')
    if not torch.isfinite(video).all():raise ValueError('contesto non finito')
    return context_guides(video)


def save_context(path,video,expected,media):
    from safetensors.torch import save_file
    # A small, CPU-only tail, not a resident copy of the full sampled latent.
    context_guides(video)
    meta={'version':VERSION,'signature':expected,'video':fingerprint(media),
          'frames':CONTEXT_FRAMES,'origin':'delivered_canvas_tail_vae_encode'}
    target=Path(path);temp=target.with_suffix('.tmp')
    try:
        save_file({'video_tail':video.detach().cpu().contiguous()},str(temp),
                  metadata={'h3_longtake':json.dumps(meta)})
        temp.replace(target)
    finally:temp.unlink(missing_ok=True)


def refine(sample,prepare_noise,nested,torch,model,samples,positive,negative,opts,progress):
    """Five actual extra steps; retain base audio even when audio was generated."""
    base_video,base_audio=samples.unbind()
    noise=prepare_noise(samples,opts['seed'])
    mask=nested((torch.ones_like(base_video),torch.zeros_like(base_audio)))
    refined=sample(model,noise,REFINE_STEPS,opts['cfg'],opts['sampler'],opts['scheduler'],
        positive,negative,samples,denoise=DENOISE,noise_mask=mask,
        disable_pbar=True,seed=opts['seed'],callback=progress)
    video,_=refined.unbind()
    from .vendor_longtake.blend import blend_video
    return nested((blend_video(base_video,video,opts['frames']),base_audio))

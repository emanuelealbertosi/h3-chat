"""Explicit FastH3 Omni sampling contract; never infer it from an arbitrary label."""
PRESET={'steps':8,'cfg':1,'sampler':'euler','scheduler':'simple','shift_video':12,'shift_audio':3,
        'attention':'vsa','attention_chunks':0,'attention_chunks_mode':'auto','pdd_enabled':False,'pdd_lora':'','loras':[]}

def is_fast(model):return model.get('external_config',{}).get('profile')=='fasth3-omni'


def install_head_bank(model):
    """Keep the physical output width separate from a 32-head checkpoint bank.

    Quantized loaders may set Linear.out_features to the stored 3072 rows.
    The pinned FinalLayer used that mutable value to detect PDD and treated
    the bank as one 3072/1024-wide output. Upstream now uses self.video_dim.
    Apply only that targeted expression fix, preserving its weighted PDD math.
    """
    import inspect
    import ast
    import textwrap
    import types
    head=model.final_layer
    check_heads(head.video_out.weight.shape[0],head.audio_out.weight.shape[0],True)
    # The pinned model detector also derives latent channels from output rows:
    # a bank then reports 768/1024 channels. Input projection weights retain
    # the true physical widths, independently of quantized Linear attributes.
    width=model.video_patch_proj.weight.shape[1]
    audio_width=model.audio_patch_proj.weight.shape[1]
    if tuple(model.patch_size)!=(1,2,2) or (width,audio_width)!=(96,32):raise ValueError('FastH3: proiezioni fisiche in ingresso non compatibili con 24/32 canali.')
    model.latents_dim=24
    model.audio_latents_dim=32
    head.video_dim=width
    if getattr(head,'_h3_fast_head_bank',False):return {'heads':32,'video_width':96,'audio_width':32,'patched':True}
    original=head.forward.__func__;source=textwrap.dedent(inspect.getsource(original))
    old='self.video_out.weight.shape[0] // self.video_out.out_features'
    new='self.video_out.weight.shape[0] // self.video_dim'
    if old in source:
        if source.count(old)!=1:raise ValueError('FastH3: rilevamento dei banchi PDD ambiguo nel runtime.')
        namespace=dict(original.__globals__)
        tree=ast.parse(source.replace(old,new));ast.increment_lineno(tree,inspect.getsourcelines(original)[1]-1)
        exec(compile(tree,inspect.getsourcefile(original) or '<FastH3 FinalLayer>','exec'),namespace)
        head.forward=types.MethodType(namespace[original.__name__],head)
    elif new not in source:raise ValueError('FastH3: API del banco PDD non riconosciuta; nessun cambio silenzioso del runtime.')
    head._h3_fast_head_bank=True
    return {'heads':32,'video_width':96,'audio_width':32,'patched':old in source}

def check_heads(video_rows,audio_rows,fast=False):
    expected=(3072,1024) if fast else (96,32)
    if (video_rows,audio_rows)!=expected:raise ValueError('Proiezioni video/audio incompatibili con il profilo FastH3 Omni scelto.' if fast else 'PDD/Turbo non supportato da questo profilo: scegli H3 standard oppure il profilo dedicato FastH3 Omni.')

def validate(options):
    if any(options[k]!=v for k,v in PRESET.items() if k not in ('attention_chunks','attention_chunks_mode','loras')):
        raise ValueError('FastH3 Omni richiede 8 passi, Euler/simple, CFG 1, shift 12/3, VSA e nessun PDD aggiuntivo. Ripristina il preset FastH3.')

def attach(model,patcher):
    blocks=model.get_model_object('diffusion_model').blocks
    if not blocks or any(getattr(b.attn,'to_gate_compress',None) is None for b in blocks):raise ValueError('Il diffusore non contiene i gate VSA di FastH3 Omni. Nessun ripiego su attenzione diversa.')
    return patcher(model,tau=1.3,topk_ratio=.1,vsa=True,start_percent=0.,end_percent=1.,min_tokens=12288,
        dense_blocks=set(),sink_conditioning='exact_kv_and_rows',extra_tokens=0,verbose=True)

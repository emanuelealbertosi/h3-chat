"""Explicit FastH3 Omni sampling contract; never infer it from an arbitrary label."""
PRESET={'steps':8,'cfg':1,'sampler':'euler','scheduler':'simple','shift_video':12,'shift_audio':3,
        'attention':'vsa','attention_chunks':0,'attention_chunks_mode':'auto','pdd_enabled':False,'pdd_lora':'','loras':[]}

def is_fast(model):return model.get('external_config',{}).get('profile')=='fasth3-omni'

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

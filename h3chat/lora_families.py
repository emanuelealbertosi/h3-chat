"""Conservative adapter family detection from paired tensors, not filenames."""
import re
import json,struct
from functools import lru_cache
from pathlib import Path


def checkpoint_family(path):
    """Separate legacy SD profiles using the checkpoint's cross-attention width."""
    try:
        p=Path(path);st=p.stat()
        return _checkpoint_family(str(p),st.st_size,st.st_mtime_ns)
    except OSError:return ''


@lru_cache(maxsize=64)
def _checkpoint_family(path,size,stamp):
    try:
        with open(path,'rb') as stream:
            length=struct.unpack('<Q',stream.read(8))[0]
            if not 2<=length<=min(16*1024**2,size-8):return ''
            header=json.loads(stream.read(length))
        if not isinstance(header,dict) or len(header)>100000:return ''
        widths=set()
        for key,value in header.items():
            if key.endswith('.attn2.to_k.weight') and isinstance(value,dict):
                shape=value.get('shape',[])
                if isinstance(shape,list) and len(shape)==2 and type(shape[1]) is int:widths.add(shape[1])
        if widths=={2048} or widths=={1280}:return 'sdxl'
        if widths=={768}:return 'sd15'
        if widths=={1024}:return 'sd2'
        return ''
    except (OSError,ValueError,TypeError,struct.error):return ''


def targets(header):
    """Layer -> (output, input, adapter format), including full LoKr/LoHa."""
    result={}
    def shape(key):
        value=header.get(key,{})
        shape=value.get('shape',[]) if isinstance(value,dict) else []
        return shape if isinstance(shape,list) and all(type(n) is int and n>0 for n in shape) else []
    for key in header:
        if key=='__metadata__':continue
        for down,up in (('.lora_down.weight','.lora_up.weight'),('.lora_A.weight','.lora_B.weight'),('.lora_A.default.weight','.lora_B.default.weight')):
            if not key.endswith(down):continue
            base=key[:-len(down)];a=shape(key);b=shape(base+up)
            if len(a)>=2 and len(b)>=2 and a[0]==b[1] and a[0]>0:result[base]=(b[0],a[1],'lora')
        if key.endswith('.lokr_w1'):
            base=key[:-len('.lokr_w1')];a=shape(key);b=shape(base+'.lokr_w2')
            if len(a)==len(b)==2:result[base]=(a[0]*b[0],a[1]*b[1],'lokr')
        if key.endswith('.hada_w1_a'):
            base=key[:-len('.hada_w1_a')];a,b,c,d=[shape(base+x) for x in ('.hada_w1_a','.hada_w1_b','.hada_w2_a','.hada_w2_b')]
            if all(len(x)==2 for x in (a,b,c,d)) and a[1]==b[0] and c[1]==d[0] and (a[0],b[1])==(c[0],d[1]):result[base]=(a[0],b[1],'loha')
    return result


def tensor_family(header):
    layers=targets(header)
    def has(pattern,out,inp):return any(re.search(pattern,k) and v[:2]==(out,inp) for k,v in layers.items())
    # MOSS's 3072-wide attention plus its gated 8192 FFN distinguish it from
    # FLUX/Qwen adapters of the same hidden width. Never infer from filename.
    if (has(r'(?:^|\.)layers\.\d+\.proj\.(?:q|k|v|o)$',3072,3072)
            and has(r'(?:^|\.)layers\.\d+\.proj\.ffn_up_gate$',16384,3072)
            and has(r'(?:^|\.)layers\.\d+\.proj\.ffn_down$',3072,8192)):return 'moss'
    if has(r'blocks[._]\d+[._]attn[._]qkv_proj$',21504,5376) or has(r'blocks[._]\d+[._]attn[._]out_proj$',5376,7168):return 'minimax-h3'
    if has(r'blocks[._]\d+[._]mlp[._]fc1$',28672,5376) and has(r'blocks[._]\d+[._]mlp[._]fc2$',5376,14336):return 'minimax-h3'
    if has(r'blocks\.\d+\.cross_attn\.k_proj$',2048,1024) and has(r'blocks\.\d+\.adaln_modulation_cross_attn\.1$',256,2048):return 'anima'
    if has(r'transformer_blocks[._]\d+[._]attn[._]add_k_proj$',3072,3072):return 'qwen-image'
    if has(r'modulation\.1$',16384,4096) and has(r'transformer_blocks\.\d+\.img_mlp\.gate_layer$',12288,4096):return 'qwen21'
    if any('single_transformer_blocks.' in k and 'to_qkv_mlp_proj' in k for k in layers):return 'flux2'
    if has(r'double_blocks[._]\d+[._]img_attn[._]proj$',4096,4096):return 'flux2'
    if has(r'double_blocks[._]\d+[._]img_attn[._]proj$',3072,3072) or has(r'double_blocks[._]\d+[._]img_attn[._]qkv$',9216,3072):return 'flux1'
    if has(r'blocks\.\d+\.cross_attn\.k$',5120,5120):return 'wan'
    if has(r'transformer_blocks\.\d+\.audio_to_video_attn\.to_q$',2048,4096):return 'ltx2'
    unet=any(re.search(r'(?:lora_unet_|unet\.)(?:down|up|mid|input|output|middle)[._]blocks?[._]',k) for k in layers)
    if unet:
        if any(k.startswith('lora_te2_') for k in layers) or any(re.search(r'transformer_blocks[._][1-9]\d*[._]',k) for k in layers):return 'sdxl'
        for context,family in ((2048,'sdxl'),(1024,'sd2'),(768,'sd15')):
            if any(re.search(r'attn2[._]to_k$',k) and v[1]==context for k,v in layers.items()):return family
    return ''

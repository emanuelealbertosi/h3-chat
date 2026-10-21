"""Load Comfy-Org INT8 ConvRot weights into the original Diffusers models.

Keep quantized weights/scales/rotation metadata intact. In particular, retain
the padded FFN width: removing columns from a rotated matrix is incorrect.
No ComfyUI server or third-party custom-node code is loaded.
"""
import re


def encoder_state(state,config):
    # Hugging Face checkpoints omit the output head when it shares the input
    # embedding. Recreate the alias, including quantization, before strict load.
    if getattr(config,'tie_word_embeddings',False) and 'lm_head.weight' not in state:
        source='model.language_model.embed_tokens.'
        for suffix in ('weight','weight_scale','comfy_quant'):
            if source+suffix not in state:raise ValueError('Embedding condiviso INT8 incompleto.')
            state['lm_head.'+suffix]=state[source+suffix]
    return state


def remap_transformer(state):
    result={}
    for key,value in state.items():
        if key.endswith('.comfy_attention.config'):continue
        match=re.match(r'^(.*\.)(qkv|to_kv|w13)\.(weight|weight_scale|comfy_quant)$',key)
        if match:
            prefix,fused,suffix=match.groups()
            targets={'qkv':('to_q','to_k','to_v'),'to_kv':('to_k','to_v'),'w13':('w1','w3')}[fused]
            if suffix=='comfy_quant':parts=[value]*len(targets)
            else:
                if value.shape[0]%len(targets):raise ValueError('Dimensione FIBO fusa non divisibile: '+key)
                size=value.shape[0]//len(targets);parts=[value[i*size:(i+1)*size] for i in range(len(targets))]
            for target,part in zip(targets,parts):result[prefix+target+'.'+suffix]=part
            continue
        key=key.replace('.attention.out.','.attention.to_out.0.').replace('.attention.q_norm.','.attention.norm_q.').replace('.attention.k_norm.','.attention.norm_k.')
        key=re.sub(r'\.to_out\.(weight|weight_scale|comfy_quant)$',r'.to_out.0.\1',key)
        result[key]=value
    return result


def install_quantized_modules(model,state,torch):
    from comfy.ops import mixed_precision_ops
    operations=mixed_precision_ops({'mixed_ops':True},torch.bfloat16,disabled=[])
    count=0
    for name,module in list(model.named_modules()):
        if name+'.comfy_quant' not in state:continue
        weight=state.get(name+'.weight')
        if weight is None or weight.dtype!=torch.int8:raise ValueError('Pesi INT8 mancanti: '+name)
        if isinstance(module,torch.nn.Linear):
            replacement=operations.Linear(weight.shape[1],weight.shape[0],bias=module.bias is not None,device='cpu',dtype=torch.bfloat16)
        elif isinstance(module,torch.nn.Embedding):
            replacement=operations.Embedding(weight.shape[0],weight.shape[1],padding_idx=module.padding_idx,device='cpu',dtype=torch.bfloat16)
        else:raise ValueError('Modulo quantizzato non supportato: '+name)
        parent,_,child=name.rpartition('.');setattr(model.get_submodule(parent) if parent else model,child,replacement);count+=1
    if not count:raise ValueError('Il file non contiene moduli FIBO INT8 compatibili.')
    model.load_state_dict(state,strict=True,assign=True)
    if any(p.is_meta for p in model.parameters()):raise ValueError('Caricamento INT8 incompleto: tensori meta residui.')
    from comfy_kitchen.tensor import QuantizedTensor
    real=[m for m in model.modules() if isinstance(getattr(m,'weight',None),QuantizedTensor)]
    if len(real)!=count:raise ValueError('Il caricamento ha perso i pesi quantizzati.')
    if any(m.weight._qdata.dtype!=torch.int8 for m in real):raise ValueError('Il modello non conserva INT8 in memoria.')
    return count


def load_transformer(root,path,torch):
    from accelerate import init_empty_weights
    from diffusers import BriaFibo2Transformer2DModel
    from safetensors.torch import load_file
    with init_empty_weights():
        transformer=BriaFibo2Transformer2DModel.from_config(BriaFibo2Transformer2DModel.load_config(str(root/'transformer')))
    count=install_quantized_modules(transformer,remap_transformer(load_file(path)),torch)
    transformer.eval()
    return transformer,count


def load_components(root,files,torch):
    from accelerate import init_empty_weights
    from transformers import AutoConfig,Qwen3VLForConditionalGeneration
    from safetensors.torch import load_file
    transformer,count=load_transformer(root,files['diffusion'],torch)
    with init_empty_weights():
        encoder=Qwen3VLForConditionalGeneration(AutoConfig.from_pretrained(str(root/'text_encoder'),local_files_only=True))
    encoder_count=install_quantized_modules(encoder,encoder_state(load_file(files['llm']),encoder.config),torch)
    encoder.tie_weights()
    # The image pipeline only consumes hidden states. Avoid materializing
    # vocabulary logits for every prompt token and an unused generation KV cache.
    from functools import partial
    encoder.forward=partial(encoder.forward,logits_to_keep=1,use_cache=False)
    transformer.eval();encoder.eval()
    return transformer,encoder,{'quantization':'int8_convrot','quantized_diffusion_modules':count,'quantized_encoder_modules':encoder_count}

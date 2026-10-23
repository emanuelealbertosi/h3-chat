"""FP32 residual LoRA, never merged into BF16/INT8 base parameters."""
import math
from contextlib import contextmanager


def cached_adapter(owner,path):
    if getattr(owner,'dmd2_adapter',None) is None or getattr(owner,'dmd2_path',None)!=path:
        owner.dmd2_adapter=Adapter(path);owner.dmd2_path=path
    return owner.dmd2_adapter


class Adapter:
    def __init__(self,path):
        import torch
        from safetensors.torch import load_file
        state=load_file(str(path),device='cpu');self.layers={};consumed=set()
        for key,down in state.items():
            if not key.endswith('.lora_down.weight'):continue
            prefix=key[:-len('.lora_down.weight')]
            if not prefix.startswith('diffusion_model.layers.'):
                raise ValueError('DMD2 MOSS: modulo inatteso '+prefix)
            up_key=prefix+'.lora_up.weight';alpha_key=prefix+'.alpha'
            up=state.get(up_key);alpha=state.get(alpha_key)
            if up is None or alpha is None or down.ndim!=2 or up.ndim!=2 or down.shape[0]!=up.shape[1] or alpha.numel()!=1:
                raise ValueError('DMD2 MOSS: coppia LoRA non valida.')
            scale=float(alpha.item())/down.shape[0]
            if not math.isfinite(scale) or not torch.isfinite(down).all() or not torch.isfinite(up).all():
                raise ValueError('DMD2 MOSS: valori non finiti.')
            self.layers[prefix[len('diffusion_model.'):]]=(down.float(),up.float(),scale)
            consumed.update((key,up_key,alpha_key))
        if not self.layers or set(state)!=consumed:
            raise ValueError('DMD2 MOSS: tensori mancanti o non applicabili.')

    @contextmanager
    def apply(self,transformer):
        import torch
        import torch.nn.functional as F
        modules=dict(transformer.named_modules());handles=[];cache={}
        # Validate everything before installing any hook.
        for name,(down,up,_) in self.layers.items():
            target=modules.get(name)
            if target is None or not hasattr(target,'weight') or tuple(target.weight.shape)!=(up.shape[0],down.shape[1]):
                raise ValueError('DMD2 MOSS: tensori incompatibili con '+name)
        def hook(name,down,up,scale):
            def residual(module,args,out):
                x=args[0];key=(name,x.device)
                if key not in cache:cache[key]=(down.to(x.device),up.to(x.device))
                a,b=cache[key]
                # Keep the small delta in FP32 until it is added to the output.
                # Never quantize or fuse it into the base model's weight.
                delta=F.linear(F.linear(x.float(),a),b).mul_(scale)
                return out+delta.to(out.dtype)
            return residual
        try:
            for name,(down,up,scale) in self.layers.items():
                handles.append(modules[name].register_forward_hook(hook(name,down,up,scale)))
            yield {'adapter':'MOSS DMD2 8-step','applied_modules':len(handles),'merge':False,'adapter_dtype':'float32'}
        finally:
            for handle in handles:handle.remove()
            cache.clear()

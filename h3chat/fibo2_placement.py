"""Partial CUDA residency for FIBO, keeping streamed weights backed on CPU."""

def weight_bytes(module,recurse=True):
    return sum(t.numel()*t.element_size() for t in [*module.parameters(recurse=recurse),*module.buffers(recurse=recurse)])


def resident(pipe,torch):
    from accelerate import cpu_offload
    from accelerate.hooks import AlignDevicesHook,add_hook_to_module
    device=torch.device('cuda');gib=1024**3
    free,_=torch.cuda.mem_get_info()
    # Space for attention, streamed leaves, the VAE and the text encoder's
    # current leaf. Do not reserve the whole card or create pinned CPU clones.
    budget=min(10*gib,free-4*gib)
    if budget<2*gib:raise ValueError('FIBO Più GPU richiede almeno 6 GiB di VRAM libera; libera memoria o scegli Prudente.')
    transformer=pipe.transformer;layers=transformer.layers
    shared=[m for name,m in transformer.named_children() if name!='layers']
    used=weight_bytes(transformer,recurse=False)+sum(weight_bytes(m) for m in shared)
    if used>budget:raise ValueError('Le parti condivise FIBO superano il budget VRAM; scegli Prudente.')
    for module in shared:module.to(device)
    for tensor in [*transformer.parameters(recurse=False),*transformer.buffers(recurse=False)]:tensor.data=tensor.data.to(device)
    kept=0
    for block in layers:
        size=weight_bytes(block)
        if used+size<=budget:
            block.to(device);used+=size;kept+=1
        else:
            # Accelerate retains one CPU state dict and restores meta tensors
            # after execution, avoiding a fresh CUDA->CPU copy on every step.
            cpu_offload(block,device,offload_buffers=len(block._parameters)>0)
    add_hook_to_module(transformer,AlignDevicesHook(execution_device=device,io_same_device=True))
    cpu_offload(pipe.text_encoder,device,offload_buffers=len(pipe.text_encoder._parameters)>0)
    pipe.vae.to(device)
    return {'resident_blocks':kept,'offloaded_blocks':len(layers)-kept,
        'resident_weights_gib':round(used/gib,3),'resident_budget_gib':round(budget/gib,3)}

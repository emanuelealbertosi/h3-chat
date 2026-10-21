"""VEDA workspace budget includes reusable PyTorch cache, like the model manager."""
import math


def head_chunks_for_edit(requested,*,aligned,width,height,frames,total_bytes,diagnostic=False,source_shape=None,manual=False):
    """Keep narrow head batches at the measured long aligned-guide threshold.

    Only batching changes; sparsity, predictor, frames and model stay intact.
    Diagnostic requests retain their exact requested comparison settings.
    """
    if manual:return requested
    latent_t=max(0,math.ceil((frames-5)/17))*5+2
    packed_video_rows=2*latent_t*(width//32)*(height//32)
    has_guide=aligned
    if not aligned and source_shape:
        sw,sh,sframes=source_shape
        source_t=max(0,math.ceil((sframes-5)/17))*5+2
        packed_video_rows=latent_t*(width//32)*(height//32)+source_t*(sw//32)*(sh//32)
        has_guide=True
    if not diagnostic and has_guide and 0<total_bytes<=20*1024**3 and packed_video_rows>=140000:
        return 56
    return requested


def available_workspace(cuda,device):
    free,total=cuda.mem_get_info(device)
    cached=max(0,cuda.memory_reserved(device)-cuda.memory_allocated(device))
    return min(total,max(0,free)+cached),max(0,free),cached


def install(patch,torch,engine_module):
    """Adapt only this H3 worker's lazy VEDA engines; leave the pinned vendor intact."""
    original=patch._engine
    def engine_for(device):
        engine=original(device)
        if engine is None or getattr(engine,'_h3_cache_budget',False):return engine
        native=engine._chunk_bytes
        def budget():
            if engine.device.type!='cuda':return native()
            available,free,cached=available_workspace(torch.cuda,engine.device)
            engine.chunking.update(free_bytes=available,driver_free_bytes=free,reusable_cache_bytes=cached)
            return int(min(max(available//engine_module._CHUNK_SHARE,engine_module._MIN_CHUNK_BYTES),engine_module._MAX_CHUNK_BYTES))
        engine._chunk_bytes=budget
        engine._h3_cache_budget=True
        return engine
    patch._engine=engine_for

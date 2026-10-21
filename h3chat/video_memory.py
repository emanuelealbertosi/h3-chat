"""Release unused sampling allocations at the VRAM boundary, never live weights."""


def should_trim_sampling_cache(snapshot, offload):
    if not offload or not snapshot:
        return False
    # Windows can spill a full CUDA pool even while most of it is unused.
    # Only trim a sizeable unused pool with little driver-visible headroom.
    unused = snapshot['reserved_mb'] - snapshot['allocated_mb']
    return snapshot['free_mb'] < 1024 and unused >= 2048


def diffuser_placement(models):
    """Report actual residency after loading; never infer paging from RAM use."""
    for patcher in models:
        if type(patcher.model).__name__!='MiniMaxH3':continue
        total=patcher.model_size();resident=patcher.loaded_size()
        if total>0:return {'total_mib':round(total/1024**2,1),'resident_mib':round(resident/1024**2,1),
            'streaming_from_ram':resident<total*.05}
    return None

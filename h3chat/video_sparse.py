"""Opt-in H3 VSA fine-stage patch; distinct from VEDA and FastH3 gates."""


def attach(model,patcher):
    blocks=model.get_model_object('diffusion_model').blocks
    if not blocks:raise ValueError('VSA richiede un diffusore MiniMax H3.')
    # The bundled upstream patch explicitly supports standard H3 without
    # compression gates. FastH3 keeps its separate, stricter trained contract.
    return patcher(model,tau=1.3,topk_ratio=.1,vsa=True,start_percent=0.,end_percent=1.,
        min_tokens=12288,dense_blocks=set(),sink_conditioning='exact_kv_and_rows',extra_tokens=0,verbose=True)

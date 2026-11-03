"""Portable generation preferences, kept separate from credentials and host grants."""
from copy import deepcopy
from .llm_options import KEYS as LLM_KEYS
from .voice import DEFAULTS as VOICE_DEFAULTS

KEYS=set(LLM_KEYS)|set(VOICE_DEFAULTS)|set('''chat_model create_model edit_model diagram_model music_model video_model
 backend threads llm_device image_device vision_enabled vision_device system_prompt
 context max_tokens temperature think_level image_cfg image_aspect width height steps seed strength negative_prompt
 image_sampler image_scheduler diagram_auto image_overrides video_overrides music_overrides llm_overrides
 music_backend music_threads music_quality music_quality_profiles
 asr_device asr_model asr_language asr_threads asr_beam transcribe_auto
 rag_device rag_visual rag_top_k web_provider web_searxng_url web_max_results profile
 lab_auto video_auto music_auto web_auto memory_policy ram_cache_gb
 manim_device manim_duration manim_fps manim_width manim_height manim_timeout manim_memory_gb'''.split())
MAPS={'image_overrides','video_overrides','music_overrides','llm_overrides'}


def snapshot(settings):
    result={k:deepcopy(settings[k]) for k in KEYS-MAPS if k in settings}
    models={settings.get(k) for k in ('chat_model','create_model','edit_model','diagram_model','music_model','video_model','_image_model')}
    for name in ('_slides','_posters','_infographic'):
        if isinstance(settings.get(name),dict):models.add(settings[name].get('image_model'))
    for key in MAPS:
        if key in settings:result[key]={ident:deepcopy(value) for ident,value in settings[key].items() if ident in models}
    if settings.get('chat_model'):
        result.setdefault('llm_overrides',{})[settings['chat_model']]={k:deepcopy(settings[k]) for k in LLM_KEYS if k in settings}
    return result


def resolve(app,body):
    """Validate a request-local override using the normal model/device rules."""
    patch=body.get('request_settings',{})
    if not isinstance(patch,dict) or set(patch)-KEYS:raise ValueError('Impostazioni della richiesta ricaricata non valide.')
    patch=deepcopy(patch)
    current=app.store.settings()
    owner=getattr(app,'execution_owner',app)
    if owner.store.settings().get('execution_mode')=='cpu' and patch.get('chat_model'):
        patch['cpu_chat_model']=patch['chat_model']
    for key in MAPS:
        if key in patch:
            if not isinstance(patch[key],dict):raise ValueError('Preset della richiesta ricaricata non validi.')
            patch[key]=current.get(key,{})|patch[key]
    patch['think_level']=body.get('think_level',patch.get('think_level',current.get('think_level','off')))
    return app.effective_settings(app.validate_settings(patch))

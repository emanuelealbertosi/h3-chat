"""Runtime policy, separate from the user's saved GPU/model presets."""
from .llm_options import merge as merge_llm_settings

MEDIA_ERROR='Modalità CPU: creazione di immagini, video e audio disabilitata. Seleziona GPU per usare queste funzioni.'
API_ERROR='Modalità CPU: scegli un LLM locale disponibile oppure collega un provider esterno per usare chat e Assistant.'
MEDIA_INTENTS={'create','edit','image_batch','music','video','voice','transcribe'}

def cpu(settings):
    return settings.get('execution_mode','gpu')=='cpu'

def effective(settings,catalog=None,mode=None):
    settings=dict(settings)
    if mode is not None:settings['execution_mode']=mode
    if not cpu(settings):return settings
    if catalog is not None:
        available=[m['id'] for m in catalog.values() if m.get('ready',True) and 'chat' in m.get('capabilities',[])]
        selected=next((key for key in (settings.get('cpu_chat_model'),settings.get('chat_model'),*available) if key in available),'')
        settings=merge_llm_settings(settings,{'chat_model':selected})
    settings.update(profile='cpu',backend='cpu',gpu_layers=0,llm_device='cpu',image_device='cpu',
        vision_device='cpu',rag_device='cpu',asr_device='cpu',manim_device='cpu',voice_device='cpu',music_backend='cpu',
        memory_policy='on_demand',ram_cache_gb=0,llm_acceleration='standard',mtp_enabled=False,
        video_auto=False,music_auto=False,voice_auto=False,transcribe_auto=False,diagram_auto=False,
        create_model='',edit_model='',diagram_model='',music_model='',video_model='')
    return settings

def require_model(settings,model,capability):
    if not cpu(settings):return
    if capability!='chat':raise ValueError(MEDIA_ERROR)
    if not model or 'chat' not in model.get('capabilities',[]):raise ValueError(API_ERROR)

def guard_intent(settings,intent):
    if cpu(settings) and intent in MEDIA_INTENTS:raise ValueError(MEDIA_ERROR)

def guard_job(settings):
    if not cpu(settings):return
    flags=('_image_model','_image_batch','_music','_video','_voice','_transcribe','_upscale','_video_probe',
           '_video_edit','_video_recreate','_video_extend','_video_remix','_video_resume','_music_resing','_manim_voice')
    if any(settings.get(key) for key in flags):raise ValueError(MEDIA_ERROR)
    if settings.get('_slides',{}).get('generate_images'):raise ValueError(MEDIA_ERROR)
    inf=settings.get('_infographic',{})
    if inf.get('voice') or inf.get('images')=='generate' or inf.get('music') in ('generate','jingle'):
        raise ValueError('Modalità CPU: disattiva voce, musica e illustrazioni AI dell’infografica. Puoi usare grafica HTML/SVG e allegati.')

def public(settings,catalog):
    live=effective(settings,catalog)
    return {'mode':settings.get('execution_mode','gpu'),'chat_model':live.get('chat_model',''),
            'api_ready':bool(catalog.get(live.get('chat_model'),{}).get('api')),
            'chat_ready':bool(catalog.get(live.get('chat_model'),{}).get('ready',False)),
            'media_enabled':not cpu(settings)}

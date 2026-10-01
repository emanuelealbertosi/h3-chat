"""Independent local devices, preserving the previous global profile by default."""
CPU_WARNING='L’elaborazione sulla CPU può richiedere molto tempo.'
def options(settings,role):
    choice=settings.get(role+'_device','inherit')
    if choice=='inherit':return settings
    if choice=='cpu':return settings|{'profile':'cpu','backend':'cpu','gpu_layers':0}
    return settings|{'profile':'low' if settings['profile']=='cpu' else settings['profile'],'backend':settings['backend'] if settings['backend'] in ('cuda','vulkan') else 'cuda'}
def label(settings,role):
    if role=='video':return 'GPU · CUDA'
    if role=='music':
        from .music_runtime import backend
        device=backend(settings)
    else:
        effective=options(settings,role);device='cpu' if effective['profile']=='cpu' else effective['backend']
    return 'CPU' if device=='cpu' else 'GPU · '+device.upper()
def validate(settings):
    for key in ('llm_device','image_device'):
        if settings[key] not in ('inherit','cpu','gpu'):raise ValueError('Modalità CPU/GPU non valida: '+key)
    for key in ('rag_device','asr_device','manim_device'):
        if settings[key] not in ('cpu','gpu'):raise ValueError('Modalità CPU/GPU non valida: '+key)

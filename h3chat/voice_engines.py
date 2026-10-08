"""Higgs-only speech, compatible with saved optional-engine requests."""
ENGINES={'higgs':'Higgs Audio v3'}
DEFAULTS={'voice_engine':'higgs'}
RETIRED=('qwen','chatterbox')

def fields(value):
    result=dict(value)
    if result.get('engine') in RETIRED:result['engine']='higgs'
    if isinstance(result.get('params'),dict):
        result['params']={k:v for k,v in result['params'].items() if k not in RETIRED}
        if not result['params']:result.pop('params')
    return result

def normalize(settings):
    result={k:v for k,v in settings.items() if not k.startswith(('voice_qwen_','voice_chatterbox_'))}
    changed=result.get('voice_engine') in RETIRED or result.get('_voice_fields',{}).get('engine') in RETIRED
    if result.get('voice_engine') in RETIRED:result['voice_engine']='higgs'
    if isinstance(result.get('_voice_fields'),dict):result['_voice_fields']=fields(result['_voice_fields'])
    if changed:result.pop('_manim_voice_resume',None)
    return result

def selected(settings):
    value=settings.get('_voice_fields',{}).get('engine') or settings.get('voice_engine','higgs')
    return 'higgs' if value in RETIRED else value

def validate_overrides(value):
    if value!={}:raise ValueError('I parametri Higgs si impostano nelle preferenze Voice.')
    return {}

def validate(settings):
    if selected(settings)!='higgs':raise ValueError('Motore Voice non valido.')

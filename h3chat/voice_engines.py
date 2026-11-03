"""Default Higgs speech and opt-in MOSS, with saved legacy request migration."""
ENGINES={'higgs':'Higgs Audio v3','moss':'MOSS-TTS Local v1.5 · sperimentale'}
DEFAULTS={'voice_engine':'higgs','voice_moss_model_path':'','voice_moss_codec_path':'','voice_moss_language':'Italian','voice_moss_temperature':1.7,'voice_moss_top_p':.8,'voice_moss_top_k':25,'voice_moss_repetition_penalty':1.0,'voice_moss_max_new_tokens':2048,'voice_moss_seed':734,'voice_moss_precision':'bf16'}
RETIRED=('qwen','chatterbox')
DEFAULTS.update(voice_moss_instruction='',voice_moss_reference_mode='configured',voice_moss_target_seconds=0.,voice_moss_codec_quality='balanced')

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
    from .moss_tts import validate_params
    if not isinstance(value,dict) or set(value)-{'moss'}:raise ValueError('Parametri del motore Voice non validi.')
    if 'moss' in value:validate_params(value['moss'])
    return value

def validate(settings):
    if selected(settings) not in ENGINES:raise ValueError('Motore Voice non valido.')
    from .moss_tts import validate_settings
    validate_settings(settings)

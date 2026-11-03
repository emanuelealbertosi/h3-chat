"""Owner-local, portable narration presets; never change general Voice settings."""
import json

CHOICES=('auto','limpida','aurora','configured')

def configure(root, settings, opts, delivery):
    selected=opts.get('voice_profile','auto')
    registry=root/'data/voices/infographic-profiles.json'
    if not registry.is_file():registry=root/'static/voice-profiles/profiles.json'
    profiles=json.loads(registry.read_text(encoding='utf-8')) if registry.is_file() else {}
    if selected=='auto':
        selected=profiles.get('default','configured') if opts['voice_gender'] in ('auto','female') else 'configured'
    fields=settings.get('_voice_fields',{})|{'delivery':delivery}
    result=settings|{'_voice_fields':fields,'memory_policy':'on_demand'}
    if selected=='configured':return result,selected
    profile=profiles.get('profiles',{}).get(selected)
    if not profile:raise ValueError('Campione '+selected+' non installato. Scegli «Dalle impostazioni Voice».')
    from pathlib import Path
    path=Path(profile['path'])
    if not path.is_absolute():path=root/path
    if not path.is_file():raise ValueError('Campione vocale non disponibile: '+selected)
    result.update(voice_precision='bf16',voice_temperature=.8,voice_seed=734,
        voice_chunk_chars=600,voice_pause_ms=220,voice_speed_factor=1.,voice_gender='female')
    result['voice_references']=settings['voice_references']|{'female':{'path':str(path),'transcript':profile['transcript']}}
    result['_voice_fields']={'pitch':'normal','speed':'normal','emotion':'neutral',
        'expressiveness':'high',**settings.get('_voice_fields',{}),
        'engine':'higgs','profile':selected,
        'delivery':'custom' if opts['voice_style']=='auto' else delivery}
    result['_voice_profile_applied']=selected
    return result,selected

"""Portable quality presets, captured before a request enters the shared queue."""
import copy

QUALITIES=('model','high','low')
PROFILES={'high':{'model':'','steps':60},'low':{'model':'','steps':32}}

def quality(value):
    if not isinstance(value,str) or value not in QUALITIES:
        raise ValueError('Qualità musica: scegli Alta, Bassa o Parametri del modello.')
    return value

def validate(settings,catalog):
    selected=quality(settings.get('music_quality','model'))
    profiles=settings.get('music_quality_profiles',PROFILES)
    if not isinstance(profiles,dict) or set(profiles)!=set(PROFILES):
        raise ValueError('Preset di qualità musica non validi.')
    for name,profile in profiles.items():
        if not isinstance(profile,dict) or set(profile)!={'model','steps'}:
            raise ValueError('Preset musica non valido: '+name)
        model=profile['model'];steps=profile['steps']
        if not isinstance(model,str) or len(model)>150 or (model and (model not in catalog or 'music' not in catalog[model]['capabilities'])):
            raise ValueError('Scegli un modello musicale valido per la qualità '+('Alta' if name=='high' else 'Bassa')+'.')
        if type(steps) is not int or not 1<=steps<=128:raise ValueError('Passi musica: scegli da 1 a 128.')
    if selected!='model' and not profiles[selected]['model']:
        raise ValueError('Configura il modello per la qualità '+('Alta' if selected=='high' else 'Bassa')+' in Impostazioni → Musica.')
    return profiles

def capture(settings,choice=None):
    selected=quality(settings.get('music_quality','model') if choice is None or choice=='' else choice)
    result=copy.deepcopy(settings);result['music_quality']=selected
    if selected=='model':return result
    profile=result.get('music_quality_profiles',PROFILES)[selected]
    if not profile['model']:
        raise ValueError('Configura il modello per la qualità '+('Alta' if selected=='high' else 'Bassa')+' in Impostazioni → Musica.')
    result['music_model']=profile['model']
    result.setdefault('music_overrides',{}).setdefault(profile['model'],{})['num_inference_steps']=profile['steps']
    return result

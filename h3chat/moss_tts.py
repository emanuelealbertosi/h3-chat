"""Experimental, explicitly selected MOSS-TTS Local Transformer 1.5."""
import json,math,re
from pathlib import Path
LANGUAGES=('Italian','English','French','German','Spanish','Portuguese','Chinese','Japanese','Korean','Arabic','Russian','Dutch','Polish','Greek','Hindi','Turkish','Romanian','Swedish','Danish','Finnish','Czech','Hungarian','Hebrew','Persian','Vietnamese','Thai','Malay','Tagalog','Swahili','Macedonian','Cantonese')
PARAMS={'temperature':(.1,3,float),'top_p':(.01,1,float),'top_k':(1,1000,int),'repetition_penalty':(.5,2,float),'max_new_tokens':(64,4096,int),'seed':(-1,2147483647,int)}
PARAMS['target_seconds']=(0,120,float)
CODEC_QUALITIES={'balanced':('bf16','bf16'),'official':('fp32','bf16'),'full':('fp32','fp32')}

def validate_params(value):
    if not isinstance(value,dict) or set(value)-set(PARAMS)-{'language','precision','instruction','reference_mode','codec_quality'}:raise ValueError('Parametri MOSS-TTS non validi.')
    for key,v in value.items():
        if key=='language':
            if v not in LANGUAGES:raise ValueError('Lingua MOSS-TTS non valida.')
        elif key=='instruction':
            if not isinstance(v,str) or len(v)>2000:raise ValueError('Direzione vocale MOSS: massimo 2.000 caratteri.')
        elif key=='codec_quality':
            if v not in CODEC_QUALITIES:raise ValueError('Precisione del codec MOSS non valida.')
        elif key=='reference_mode':
            if v not in ('configured','none'):raise ValueError('Riferimento MOSS-TTS non valido.')
        elif key=='precision':
            if v!='bf16':raise ValueError('MOSS-TTS Local v1.5: questa prima integrazione usa BF16.')
        else:
            lo,hi,kind=PARAMS[key]
            if type(v) not in ((int,) if kind is int else (int,float)) or not math.isfinite(v) or not lo<=v<=hi:raise ValueError('Parametro MOSS-TTS fuori intervallo: '+key)
    return value

def resolve(folder,codec=False):
    from .external_models import absolute_path
    path=absolute_path(folder)
    try:config=json.loads((path/'config.json').read_text(encoding='utf-8'))
    except (OSError,ValueError):raise ValueError('Seleziona la cartella locale MOSS-TTS Local v1.5 e il suo codec v2.') from None
    if config.get('model_type')!=('moss-audio-tokenizer' if codec else 'moss_tts_local') or config.get('sampling_rate')!=48000:raise ValueError('Il modello non è MOSS-TTS Local v1.5 / codec stereo v2 a 48 kHz.')
    if not codec and config.get('n_vq')!=12:raise ValueError('MOSS-TTS Local v1.5 richiede dodici codebook.')
    index=path/'model.safetensors.index.json'
    files=set(json.loads(index.read_text())['weight_map'].values()) if index.exists() else {'model.safetensors'}
    if any(not (path/name).is_file() for name in files):raise ValueError('Pesi MOSS-TTS incompleti: attendi il termine del download.')
    return str(path)

def validate_settings(settings):
    values={k:settings['voice_moss_'+k] for k in (*PARAMS,'language','precision','instruction','reference_mode','codec_quality') if 'voice_moss_'+k in settings};validate_params(values)
    for key in ('voice_moss_model_path','voice_moss_codec_path'):
        if key in settings and not isinstance(settings[key],str):raise ValueError('Percorso MOSS-TTS non valido.')

def ready(root):
    root=Path(root)
    return all((root/name).is_file() for name in ('native/moss-voice-backend.py','native/h3_moss_audio.py','runtime/vision/packages/torch/__init__.py','runtime/vision/packages/transformers/__init__.py','runtime/vision/packages/av/__init__.py'))

def configuration(root,settings,choice):
    model=resolve(settings.get('voice_moss_model_path',''));codec=resolve(settings.get('voice_moss_codec_path',''),True)
    params={k:settings.get('voice_moss_'+k,v) for k,v in {'language':'Italian','temperature':1.7,'top_p':.8,'top_k':25,'repetition_penalty':1.,'max_new_tokens':2048,'seed':734,'precision':'bf16','instruction':'','reference_mode':'configured','target_seconds':0.,'codec_quality':'balanced'}.items()}
    params.update(settings.get('_voice_fields',{}).get('params',{}).get('moss',{}));validate_params(params)
    ref=settings['voice_references'][choice['gender']] if params['reference_mode']=='configured' else {'path':'','transcript':''}
    if ref['path'] and not Path(ref['path']).is_file():raise ValueError('Campione vocale MOSS-TTS non disponibile.')
    identity=Path(ref['path']).stem if ref['path'] else 'designed-'+str(params['seed'])
    return {'engine':'moss','model_path':model,'codec_path':codec,'device':'cuda' if settings['voice_device']=='gpu' else 'cpu','pause_ms':settings['voice_pause_ms'],'speed_factor':settings['voice_speed_factor'],**params}, {'id':'moss:'+choice['gender']+':'+identity,'reference':ref['path'],'transcript':ref['transcript']}

def spoken(text):
    """Translate the owner's pause direction into the native v1.5 markup."""
    return re.sub(r'\[\s*pausa\s*\]','[pause 0.8s]',text,flags=re.I)


def instruction(choice,explicit=''):
    if explicit.strip():return explicit.strip()
    return ' '.join([{'female':'An adult female speaker.','male':'An adult male speaker.'}.get(choice.get('gender'),''),{'neutral':'Natural, clear speech.','affection':'Warm, affectionate tone.','enthusiasm':'Lively, enthusiastic tone.','contemplation':'Thoughtful tone.','determination':'Confident, determined tone.','sadness':'Sad, restrained tone.'}.get(choice.get('emotion'),''),{'low':'Low pitch.','high':'High pitch.'}.get(choice.get('pitch'),''),{'slow':'Speak slowly.','fast':'Speak briskly.'}.get(choice.get('speed'),''),{'low':'Restrained expressiveness.','high':'Expressive delivery.'}.get(choice.get('expressiveness'),'')]).strip()

"""Shared admin configuration for the application-private audio remix engines."""
import json
import os
import threading
from pathlib import Path

LOCK=threading.Lock()
DEFAULTS={'backend':'cuda','threads':8,'separation_model':'','conversion_model':'',
          'sheet_model':'','mert_model':'','voice_steps':30}

def validate(value):
    if not isinstance(value,dict) or set(value)-set(DEFAULTS):raise ValueError('Impostazioni Remix non valide.')
    result=DEFAULTS|value
    if result['backend'] not in ('cpu','cuda'):raise ValueError('Remix: scegli CPU oppure GPU NVIDIA.')
    for key,lo,hi in (('threads',1,64),('voice_steps',30,100)):
        if type(result[key]) is not int or not lo<=result[key]<=hi:raise ValueError('Parametro Remix non valido: '+key)
    if result['voice_steps'] not in (30,50,100):raise ValueError('Conversione voce: scegli 30, 50 o 100 passi.')
    for key in ('separation_model','conversion_model','sheet_model','mert_model'):
        text=result[key]
        if not isinstance(text,str):raise ValueError('Percorso Remix non valido.')
        if text and (not Path(text).is_absolute() or not Path(text).exists()):raise ValueError('Percorso Remix non disponibile: '+key)
        if text and key.endswith('_model') and key in ('sheet_model','mert_model') and not (Path(text)/'config.json').is_file():raise ValueError('Scegli una cartella Transformers: '+key)
        if text and key in ('separation_model','conversion_model'):
            folder=Path(text)
            if folder.is_file():
                if folder.suffix.lower()!='.gguf':raise ValueError('Scegli il file GGUF oppure la sua cartella.')
                result[key]=str(folder.parent)
            if not any(Path(result[key]).glob('*.gguf')):raise ValueError('La cartella non contiene un modello GGUF: '+key)
    return result

def settings(root):
    try:value=json.loads((Path(root)/'data/remix.json').read_text(encoding='utf-8'))
    except FileNotFoundError:value={}
    return validate(value)

def ready(root,config=None):
    root=Path(root);config=config or settings(root)
    folder=root/'runtime/remix'/config['backend']
    binary=folder/('audiocpp_cli.exe' if __import__('os').name=='nt' else 'audiocpp_cli')
    ffmpeg=root/'runtime/remix/ffmpeg.exe'
    py=root/'runtime/remix/transcription/python.exe'
    native=binary.is_file()
    if __import__('os').name=='nt':
        native=native and all((folder/n).is_file() for n in ('vcruntime140.dll','vcruntime140_1.dll','msvcp140.dll','vcomp140.dll'))
        if config['backend']=='cuda':native=native and all(any((d/n).is_file() for d in (folder,root/'runtime/music/cuda')) for n in ('cudart64_12.dll','cublas64_12.dll','cublasLt64_12.dll'))
    return {'media':ffmpeg.is_file(),'native':native,
            'separation':native and bool(config['separation_model']),
            'conversion':native and bool(config['conversion_model']),
            'score':py.is_file() and (py.parent/'ready.json').is_file() and bool(config['sheet_model']) and bool(config['mert_model'])}

def describe(root,admin=False):
    config=settings(root)
    return {'ready':ready(root,config),**({'settings':config} if admin else {'backend':config['backend'],'voice_steps':config['voice_steps']})}

def save(root,body):
    value=validate(body);path=Path(root)/'data/remix.json';path.parent.mkdir(parents=True,exist_ok=True)
    with LOCK:
        part=path.with_suffix('.tmp');part.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8');os.replace(part,path)
    return describe(root,True)

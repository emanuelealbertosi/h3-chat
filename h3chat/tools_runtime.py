"""Private wheels and local CTranslate2 model directories, never remote code."""
import json
import hashlib
from pathlib import Path
from .external_models import absolute_path

REQUIRED={'latex':('TinyTeX/bin/windows/latex.exe','TinyTeX/bin/windows/dvisvgm.exe','TinyTeX/texmf-dist/tex/latex/standalone/standalone.cls'),
          'documents':('pypdf/__init__.py','docx/__init__.py','lxml/etree.cp313-win_amd64.pyd','pypdfium2/__init__.py','av/__init__.py','numpy/__init__.py','msvcp140.dll'),
          'lab':('manim/__init__.py','matplotlib/__init__.py','manimpango/__init__.py','cairo/__init__.py','msvcp140.dll'),
          'asr':('faster_whisper/__init__.py','ctranslate2/__init__.py','av/__init__.py','tokenizers/__init__.py','msvcp140.dll')}

def status(root):
    root=Path(root)
    result={}
    for kind,names in REQUIRED.items():
        try:ready=json.loads((root/'runtime/tools'/kind/'ready.json').read_text(encoding='utf-8')).get('manifest')==manifest_digest(root,kind) and all((root/'runtime/tools'/kind/name).is_file() for name in names)
        except (OSError,ValueError,KeyError):ready=False
        result[kind]={'ready':ready}
    return result

def manifest_digest(root,kind):
    root=Path(root);files=json.loads((root/'runtimes.json').read_text(encoding='utf-8'))['tools_'+kind]['files']
    crt=(root/'native/redist/SOURCES.json').read_text(encoding='utf-8')
    return hashlib.sha256((json.dumps(files,sort_keys=True)+crt).encode()).hexdigest()

def mark_ready(root,kind):
    target=Path(root)/'runtime/tools'/kind/'ready.json';target.parent.mkdir(parents=True,exist_ok=True)
    part=target.with_suffix('.writing');part.write_text(json.dumps({'manifest':manifest_digest(root,kind)}),encoding='utf-8');part.replace(target)

def model_path(root,setting):
    if setting in ('whisper-small','whisper-tiny'):p=Path(root)/'models'/setting
    else:p=absolute_path(setting)
    if not p.is_dir() or any(not (p/name).is_file() for name in ('model.bin','config.json','tokenizer.json')):
        raise ValueError('Trascrizione: scegli una cartella Faster Whisper/CTranslate2 con model.bin, config.json e tokenizer.json, oppure scarica il modello dall’admin.')
    try:config=json.loads((p/'config.json').read_text(encoding='utf-8'))
    except (OSError,ValueError):raise ValueError('Configurazione del modello di trascrizione non valida.')
    if config.get('model_type') not in (None,'Whisper') or config.get('n_mels',80) not in (80,128):raise ValueError('La cartella non contiene un modello Whisper compatibile.')
    return p.resolve()

def pure_transcription(prompt,audios):
    import re
    return bool(audios and re.fullmatch(r'\s*(?:trascrivi|transcribe)(?:\s+(?:questo|questa|il|la|l[’\x27])?\s*(?:audio|registrazione|traccia|file|allegato|audio allegato))?[.!?\s]*',prompt,re.I))

def validate(settings):
    for key in ('web_auto','transcribe_auto'):
        if type(settings[key]) is not bool:raise ValueError('Opzione strumenti non valida: '+key)
    if settings['web_provider'] not in ('duckduckgo','bing','searxng'):raise ValueError('Provider ricerca non valido.')
    if type(settings['web_max_results']) is not int or not 1<=settings['web_max_results']<=5:raise ValueError('Scegli da 1 a 5 fonti web.')
    url=settings['web_searxng_url']
    if not isinstance(url,str) or len(url)>2000:raise ValueError('Indirizzo SearXNG non valido.')
    if url:
        from urllib.parse import urlsplit
        p=urlsplit(url)
        if p.scheme not in ('http','https') or not p.hostname or p.username or p.password or p.query or p.fragment:raise ValueError('Usa l’indirizzo base di SearXNG senza credenziali o query.')
    if type(settings['asr_threads']) is not int or not 1<=settings['asr_threads']<=32:raise ValueError('Thread trascrizione: da 1 a 32.')
    if type(settings['asr_beam']) is not int or not 1<=settings['asr_beam']<=5:raise ValueError('Beam trascrizione: da 1 a 5.')
    if not isinstance(settings['asr_language'],str) or settings['asr_language'] not in ('auto','it','en','fr','de','es','pt','ja','zh','ru','ar'):raise ValueError('Lingua trascrizione non valida.')
    if settings['asr_model'] not in ('whisper-small','whisper-tiny'):absolute_path(settings['asr_model'])

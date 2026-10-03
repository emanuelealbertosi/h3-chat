"""Validated WAV/MP3 downloads, preserving originals and caching conversions."""
import hashlib
from pathlib import Path
import re
import subprocess
import threading
from .downloads import safe_join
from .engine import CREATE_NO_WINDOW
from .tools_runtime import status

_conversion_lock=threading.Lock()


def export_audio(root,data,item,format):
    if format not in ('wav','mp3'):raise ValueError('Scegli WAV oppure MP3.')
    relative=str(item.get('path',''))
    if not item.get('mime','').startswith('audio/') or not relative.startswith(('uploads/','outputs/')):
        raise ValueError('Seleziona una traccia audio della chat.')
    source=safe_join(data,relative)
    if source.suffix.lower() not in ('.wav','.mp3','.flac','.ogg') or not source.is_file():
        raise ValueError('Traccia audio non disponibile.')
    name=re.sub(r'[\x00-\x1f<>:"/\\|?*]','_',Path(str(item.get('name','audio'))).stem).strip(' .')[:140] or 'audio'
    result={'name':name+'.'+format,'mime':'audio/mpeg' if format=='mp3' else 'audio/wav'}
    if source.suffix.lower()=='.'+format:return result|{'url':'/media/'+relative}
    if not status(root)['documents']['ready']:
        raise ValueError('Aggiorna i componenti audio con install.bat oppure dal Setup → Strumenti → Documenti.')
    with source.open('rb') as stream:digest=hashlib.file_digest(stream,'sha256').hexdigest()
    key=hashlib.sha256((digest+format+'audio-v1-320k-pcm16').encode()).hexdigest()
    folder=safe_join(Path(data)/'exports','audio-'+key);target=folder/('audio.'+format)
    with _conversion_lock:
        if not target.is_file():
            folder.mkdir(parents=True,exist_ok=True);part=target.with_suffix('.partial')
            try:
                process=subprocess.run([str(Path(root)/'runtime/python/python.exe'),'-X','utf8',str(Path(root)/'native/audio-export-worker.py'),str(source),str(part),format],
                    cwd=root,capture_output=True,timeout=300,creationflags=CREATE_NO_WINDOW)
                if process.returncode or not part.is_file() or part.stat().st_size<32:
                    raise ValueError('Impossibile convertire la traccia audio. Verifica che il file sia valido.')
                part.replace(target)
            except subprocess.TimeoutExpired as exc:raise ValueError('La conversione audio ha superato il tempo disponibile. Riprova con una traccia più breve.') from exc
            finally:part.unlink(missing_ok=True)
    return result|{'url':'/exports/audio-'+key+'/audio.'+format}

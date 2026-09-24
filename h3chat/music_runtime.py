"""Application-private native music binaries: no H3-Music or external server."""
from pathlib import Path

def backend(settings):
 value=settings.get('music_backend','cuda')
 return ('cuda' if settings['profile']!='cpu' and settings['backend']=='cuda' else 'cpu') if value=='auto' else value

def executable(root,kind):
 path=Path(root)/'runtime/music'/kind/'h3-music-worker.exe'
 required=['h3-music-worker.exe','vcruntime140.dll','vcruntime140_1.dll','msvcp140.dll','vcomp140.dll']
 if kind=='cuda':required+=['cudart64_12.dll','cublas64_12.dll','cublasLt64_12.dll']
 return path if all((path.parent/name).is_file() for name in required) else None

def status(root):
 return {k:{'ready':bool(executable(root,k))} for k in ('cpu','cuda')}

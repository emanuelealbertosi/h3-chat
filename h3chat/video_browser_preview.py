"""Cached CPU browser copy; models and original source files are untouched."""
import threading
from .platform_runtime import python_executable

from .downloads import safe_join

LOCK=threading.Lock()


def progress(app,ident):
    media=app.validate_media([{'id':ident}])[0]
    if not media['mime'].startswith('video/'):raise ValueError('Scegli un video.')
    from .video_conversion_progress import read
    return read(safe_join(app.data,'outputs/browser-previews/'+media['id']+'/progress.json'))


def prepare(app, ident):
    media=app.validate_media([{'id':ident}])[0]
    if not media['mime'].startswith('video/'):raise ValueError('Scegli un video.')
    source=safe_join(app.data,media['path']);output=app.data/'outputs'/'browser-previews'/ident/'preview.mp4'
    from .video_conversion_progress import write
    progress_file=output.parent/'progress.json';write(progress_file,'In attesa della conversione')
    # Serialize conversions across users; the CPU job does not activate a model.
    with LOCK:
        if app.closed.is_set():raise ValueError('Applicazione in chiusura.')
        if not output.is_file():
            output.parent.mkdir(parents=True,exist_ok=True)
            from .residency import Session
            # A browsing preview must not replace the active job's tool_session
            # cancellation handle (or activate/offload any GPU model).
            session=Session(('preview',ident),'tool',{'id':'video-browser-worker.py','name':'Anteprima video'},{},{},output.parent/'preview.log')
            try:
                session.start([python_executable(app.root),'-X','utf8',app.root/'native/video-browser-worker.py'],ipc=True,cwd=app.root)
                session.wait('hello',app.closed,30);session.send({'source':str(source),'output':str(output)})
                session.wait('result',app.closed,7200)
            except Exception:
                write(progress_file,'Conversione non riuscita',status='failed');raise
            finally:session.stop()
        write(progress_file,'Anteprima pronta',status='done',done=1,total=1)
    return {'url':'/media/'+output.relative_to(app.data).as_posix(),'original_preserved':True}

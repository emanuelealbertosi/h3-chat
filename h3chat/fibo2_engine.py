"""The image pipeline runs in a private, offline process with normal cancellation."""
from .fibo2 import status


def start(engine,session,model,settings,log_path,cancel,stage):
    if not status(engine.root)['ready']:raise ValueError('Installa il componente opzionale FIBO 2.0 prima di generare.')
    backend='cpu' if settings['profile']=='cpu' else settings['backend']
    if backend not in ('cpu','cuda'):raise ValueError('FIBO 2.0 richiede NVIDIA CUDA oppure CPU; Vulkan non supportato.')
    with engine.process_lock:
        if cancel.is_set():
            from .downloads import Cancelled
            raise Cancelled()
        session.start([engine.root/'runtime/python/python.exe','-I','-X','utf8',engine.root/'native/fibo2-worker.py'],ipc=True,cwd=engine.root)
    session.wait('hello',cancel,30)
    from .image_options import options
    memory=(settings.get('_image_options') or options(model,settings)).get('fibo_offload','sequential')
    session.send({'op':'load','backend':backend,'files':session.files,'threads':settings['threads'],'fibo_offload':memory})
    session.wait('ready',cancel,900,stage);session.ready=True
    return session

"""Small host-platform boundary; Windows defaults remain unchanged."""
import sys
from pathlib import Path


def is_macos():return sys.platform=='darwin'


def python_executable(root):
    return Path(root)/('runtime/python/bin/python3' if is_macos() else 'runtime/python/python.exe')


def prepare_environment(root):
    if is_macos():
        import os
        certificates=Path(root)/'runtime/tools/documents/certifi/cacert.pem'
        if certificates.is_file():
            os.environ.setdefault('SSL_CERT_FILE',str(certificates))
            os.environ.setdefault('REQUESTS_CA_BUNDLE',str(certificates))


def info():
    import platform
    return {'system':sys.platform,'architecture':platform.machine(),
            'local_media':not is_macos(),'local_code_execution':not is_macos(),
            'backends':['cpu','metal'] if is_macos() else ['cpu','vulkan','cuda']}


def require_local_model(model):
    if is_macos() and not model.get('api') and not model.get('remote_media') and 'chat' not in model.get('capabilities',[]):
        raise ValueError('Su macOS questo motore generativo locale non è ancora disponibile. Configura un servizio esterno nelle impostazioni API.')


def guard_settings(settings):
    if is_macos() and settings.get('_lab')=='manim':
        raise ValueError('Manim non è ancora disponibile in questa edizione macOS. Puoi usare slide, canvas e calcolo numerico.')


def runtime_ready(root,key):
    from .engine import runtime_executable
    from .tools_runtime import status
    if key in ('cpu','metal'):return bool(runtime_executable(root,key,'llama'))
    if key=='tools_documents':return status(root)['documents']['ready']
    return False

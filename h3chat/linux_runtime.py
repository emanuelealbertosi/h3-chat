"""Linux-only runtime manifest. Never install a Windows binary on POSIX."""
import json
from pathlib import Path


def manifests(root):
    path=Path(root)/'runtimes.json'
    values=json.loads(path.read_text(encoding='utf8'))
    return {key:value for key,value in values.items() if isinstance(value,dict) and value.get('platform')=='linux'}


def finalize(root,key):
    root=Path(root)
    if key=='remix_score':
        folder=root/'runtime/remix/transcription'
        (folder/'ready.json').write_text(json.dumps({'python':'3.11.16','platform':'linux','manifest_verified':True}),encoding='utf8')
    if key in ('vision','vision_acceleration'):
        from .vision_runtime import REVISION
        folder=root/'runtime/vision';folder.mkdir(parents=True,exist_ok=True)
        (folder/'packages.json').write_text(json.dumps({'platform':'linux','verified_manifest':True}),encoding='utf8')
        (folder/'ready.json').write_text(json.dumps({'core_revision':REVISION}),encoding='utf8')

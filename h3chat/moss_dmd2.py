"""Optional MOSS DMD2 controls; no model or Torch imports in the web process."""
import json
from pathlib import Path

RECIPE = {'steps':8, 'cfg':1, 'sampler':'euler', 'scheduler':'sgm_uniform'}
SHA256 = '7683fe1fb51f73f5d690f24dd6b7f46f31ab9a9873729a854ac5c9a420ffe6f2'
SIZE = 1189176800


def validate(value, moss=None):
    if 'moss_turbo' in value and type(value['moss_turbo']) is not bool:
        raise ValueError('Turbo DMD2: scegli attivo o disattivo.')
    previous=value.get('moss_turbo_previous')
    if previous is not None:
        if not isinstance(previous,dict) or set(previous)!=set(RECIPE):
            raise ValueError('Impostazioni precedenti Turbo DMD2 non valide.')
        from .image_options import validate_overrides
        validate_overrides({'previous':previous})
    if moss is False and (value.get('moss_turbo') or previous is not None):
        raise ValueError('Turbo DMD2 è disponibile soltanto per MOSS e Kromoss.')


def effective(value):
    return value|RECIPE if value.get('moss_turbo') else value


def status(root):
    try:
        value=json.loads((Path(root)/'data/moss-dmd2.json').read_text(encoding='utf-8'))
        path=Path(value['path'])
        ready=value.get('sha256')==SHA256 and path.is_file() and path.stat().st_size==SIZE
    except (OSError,ValueError,KeyError,TypeError):ready=False
    return {'ready':ready,'recipe':RECIPE,'experimental_sft':True}


def adapter_path(root):
    if not status(root)['ready']:
        raise ValueError('Installa il componente DMD2 per MOSS prima di attivare Turbo.')
    return json.loads((Path(root)/'data/moss-dmd2.json').read_text(encoding='utf-8'))['path']

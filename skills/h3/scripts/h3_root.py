"""Find an H3-Chat installation without assuming a drive or user profile."""
import os
from pathlib import Path


def is_installation(path):
    return (path/'app.py').is_file() and (path/'h3chat').is_dir() and (path/'catalog.json').is_file()


def find_root(explicit=None):
    selected=explicit if explicit is not None else os.environ.get('H3_CHAT_ROOT')
    if selected is not None:
        root=Path(selected).expanduser().resolve()
        if not is_installation(root):raise ValueError('H3-Chat non trovato nel percorso scelto: '+str(root))
        return root
    # A bundled skill belongs to its containing checkout/portable folder. An
    # installed copy can instead be invoked from inside the intended project.
    for start in (Path(__file__).resolve().parent,Path.cwd().resolve()):
        for root in (start,*start.parents):
            if is_installation(root):return root
    raise ValueError('Indica la cartella H3-Chat con --root o con H3_CHAT_ROOT; nessuna installazione trovata.')

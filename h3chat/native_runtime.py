"""Install the signed, unmodified Microsoft CRT beside private native engines."""
import hashlib
import json
import os
from pathlib import Path


def install_redist(root, destination):
    root=Path(root).resolve();destination=Path(destination).resolve()
    if destination.parent.parent!=root/'runtime' or destination.parent.name not in ('cpu','cuda','vulkan') or destination.name not in ('llama','sd'):
        return []
    source=root/'native/redist'
    manifest=json.loads((source/'SOURCES.json').read_text(encoding='utf-8'))
    verified=[]
    for name,expected in manifest['files'].items():
        if Path(name).name!=name or not name.endswith('.dll'):raise ValueError('Nome libreria CRT non valido.')
        data=(source/name).read_bytes()
        if hashlib.sha256(data).hexdigest()!=expected:raise ValueError('Libreria CRT danneggiata: '+name)
        verified.append((destination/name,data))
    destination.mkdir(parents=True,exist_ok=True)
    for path,data in verified:
        if path.exists() and path.read_bytes()==data:continue
        temp=path.with_name(path.name+'.installing');temp.write_bytes(data);os.replace(temp,path)
    return [path for path,_ in verified]

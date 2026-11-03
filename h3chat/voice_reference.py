"""Explicit owner-local replacements of legacy stock voice references."""
import hashlib,json
from pathlib import Path


def reference(root,settings,gender):
    original=settings['voice_references'][gender]
    # H3 infographics currently author Italian narration. Never silently replace
    # a custom reference, an unrelated file or a reference used for another tool.
    infographic=settings.get('_infographic')
    if not isinstance(infographic,dict) or not infographic.get('voice'):return original,None
    path=Path(root)/'data/voices/reference-migrations.json'
    if not path.is_file():return original,None
    records=json.loads(path.read_text(encoding='utf-8'))
    for row in records:
        if row.get('gender')!=gender or row.get('language')!='it':continue
        old=Path(original['path']).resolve();source=Path(row['from']).resolve();target=Path(row['to']).resolve()
        allowed=(Path(root)/'data/voices').resolve()
        if old!=source or old.parent!=allowed or target.parent!=allowed or not target.is_file() or not old.is_file():continue
        if hashlib.sha256(old.read_bytes()).hexdigest()!=row.get('from_sha256'):continue
        return {'path':str(target),'transcript':row.get('transcript','')},row.get('reason','Campione italiano aggiornato')
    return original,None

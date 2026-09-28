"""Precompiled UI/launcher/native worker for compiler-free clone installation."""
import hashlib
import json
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def sources(root):
    paths = [*sorted((root/'ui').rglob('*.js')), root/'package.json', root/'package-lock.json',
             root/'scripts/build-ui.mjs', root/'scripts/Launcher.cs', root/'native/sd-worker.cpp',
             *sorted((root/'native/vendor').glob('*'))]
    return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes().replace(b'\r\n', b'\n')).hexdigest()
            for p in paths if p.is_file()}

def verify_sources(root, manifest):
    if sources(root) != manifest['sources']:
        raise ValueError('Componenti precompilati non allineati ai sorgenti. Scarica una versione completa oppure ricostruisci il bundle come documentato.')

def build(root=ROOT):
    paths = [root/'H3-Chat.exe', root/'native/h3-sd-worker.exe', root/'static/app.js', root/'static/app.js.LEGAL.txt',
             *sorted((root/'static/vendor').rglob('*'))]
    files = {p.relative_to(root).as_posix(): p for p in paths if p.is_file()}
    for name in ('H3-Chat.exe', 'native/h3-sd-worker.exe', 'static/app.js', 'static/vendor/katex.min.css'):
        if name not in files: raise ValueError('Build incompleta: '+name)
    out = root/'distribution'; out.mkdir(exist_ok=True)
    archive = out/'windows-bootstrap.zip'
    with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for name, path in sorted(files.items()):
            info = zipfile.ZipInfo(name, (2026, 1, 1, 0, 0, 0)); info.compress_type=zipfile.ZIP_DEFLATED
            z.writestr(info, path.read_bytes())
    manifest = {'archive': archive.name, 'size': archive.stat().st_size, 'sha256': digest(archive),
                'sources': sources(root), 'files': {name: digest(path) for name,path in files.items()}}
    (out/'windows-bootstrap.json').write_text(json.dumps(manifest, indent=2)+'\n', encoding='utf-8')
    print('Bundle clone pronto:', archive, archive.stat().st_size, 'bytes')

if __name__ == '__main__': build()

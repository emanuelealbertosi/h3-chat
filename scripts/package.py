"""Build a clean portable release; never include personal data or model weights."""
import hashlib
import json
import zipfile
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'scripts')]
INCLUDE=('native','h3chat','static','licenses','docs','scripts/Launcher.cs','scripts/install.ps1','scripts/bootstrap-python.ps1','scripts/install.py','scripts/bootstrap_bundle.py','scripts/check_native.py','scripts/build-ui.mjs','distribution','ui','package.json','package-lock.json','install.bat','start.bat','stop.bat','app.py','launcher.py','catalog.json','runtimes.json',
         'H3-Chat.exe','Installa-H3-Chat.bat','Avvia-H3-Chat.bat','Ferma-H3-Chat.bat','README.md','LICENSE','NOTICE','runtime/python','runtime/music/cpu','runtime/tools/documents','tools-models.json','scripts/tools-sources.json','scripts/lab-sources.json','scripts/lab-requirements.txt','scripts/latex-sources.json')

INCLUDE=(*INCLUDE,'scripts/reset_admin_password.py')

def main():
    for required in ('runtime/python/python.exe','H3-Chat.exe','static/app.js','native/h3-sd-worker.exe','runtime/music/cpu/h3-music-worker.exe','runtime/cpu/llama/llama-server.exe','runtime/cpu/sd/stable-diffusion.dll','README.md'):
        if not (ROOT/required).exists():raise SystemExit('Missing: '+required)
    from h3chat.native_runtime import install_redist
    from h3chat.tools_runtime import status
    if not status(ROOT)['documents']['ready']:
        raise SystemExit('Missing or incomplete document runtime: run install.bat first.')
    for backend in ('cpu',):
        for engine in ('llama','sd'):install_redist(ROOT,ROOT/'runtime'/backend/engine)
    from bootstrap_bundle import verify_sources
    verify_sources(ROOT,json.loads((ROOT/'distribution/windows-bootstrap.json').read_text(encoding='utf-8')))
    files=[]
    for relative in INCLUDE:
        source=ROOT/relative
        if source.is_dir():files.extend(p for p in source.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc')
        elif source.is_file():files.append(source)
    # Include CPU motors for a immediately self-contained release; GPU backends install from UI.
    for engine in ('llama','sd'):
        source=ROOT/'runtime/cpu'/engine
        if source.exists():files.extend(p for p in source.rglob('*') if p.is_file())
    out=ROOT/'dist';out.mkdir(exist_ok=True)
    import sys
    sys.path.insert(0,str(ROOT))
    from h3chat import __version__
    archive=out/f'H3-Chat-{__version__}-windows-x64.zip'
    manifest={}
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for file in sorted(set(files)):
            rel=file.relative_to(ROOT).as_posix()
            data=file.read_bytes();manifest[rel]=hashlib.sha256(data).hexdigest();z.writestr('H3-Chat/'+rel,data)
        z.writestr('H3-Chat/FILES-SHA256.json',json.dumps(manifest,indent=2))
    digest=hashlib.sha256(archive.read_bytes()).hexdigest()
    (out/(archive.name+'.sha256')).write_text(digest+'  '+archive.name+'\n')
    print(archive,round(archive.stat().st_size/1e6,1),'MB',digest)


if __name__=='__main__':main()

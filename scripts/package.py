"""Build a clean portable release; never include personal data or model weights."""
import hashlib
import json
import zipfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
INCLUDE=('h3chat','static','licenses','docs','scripts/Launcher.cs','scripts/install.ps1','app.py','launcher.py','catalog.json','runtimes.json',
         'H3-Chat.exe','Installa-H3-Chat.bat','Avvia-H3-Chat.bat','Ferma-H3-Chat.bat','README.md','LICENSE','NOTICE','runtime/python')


def main():
    for required in ('runtime/python/python.exe','H3-Chat.exe','static/app.js','README.md'):
        if not (ROOT/required).exists():raise SystemExit('Missing: '+required)
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
    archive=out/'H3-Chat-0.1.0-windows-x64.zip'
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

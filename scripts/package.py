"""Build a clean portable release; never include personal data or model weights."""
import hashlib
import json
import zipfile
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'scripts')]
INCLUDE=('native','h3chat','static','licenses','docs','scripts/Launcher.cs','scripts/install.ps1','scripts/bootstrap-python.ps1','scripts/install.py','scripts/bootstrap_bundle.py','scripts/check_native.py','scripts/build-ui.mjs','distribution','ui','package.json','package-lock.json','install.bat','start.bat','stop.bat','app.py','launcher.py','catalog.json','runtimes.json',
         'H3-Chat.exe','Installa-H3-Chat.bat','Avvia-H3-Chat.bat','Ferma-H3-Chat.bat','README.md','LICENSE','NOTICE','runtime/python','runtime/music/cpu','runtime/tools/documents','tools-models.json','upscale-runtimes.json','scripts/tools-sources.json','scripts/lab-sources.json','scripts/lab-requirements.txt','scripts/latex-sources.json','scripts/install_qwen27_accelerator.py','scripts/benchmark_llm_accelerator.py')

INCLUDE=(*INCLUDE,'scripts/reset_admin_password.py','remix-runtimes.json','scripts/install-remix-score.py','scripts/build-remix-runtime.ps1','scripts/package-remix-runtime.py','scripts/model_download.py','runtime/bootstrap/pip.pyz','scripts/install-moss.py','scripts/moss-sources.json',
         'Avvia-server-immagini.bat','Installa-API-senza-GPU.bat','scripts/start-image-server.py','scripts/image-api-server.py','scripts/download-moss-bf16.py','scripts/convert-glp-lora.py','skills/h3')

# Git ignore rules do not apply to release archives. Keep local handoffs and
# production-run notes out even when an older checkout still contains them.
PRIVATE_FILES=frozenset(('docs/h3-session-state.json','docs/video-roadmap.md'))
PRIVATE_PARTS=frozenset(('.git','__pycache__','.pytest_cache','.mypy_cache'))


def release_file(path,root):
    relative=path.relative_to(root)
    return (relative.as_posix() not in PRIVATE_FILES
            and not any(part in PRIVATE_PARTS for part in relative.parts)
            and path.suffix.lower() not in ('.pyc','.pyo','.tmp','.bak','.log','.sqlite','.sqlite3')
            and not path.name.lower().endswith(('.orig','.rej','~'))
            and path.resolve().is_relative_to(root.resolve()))


def collect_files(root=ROOT):
    root=Path(root)
    files=[]
    # The allowlist supplies application/runtime sources, never data or models.
    for relative in (*INCLUDE,'runtime/cpu/llama','runtime/cpu/sd'):
        source=root/relative
        candidates=source.rglob('*') if source.is_dir() else (source,)
        files.extend(path for path in candidates if path.is_file() and release_file(path,root))
    return sorted(set(files))

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
    # Include CPU motors for a immediately self-contained release; GPU backends install from UI.
    files=collect_files()
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

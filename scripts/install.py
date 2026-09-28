"""Idempotent clone setup. No Node, compiler, system Python or personal data writes."""
import json
import os
import subprocess
import sys
import threading
import time
import zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'scripts')]
from h3chat.downloads import download, extract_zip, file_hash, safe_join
from bootstrap_bundle import verify_sources


def install_bundle(root=ROOT):
    manifest=json.loads((root/'distribution/windows-bootstrap.json').read_text(encoding='utf-8'))
    verify_sources(root,manifest)
    archive=root/'distribution/windows-bootstrap.zip'
    if archive.stat().st_size!=manifest['size'] or file_hash(archive)!=manifest['sha256']:
        raise ValueError('Bundle precompilato corrotto: riscarica il repository.')
    # Verify every member before replacing any installed component.
    with zipfile.ZipFile(archive) as z:
        if set(z.namelist())!=set(manifest['files']): raise ValueError('Contenuto bundle inatteso.')
        import hashlib
        pending=[]
        for name,expected in manifest['files'].items():
            target=safe_join(root,name)
            data=z.read(name)
            if hashlib.sha256(data).hexdigest()!=expected: raise ValueError('Checksum bundle errato: '+name)
            if not target.exists() or file_hash(target)!=expected: pending.append((target,data))
        for target,data in pending:
            target.parent.mkdir(parents=True,exist_ok=True)
            part=target.with_name(target.name+'.installing');part.write_bytes(data);os.replace(part,target)


def install_runtime(key,root=ROOT):
    manifest=json.loads((root/'runtimes.json').read_text(encoding='utf-8'))[key]
    marker=root/'runtime'/('installed-'+key+'.json')
    try:
        previous=json.loads(marker.read_text(encoding='utf-8'))
        if previous['manifest']==manifest and previous['files'] and all(safe_join(root,n).is_file() and file_hash(safe_join(root,n))==h for n,h in previous['files'].items()):
            print(key+': gia installato e verificato.',flush=True);return
    except (OSError,ValueError,KeyError):pass
    installed={}
    for entry in manifest['files']:
        archive=safe_join(root,entry['path'])
        last=-1
        def progress(current,total):
            nonlocal last
            percent=int(current*100/total)//10*10
            if percent!=last: print(archive.name+': '+str(percent)+'%',flush=True);last=percent
        for attempt in range(3):
            try:
                download(entry['url'],archive,entry['sha256'],entry['size'],threading.Event(),progress);break
            except Exception:
                if attempt==2:raise
                print('Download interrotto, riprendo...',flush=True);time.sleep(2)
        destination=safe_join(root,entry['extract_to'])
        if entry.get('extract_members'):
            from h3chat.downloads import extract_members
            extract_members(archive,destination,entry['extract_members'])
            targets=[safe_join(destination,n) for n in entry['extract_members'].values()]
        else:
            extract_zip(archive,destination)
            with zipfile.ZipFile(archive) as z: targets=[safe_join(destination,i.filename) for i in z.infolist() if not i.is_dir()]
        installed.update({p.relative_to(root).as_posix():file_hash(p) for p in targets})
    marker.write_text(json.dumps({'manifest':manifest,'files':installed},indent=2),encoding='utf-8')


def main():
    if sys.platform!='win32' or sys.maxsize<=2**32: raise ValueError('Questo pacchetto richiede Windows x64.')
    from launcher import running_servers
    if running_servers(8787): raise ValueError('H3-Chat e aperto. Termina i lavori, esegui stop.bat e rilancia install.bat.')
    print('[1/4] Interfaccia e launcher precompilati',flush=True);install_bundle()
    print('[2/4] Motori chat e immagini CPU',flush=True);install_runtime('cpu')
    print('[3/4] Motore musicale CPU',flush=True);install_runtime('music_cpu')
    print('[4/4] Verifica motori',flush=True)
    subprocess.run([sys.executable,'-X','utf8',str(ROOT/'scripts/check_native.py')],check=True)
    worker=ROOT/'runtime/music/cpu/h3-music-worker.exe'
    result=subprocess.run([str(worker)],input=b'',capture_output=True,cwd=worker.parent,timeout=30)
    if result.returncode or json.loads(result.stdout).get('event')!='hello': raise ValueError('Verifica motore musicale fallita.')
    print('H3-Chat pronto. Scegli modelli e GPU nel Setup. Preferenze e dati esistenti conservati.',flush=True)

if __name__=='__main__':
    try: main()
    except Exception as exc: print('Installazione non completata: '+str(exc),file=sys.stderr,flush=True);sys.exit(1)

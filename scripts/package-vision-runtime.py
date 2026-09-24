"""Package the optional runtime separately (no Python executable or model weights)."""
import hashlib
import json
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]
REVISION = '3b4c0b0e457cf0a51cf3038e0a6750d8f96ce251'


def main():
    source = ROOT/'runtime/vision'
    assert (source/'packages/torch/__init__.py').is_file()
    assert (source/'core/LICENSE').is_file()
    (source/'ready.json').write_text(json.dumps({'core_revision':REVISION,'python':'3.13','platform':'win_amd64'}),encoding='utf-8')
    files = [p for folder in ('core','packages') for p in (source/folder).rglob('*')
             if p.is_file() and '__pycache__' not in p.parts and p.suffix not in ('.pyc','.pth')]
    files += [source/'packages.json',source/'SOURCES.json']
    output = ROOT/'dist/H3-Chat-vision-engine-0.7.0-windows-x64.zip'
    output.parent.mkdir(exist_ok=True)
    manifest = {}
    with zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as archive:
        for i,file in enumerate(sorted(files)):
            name = file.relative_to(source).as_posix()
            with file.open('rb') as stream:
                manifest[name] = hashlib.file_digest(stream,'sha256').hexdigest()
            archive.write(file,name)
            if i % 5000 == 0:print(i,'/',len(files),flush=True)
        archive.writestr('FILES-SHA256.json',json.dumps(manifest,indent=2))
        archive.write(source/'ready.json','ready.json')
    with output.open('rb') as stream:sha=hashlib.file_digest(stream,'sha256').hexdigest()
    output.with_suffix('.zip.sha256').write_text(sha+'  '+output.name+'\n',encoding='utf-8')
    manifest_path=ROOT/'runtimes.json'
    runtimes=json.loads(manifest_path.read_text(encoding='utf-8'))
    support = [f for f in runtimes.get('vision',{}).get('files',[]) if f.get('extract_to')=='runtime/vision/dlls']
    runtimes['vision']={'files':support+[{'path':'runtime/downloads/'+output.name,'extract_to':'runtime/vision',
        'url':'https://github.com/emanuelealbertosi/h3-chat/releases/download/v0.7.0/'+output.name,
        'size':output.stat().st_size,'sha256':sha}]}
    manifest_path.write_text(json.dumps(runtimes,indent=2)+'\n',encoding='utf-8')
    print(output,output.stat().st_size,sha,flush=True)


if __name__=='__main__':main()

"""Explicit optional P-H3 setup; shared image core and Torch remain intact."""
import argparse,json,subprocess,sys,urllib.request,urllib.error,zipfile
from pathlib import Path
from model_download import fetch,parallel_fetch
ROOT=Path(__file__).resolve().parents[1]

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--models-dir',type=Path,required=True)
    parser.add_argument('--runtime-only',action='store_true');args=parser.parse_args()
    manifest=json.loads((ROOT/'scripts/ph3-sources.json').read_text())
    runtime=ROOT/'runtime/ph3';downloads=runtime/'downloads';downloads.mkdir(parents=True,exist_ok=True)
    core=manifest['core'];archive=downloads/'core.zip'
    fetch('https://codeload.github.com/Comfy-Org/ComfyUI/zip/'+core['revision'],archive,digest=core['archive_sha256'])
    folder=runtime/'core';folder.mkdir(exist_ok=True)
    with zipfile.ZipFile(archive) as bundle:
        prefix=bundle.namelist()[0].split('/')[0]+'/'
        for item in bundle.infolist():
            name=item.filename.removeprefix(prefix)
            if not name or item.is_dir():continue
            target=(folder/name).resolve()
            if not target.is_relative_to(folder.resolve()):raise ValueError('Percorso runtime non valido.')
            if name in ('LICENSE','NOTICE') or name.endswith(('.py','.json','.txt','.jinja','.model','.tiktoken','.yaml','.yml')) or name.startswith(('comfy/','comfy_api/','comfy_extras/')):
                target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(bundle.read(item))
    (runtime/'provenance.json').write_text(json.dumps(core,indent=2)+'\n')
    pip=ROOT/'runtime/bootstrap/pip.pyz'
    subprocess.run([sys.executable,str(pip),'install','--no-deps','--only-binary=:all:','--target',str(runtime/'packages'),
                    '--cache-dir',str(downloads/'pip-cache'),*manifest['packages']],check=True)
    if not args.runtime_only:
        for item in manifest['files']:
            path=args.models_dir/item['path'];path.parent.mkdir(parents=True,exist_ok=True)
            url=f"https://huggingface.co/{manifest['repository']}/resolve/{manifest['revision']}/{item['path']}"
            if path.exists():fetch(url,path,item['size'],item['sha256'])
            else:parallel_fetch(url,path,item['size'],item['sha256'],workers=16)
        for name in ('LICENSE','NOTICE'):
            try:
                data=urllib.request.urlopen(f"https://huggingface.co/{manifest['repository']}/resolve/{manifest['revision']}/{name}",timeout=60).read()
                (args.models_dir/name).write_bytes(data)
            except urllib.error.HTTPError as exc:
                if exc.code!=404:raise
        (args.models_dir/'h3-installation.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print('Runtime P-H3 pronto. Collega i componenti nel Catalogo: P-H3-Image.')

if __name__=='__main__':main()

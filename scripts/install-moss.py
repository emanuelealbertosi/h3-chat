"""Install the pinned optional MOSS plugin and its small set of components.

Existing diffusion weights stay in place. No shared Python packages/core are
upgraded, and model registration remains an explicit application operation.
"""
import argparse,concurrent.futures,hashlib,importlib.util,json,shutil,time,threading,urllib.request
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def parallel_fetch(url,path,size,digest,workers=24):
    """Resolve once, then resume verified byte ranges on the official CDN."""
    part=path.with_suffix(path.suffix+'.part');manifest=part.with_suffix('.chunks.json');chunk=32*1024**2
    saved=json.loads(manifest.read_text()) if manifest.exists() else {}
    done=set(saved.get('done',[])) if saved.get('size')==size and saved.get('url')==url and part.exists() else set()
    if not done:
        with part.open('wb') as file:file.truncate(size)
    with urllib.request.urlopen(urllib.request.Request(url,method='HEAD'),timeout=90) as response:direct=response.geturl()
    writer=threading.Lock()
    def block(index):
        start=index*chunk;end=min(size,start+chunk)-1
        for attempt in range(3):
            try:
                with urllib.request.urlopen(urllib.request.Request(direct,headers={'Range':f'bytes={start}-{end}'}),timeout=90) as response:
                    if response.status!=206 or response.headers.get('Content-Range')!=f'bytes {start}-{end}/{size}':raise RuntimeError('Intervallo MOSS inatteso.')
                    content=response.read(end-start+1)
                    if len(content)!=end-start+1:raise RuntimeError('Blocco MOSS incompleto.')
                # USB hard disks suffer badly from interleaved range writes.
                # Buffer at most 24 × 32 MiB and publish whole blocks serially.
                with writer,part.open('r+b') as file:
                    file.seek(start);file.write(content)
                return index
            except Exception as exc:
                print(f'MOSS blocco {index}, tentativo {attempt+1}: {type(exc).__name__}',flush=True)
                if attempt==2:raise
    count=(size+chunk-1)//chunk;last=0
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        for future in concurrent.futures.as_completed([pool.submit(block,n) for n in range(count) if n not in done]):
            done.add(future.result());temp=manifest.with_suffix('.tmp');temp.write_text(json.dumps({'url':url,'size':size,'done':sorted(done)}));temp.replace(manifest)
            if time.monotonic()-last>10:print(f'MOSS: {len(done)}/{count} blocchi completati',flush=True);last=time.monotonic()
    with part.open('rb') as stream:actual=hashlib.file_digest(stream,'sha256').hexdigest()
    if actual!=digest:raise RuntimeError('SHA256 MOSS errato: file non attivato.')
    part.replace(path);manifest.unlink(missing_ok=True)

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--model-root',type=Path,required=True);args=parser.parse_args()
    if not args.model_root.is_absolute():raise ValueError('Indica una cartella assoluta per encoder e VAE.')
    manifest=json.loads((ROOT/'scripts/moss-sources.json').read_text());home=ROOT/'runtime/vision/moss_image';home.mkdir(parents=True,exist_ok=True)
    for item in manifest['files']:
        request=f"https://raw.githubusercontent.com/{manifest['repository']}/{manifest['revision']}/{item['path']}"
        with urllib.request.urlopen(request,timeout=90) as response:content=response.read()
        blob=b'blob '+str(len(content)).encode()+b'\0'+content
        if hashlib.sha1(blob).hexdigest()!=item['git_sha1']:raise RuntimeError('Codice MOSS diverso dalla revisione verificata.')
        (home/Path(item['path']).name).write_bytes(content)
    args.model_root.mkdir(parents=True,exist_ok=True)
    files=manifest['weights']['files'];needed=sum(x['size'] for x in files if not (args.model_root/x['rfilename']).is_file() and not (args.model_root/(x['rfilename']+'.part')).is_file())
    if shutil.disk_usage(args.model_root).free<needed+512*1024**2:raise RuntimeError('Spazio insufficiente per encoder e VAE MOSS.')
    spec=importlib.util.spec_from_file_location('moss_download',ROOT/'scripts/model_download.py');download=importlib.util.module_from_spec(spec);spec.loader.exec_module(download)
    download.parallel_fetch=parallel_fetch
    for item in files:
        print('MOSS: '+item['rfilename'],flush=True)
        download.fetch(f"https://huggingface.co/Comfy-Org/MOSS-Image/resolve/{manifest['weights']['revision']}/{item['rfilename']}",args.model_root/item['rfilename'],item['size'],item['lfs']['sha256'])
    (home/'provenance.json').write_text(json.dumps(manifest,indent=2))
    print('MOSS pronto per il collegamento del diffusore nelle impostazioni. Pesi verificati.',flush=True)

if __name__=='__main__':main()

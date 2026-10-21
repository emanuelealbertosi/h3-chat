"""Download and verify the official Comfy-Org SFT BF16 diffusion weights."""
import hashlib,importlib.util,json,shutil,urllib.request,time,threading,subprocess,os
from concurrent.futures import ThreadPoolExecutor,as_completed
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
PATH=Path('F:/sd-webui-forge-neo/models/Stable-diffusion/moss_image_sft_bf16.safetensors')
REV='3284a1dbb351e3396d70f39f2a71cbf6ed2ef1bb'
SHA='f96738d8116d78b7316b57c663d8c98591ddafab7488f48e3099b7655e34ab6f'
SIZE=10164655808

def transfer(url):
    part=PATH.with_suffix(PATH.suffix+'.part');journal=part.with_suffix('.chunks.json');chunk=8*1024**2
    saved=json.loads(journal.read_text()) if journal.exists() else {}
    if saved and (saved.get('size')!=SIZE or saved.get('url')!=url):raise RuntimeError('Unexpected resume journal')
    previous=saved.get('chunk',32*1024**2)
    done={n for old in saved.get('done',[]) for n in range(old*(previous//chunk),min((old+1)*(previous//chunk),(SIZE+chunk-1)//chunk))}
    if not part.exists():
        with part.open('wb') as stream:stream.truncate(SIZE)
    elif part.stat().st_size!=SIZE:raise RuntimeError('Unexpected partial size')
    count=(SIZE+chunk-1)//chunk;writer=threading.Lock()
    def block(n):
        start=n*chunk;end=min(SIZE,start+chunk)-1
        for attempt in range(4):
            try:
                request=urllib.request.Request(url+f'?download=true&h3block8={n}',headers={'Range':f'bytes={start}-{end}'})
                with urllib.request.urlopen(request,timeout=45) as response:
                    if response.status!=206 or response.headers.get('Content-Range')!=f'bytes {start}-{end}/{SIZE}':raise RuntimeError('Unexpected range')
                    content=response.read(end-start+1)
                if len(content)!=end-start+1:raise RuntimeError('Incomplete range')
                with writer,part.open('r+b') as stream:stream.seek(start);stream.write(content)
                return n
            except OSError:
                if attempt==3:raise
    last=0
    with ThreadPoolExecutor(max_workers=24) as pool:
        for future in as_completed([pool.submit(block,n) for n in range(count) if n not in done]):
            done.add(future.result());temp=journal.with_suffix('.tmp')
            temp.write_text(json.dumps({'url':url,'size':SIZE,'chunk':chunk,'done':sorted(done)}));temp.replace(journal)
            if time.monotonic()-last>15:print(f'MOSS BF16: {len(done)/count:.1%} ({len(done)}/{count} blocks)',flush=True);last=time.monotonic()
    with part.open('rb') as stream:
        if hashlib.file_digest(stream,'sha256').hexdigest()!=SHA:raise RuntimeError('BF16 hash mismatch')
    part.replace(PATH);journal.unlink()

def main():
    work=ROOT/'work/moss-bf16-2026-10-18';work.mkdir(parents=True,exist_ok=True)
    if shutil.disk_usage(PATH.parent).free<SIZE+8*1024**3:raise RuntimeError('Not enough space with reserve')
    if not PATH.exists():transfer(f'https://huggingface.co/Comfy-Org/MOSS-Image/resolve/{REV}/diffusion_models/{PATH.name}')
    with PATH.open('rb') as stream:
        if PATH.stat().st_size!=SIZE or hashlib.file_digest(stream,'sha256').hexdigest()!=SHA:raise RuntimeError('BF16 hash mismatch')
    (work/'installed.json').write_text(json.dumps({'done':True,'path':str(PATH),'revision':REV,'bytes':SIZE,'sha256':SHA,'precision':'BF16','variant':'SFT','gpu_tested':False},indent=2))
    env=os.environ.copy();env.update(CUDA_VISIBLE_DEVICES='-1',OMP_NUM_THREADS='2')
    bootstrap="import os,sys,runpy;handle=os.add_dll_directory(sys.argv[1]);sys.path[:0]=sys.argv[2:5];runpy.run_path(sys.argv[5],run_name='__main__')"
    subprocess.run([str(ROOT/'runtime/python/python.exe'),'-X','utf8','-c',bootstrap,str(ROOT/'runtime/vision/dlls'),str(ROOT),str(ROOT/'runtime/vision/packages'),str(ROOT/'runtime/vision/core'),str(work/'check-metadata.py')],env=env,cwd=ROOT,check=True)
    print('MOSS SFT BF16 installed, official SHA256 verified. No GPU used.',flush=True)

if __name__=='__main__':main()

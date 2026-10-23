"""Explicit download/verification of pinned MOSS BF16 weights; no GPU or registration."""
import argparse,hashlib,json,shutil,urllib.request,time,threading
from concurrent.futures import ThreadPoolExecutor,as_completed
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
FILENAME='moss_image_sft_bf16.safetensors'
REV='3284a1dbb351e3396d70f39f2a71cbf6ed2ef1bb'
SHA='f96738d8116d78b7316b57c663d8c98591ddafab7488f48e3099b7655e34ab6f'
SIZE=10164655808

def transfer(url,target):
    part=target.with_suffix(target.suffix+'.part');journal=part.with_suffix('.chunks.json');chunk=8*1024**2
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
    part.replace(target);journal.unlink(missing_ok=True)

def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    location=parser.add_mutually_exclusive_group(required=True)
    location.add_argument('--output',type=Path,help='Absolute destination file; filename may be customized.')
    location.add_argument('--model-root',type=Path,help='Absolute model root; writes Stable-diffusion/'+FILENAME)
    parser.add_argument('--verify-only',action='store_true',help='Only verify an existing file; never download or create files.')
    args=parser.parse_args(argv)
    target=args.output if args.output is not None else args.model_root/'Stable-diffusion'/FILENAME
    if not target.is_absolute():raise ValueError('Specify an absolute --output or --model-root path.')
    target=target.expanduser().resolve()
    if not target.exists():
        if args.verify_only:raise FileNotFoundError('BF16 file not found: '+str(target))
        target.parent.mkdir(parents=True,exist_ok=True)
        if shutil.disk_usage(target.parent).free<SIZE+8*1024**3:raise RuntimeError('Not enough space with reserve')
        transfer(f'https://huggingface.co/Comfy-Org/MOSS-Image/resolve/{REV}/diffusion_models/{FILENAME}',target)
    with target.open('rb') as stream:
        if target.stat().st_size!=SIZE or hashlib.file_digest(stream,'sha256').hexdigest()!=SHA:raise RuntimeError('BF16 hash mismatch; file not registered or modified.')
    # Attest the full pinned file without loading tensors or a private work script.
    print(json.dumps({'verified':True,'path':str(target),'revision':REV,'bytes':SIZE,'sha256':SHA,
                      'precision':'BF16','variant':'SFT','gpu_used':False,'registered':False}),flush=True)
    return 0

if __name__=='__main__':raise SystemExit(main())

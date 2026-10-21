"""Explicit, pinned FIBO download into the shared image model directory."""
import concurrent.futures,hashlib,json,os,shutil,sys,threading,time,urllib.request,urllib.error,urllib.parse
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
os.environ.update(HF_XET_CACHE=str(ROOT/'runtime/fibo2/cache/xet'),HF_HUB_CACHE=str(ROOT/'runtime/fibo2/cache/hub'),HF_HUB_DISABLE_XET='1',HF_HUB_DOWNLOAD_TIMEOUT='90',HF_HUB_DISABLE_TELEMETRY='1',TEMP='F:/H3-TestTmp',TMP='F:/H3-TestTmp')
sys.path.insert(0,str(ROOT/'runtime/vision/packages'))
from huggingface_hub import get_token

def fetch(url,path,size,token):
    path.parent.mkdir(parents=True,exist_ok=True)
    headers={'Authorization':'Bearer '+token} if token else {}
    direct='';direct_lock=threading.Lock();renewed=0
    def endpoint(force=False):
        nonlocal direct,renewed
        with direct_lock:
            if not direct or (force and time.monotonic()-renewed>5) or time.monotonic()-renewed>300:
                # A cached resolve redirect can outlive its signed CDN URL.
                # Ask the authenticated origin for a fresh redirect each time.
                fresh=url+('&' if '?' in url else '?')+'download=true&h3_nonce='+str(time.time_ns())
                # Some gated components authorize GET but reject a HEAD
                # redirect. Resolve with one byte, then use the CDN ranges.
                with urllib.request.urlopen(urllib.request.Request(fresh,headers=headers|{'Range':'bytes=0-0'}),timeout=30) as r:
                    direct=r.geturl();r.read(1)
                host=urllib.parse.urlsplit(direct).hostname or ''
                if host!='huggingface.co' and not host.endswith('.hf.co'):raise RuntimeError('Destinazione download FIBO inattesa.')
                renewed=time.monotonic()
            return direct
    part=path.with_name(path.name+'.fibo-part');record=path.with_name(path.name+'.fibo-chunks.json');chunk=4*1024**2
    state=json.loads(record.read_text()) if record.exists() else {};done=set()
    if state.get('size')==size and part.exists():
        previous=state.get('chunk_bytes',32*1024**2)
        for i in state.get('done',[]):
            if previous%chunk:raise RuntimeError('Formato di ripresa FIBO incompatibile.')
            done.update(range(i*previous//chunk,min((size+chunk-1)//chunk,(i+1)*previous//chunk)))
    if not done:
        with part.open('wb') as stream:stream.truncate(size)
    count=(size+chunk-1)//chunk;lock=threading.Lock();last=0
    def block(i):
        start=i*chunk;end=min(size,start+chunk)-1
        for attempt in range(3):
            try:
                destination=endpoint(attempt>0)
                with urllib.request.urlopen(urllib.request.Request(destination,headers=headers|{'Range':f'bytes={start}-{end}'}),timeout=30) as response:
                    if response.status!=206 or response.headers.get('Content-Range')!=f'bytes {start}-{end}/{size}':raise RuntimeError(f'Intervallo inatteso: HTTP {response.status}; Content-Range {response.headers.get("Content-Range")} per {start}-{end}.')
                    data=response.read(end-start+1)
                if len(data)!=end-start+1:raise RuntimeError('Intervallo FIBO incompleto.')
                with lock,part.open('r+b') as stream:stream.seek(start);stream.write(data)
                return i
            except Exception as exc:
                # Do not log signed URLs, request headers or credentials.
                detail=str(exc) if isinstance(exc,RuntimeError) else type(exc).__name__
                print(f'FIBO · blocco {i}: tentativo {attempt+1} non completato ({detail}, HTTP {getattr(exc,"code","-")})',flush=True)
                if attempt==2:raise
    pool=concurrent.futures.ThreadPoolExecutor(max_workers=64)
    try:
        remaining=iter(i for i in range(count) if i not in done)
        futures={pool.submit(block,i) for i in list(__import__('itertools').islice(remaining,64))}
        while futures:
            completed,_=concurrent.futures.wait(futures,return_when=concurrent.futures.FIRST_COMPLETED)
            for future in completed:
                futures.remove(future);item=future.result()
                done.add(item);record.write_text(json.dumps({'size':size,'chunk_bytes':chunk,'done':sorted(done)}))
                if time.monotonic()-last>10:print(f'FIBO · {path.parent.name}/{path.name}: {len(done)}/{count} blocchi',flush=True);last=time.monotonic()
                item=next(remaining,None)
                if item is not None:futures.add(pool.submit(block,item))
    finally:pool.shutdown(wait=True,cancel_futures=True)
    part.replace(path);record.unlink(missing_ok=True)

def main():
    target=Path('F:/sd-webui-forge-neo/models/Stable-diffusion/Fibo-2.0-dev')
    revision='530604492bf2bd1364ae43ca6b2bf2285ef0f2ba'
    manifest=json.loads((ROOT/'work/fibo2-research-2026-10-20/metadata.json').read_text())['siblings']
    files=[e for e in manifest if not e['rfilename'].startswith(('assets/','fine_tuning/','.gitattributes'))]
    needed=sum(e['size'] for e in files if not (target/e['rfilename']).exists())
    if shutil.disk_usage(target.parent).free<needed+8*1024**3:raise RuntimeError('Spazio insufficiente per pesi e margine temporaneo FIBO.')
    print('FIBO 2.0 · download autorizzato nella cartella comune dei modelli immagini',flush=True)
    token=get_token()
    for e in files:
        path=target/e['rfilename']
        if not path.is_file() or path.stat().st_size!=e['size']:
            fetch(f'https://huggingface.co/briaai/Fibo-2.0-dev/resolve/{revision}/'+e['rfilename'],path,e['size'],token)
    checked=[]
    for e in files:
        path=target/e['rfilename']
        if path.stat().st_size!=e['size']:raise RuntimeError('Dimensione errata: '+e['rfilename'])
        if e.get('lfs'):
            print('FIBO · verifica '+e['rfilename'],flush=True)
            with path.open('rb') as stream:actual=hashlib.file_digest(stream,'sha256').hexdigest()
            if actual!=e['lfs']['sha256']:raise RuntimeError('SHA256 errato: '+e['rfilename'])
        checked.append(e['rfilename'])
    report={'repository':'briaai/Fibo-2.0-dev','revision':revision,'path':str(target),'verified_files':checked,'ready_weights':True}
    (ROOT/'work/fibo2-research-2026-10-20/download.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report),flush=True)
if __name__=='__main__':main()

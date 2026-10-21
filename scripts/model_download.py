"""Shared resumable model downloads with size and SHA256 verification."""
import concurrent.futures,hashlib,json,time,urllib.request

def fetch(url,path,size=None,digest=None):
    path.parent.mkdir(parents=True,exist_ok=True)
    if path.exists() and (not size or path.stat().st_size==size):
        if not digest or checksum(path)==digest:return
        raise RuntimeError('File esistente con hash diverso: '+str(path))
    if size and size>512*1024**2:return parallel_fetch(url,path,size,digest)
    part=path.with_suffix(path.suffix+'.part');offset=part.stat().st_size if part.exists() else 0
    headers={'User-Agent':'H3-Chat model setup'}
    if offset:headers['Range']=f'bytes={offset}-'
    with urllib.request.urlopen(urllib.request.Request(url,headers=headers),timeout=120) as response:
        if offset and response.status!=206:raise RuntimeError('Il server non supporta la ripresa del download.')
        with part.open('ab' if offset else 'wb') as out:
            last=0
            while data:=response.read(4*1024**2):
                out.write(data);offset+=len(data)
                if time.monotonic()-last>10:print(f'Download {path.name}: {offset/1024**3:.2f} GiB'+(f' / {size/1024**3:.2f}' if size else ''),flush=True);last=time.monotonic()
    if size and part.stat().st_size!=size:raise RuntimeError('Download incompleto.')
    if digest and checksum(part)!=digest:raise RuntimeError('Verifica SHA256 non riuscita.')
    part.replace(path)

def parallel_fetch(url,path,size,digest,workers=8):
    part=path.with_suffix(path.suffix+'.part');manifest=part.with_suffix('.chunks.json');chunk=32*1024**2
    saved=json.loads(manifest.read_text()) if manifest.exists() else {}
    done=set(saved.get('done',[])) if saved.get('size')==size and saved.get('url')==url and part.exists() else set()
    if not done:
        with part.open('wb') as file:file.truncate(size)
    def block(index):
        start=index*chunk;end=min(size,start+chunk)-1
        for attempt in range(3):
            try:
                request=urllib.request.Request(url+f'?download=true&part={index}',headers={'Range':f'bytes={start}-{end}','User-Agent':'H3-Chat model setup'})
                with urllib.request.urlopen(request,timeout=120) as response:
                    if response.status!=206 or response.headers.get('Content-Range')!=f'bytes {start}-{end}/{size}':raise RuntimeError('Intervallo download inatteso.')
                    with part.open('r+b') as file:
                        file.seek(start);remaining=end-start+1
                        while remaining:
                            data=response.read(min(4*1024**2,remaining))
                            if not data:raise RuntimeError('Blocco incompleto.')
                            file.write(data);remaining-=len(data)
                return index
            except Exception:
                if attempt==2:raise
    count=(size+chunk-1)//chunk;last=0
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        for future in concurrent.futures.as_completed([pool.submit(block,n) for n in range(count) if n not in done]):
            done.add(future.result());temp=manifest.with_suffix('.tmp');temp.write_text(json.dumps({'url':url,'size':size,'done':sorted(done)}));temp.replace(manifest)
            if time.monotonic()-last>10:print(f'Pesi: {len(done)}/{count} blocchi verificati in trasferimento',flush=True);last=time.monotonic()
    if checksum(part)!=digest:raise RuntimeError('Verifica SHA256 dei pesi non riuscita.')
    part.replace(path);manifest.unlink(missing_ok=True)

def checksum(path):
    digest=hashlib.sha256()
    with path.open('rb') as stream:
        while data:=stream.read(8*1024**2):digest.update(data)
    return digest.hexdigest()

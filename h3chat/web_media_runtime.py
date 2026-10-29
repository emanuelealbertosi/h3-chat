"""Small optional public-video downloader. Fixed wheels, hashes, no pip hooks."""
import hashlib,json,os,platform,shutil,subprocess,tarfile,tempfile,urllib.request,zipfile
from pathlib import Path

WHEELS=(
 ('yt_dlp','2026.10.26','https://files.pythonhosted.org/packages/7f/3d/16ea7d5638cf585991f2c5705e8083688dde633d32d0871f2404e0f4d827/yt_dlp-2026.10.26-py3-none-any.whl',3186201,'a05c5b5d8562f7e8a62f5334348b406af4930d56d3a65f8021d14af0e22339ae'),
 ('yt_dlp_ejs','0.8.0','https://files.pythonhosted.org/packages/e3/bd/520769863744b669440a924271a6159ddd82ad5ae26b4ac4d4b69e9f8d44/yt_dlp_ejs-0.8.0-py3-none-any.whl',53443,'79300e5fca7f937a1eeede11f0456862c1b41107ce1d726871e0207424f4bdb4'),
)
NODE_VERSION='24.21.0'
NODE_SOURCES={
 'windows-x64':('win-x64/node.exe','ba4e6d110e8c1592a1ecd390f6b05f3da124b13871a5be62b341a07a853c6c32'),
 'darwin-arm64':('node-v24.21.0-darwin-arm64.tar.xz','6239d4cf92d864487ec8cd3615038f7b67e7f58b77b21cd2f09ea9fbd68065fe'),
 'linux-x64':('node-v24.21.0-linux-x64.tar.xz','fd8e59d5a511510f6a298afb548f18c7d2b1be404d8b4a27d94fbe49f56cb2d6'),
}

def node(root):
    for value in (Path(root)/'runtime/tools/web-media/node.exe',Path(root)/'runtime/tools/web-media/node',shutil.which('node')):
        if value and Path(value).is_file():return str(value)
    return None

def ensure_node(root,stage=lambda _:None):
    current=node(root)
    if current:
        value=subprocess.run([current,'--version'],capture_output=True,text=True,timeout=10,check=True,creationflags=0x08000000 if os.name=='nt' else 0).stdout.strip()
        if value.startswith('v') and int(value[1:].split('.')[0])>=22:return current
    machine=platform.machine().lower();arch='arm64' if machine in ('aarch64','arm64') else 'x64' if machine in ('amd64','x86_64') else machine
    key=('windows' if os.name=='nt' else platform.system().lower())+'-'+arch
    if key not in NODE_SOURCES:raise ValueError('Runtime JavaScript automatico non disponibile per questa piattaforma. Installa Node 22+ e riprendi il compito.')
    name,digest=NODE_SOURCES[key];folder=Path(root)/'runtime/tools/web-media';folder.mkdir(parents=True,exist_ok=True);target=folder/('node.exe' if os.name=='nt' else 'node')
    if target.exists():raise ValueError('Runtime JavaScript privato non compatibile: controllalo prima di sostituirlo.')
    stage('Installazione runtime JavaScript privato verificato · Node '+NODE_VERSION)
    with tempfile.TemporaryDirectory(prefix='node-install-',dir=folder) as raw:
        temporary=Path(raw);archive=temporary/'download';hasher=hashlib.sha256();total=0
        with urllib.request.urlopen('https://nodejs.org/dist/v'+NODE_VERSION+'/'+name,timeout=45) as response,archive.open('xb') as output:
            while block:=response.read(1024**2):
                total+=len(block)
                if total>200*1024**2 or shutil.disk_usage(folder).free<512*1024**2:raise ValueError('Runtime JavaScript troppo grande o spazio insufficiente.')
                output.write(block);hasher.update(block)
        if hasher.hexdigest()!=digest:raise ValueError('Verifica SHA256 del runtime JavaScript non riuscita.')
        if name.endswith('.exe'):binary=archive
        else:
            prefix=name.removesuffix('.tar.xz');binary=temporary/'node'
            with tarfile.open(archive,'r:xz') as tar:
                member=tar.getmember(prefix+'/bin/node')
                if not member.isfile() or member.size>200*1024**2:raise ValueError('Archivio del runtime JavaScript non valido.')
                with tar.extractfile(member) as source,binary.open('xb') as output:shutil.copyfileobj(source,output)
                license=tar.getmember(prefix+'/LICENSE')
                if not license.isfile() or license.size>1024**2:raise ValueError('Licenza del runtime JavaScript non valida.')
                (folder/'NODE-LICENSE.txt').write_bytes(tar.extractfile(license).read())
            binary.chmod(0o755)
        # Exclusive publish; concurrent installation never overwrites a file.
        with binary.open('rb') as source,target.open('xb') as output:shutil.copyfileobj(source,output)
        if os.name!='nt':target.chmod(0o755)
        (folder/'node-source.json').write_text(json.dumps({'version':NODE_VERSION,'url':'https://nodejs.org/dist/v'+NODE_VERSION+'/'+name,'sha256':digest},indent=2),encoding='utf8')
    return str(target)

def ensure_ffmpeg(root,stage=lambda _:None):
    root=Path(root);private=root/'runtime/tools/web-media/ffmpeg.exe'
    for path in (root/'runtime/remix/ffmpeg.exe',private,shutil.which('ffmpeg')):
        if path and Path(path).is_file():return str(path)
    if os.name!='nt':
        from imageio_ffmpeg import get_ffmpeg_exe
        return get_ffmpeg_exe()
    # Reuse H3's pinned CPU-only media bundle, never an arbitrary installer or
    # the audio/vision model runtimes. It contains a standalone FFmpeg binary.
    from .downloads import download,extract_members
    import threading
    name='H3-Chat-remix_media-0.18.47-windows-x64.zip';archive=root/'runtime/archives'/name
    stage('Installazione componente media CPU verificato · FFmpeg')
    download('https://github.com/emanuelealbertosi/h3-chat/releases/download/v0.18.47/'+name,archive,
             '44b40a772103df01e18b25d22a37b37cc8b47008ec8d0076a99f36ed59663303',60708189,threading.Event(),
             lambda received,total:stage('Componente media CPU · '+str(round(received/1024**2,1))+' / '+str(round(total/1024**2,1))+' MiB'))
    with zipfile.ZipFile(archive) as bundle:
        members={'ffmpeg.exe':'ffmpeg.exe'}
        for member in bundle.namelist():
            if '/' not in member and member.startswith('remix-') and member.endswith(('.txt','.md')):members[member]=member
    extract_members(archive,private.parent,members)
    return str(private)

def status(root):
    folder=Path(root)/'runtime/tools/web-media'
    try:manifest=json.loads((folder/'ready.json').read_text(encoding='utf8'))
    except (OSError,ValueError):manifest={}
    return {'installed':manifest.get('wheels')==[{'name':n,'version':v,'sha256':h} for n,v,_,_,h in WHEELS] and all((folder/n/'__init__.py').is_file() for n,*_ in WHEELS),
        'javascript_runtime':bool(node(root)),'versions':{n:v for n,v,*_ in WHEELS}}

def ensure(root,stage=lambda _:None):
    folder=Path(root)/'runtime/tools/web-media'
    if status(root)['installed']:return folder
    folder.parent.mkdir(parents=True,exist_ok=True)
    lock=folder.with_suffix('.installing')
    try:descriptor=os.open(lock,os.O_CREAT|os.O_EXCL|os.O_WRONLY)
    except FileExistsError:raise ValueError('Installazione del downloader già in corso; attendi il completamento.') from None
    os.close(descriptor)
    try:
        with tempfile.TemporaryDirectory(prefix='web-media-',dir=folder.parent) as raw:
            temporary=Path(raw);packages=temporary/'packages';packages.mkdir()
            for name,version,url,size,digest in WHEELS:
                stage('Installazione downloader video verificato · '+name+' '+version)
                wheel=temporary/(name+'.whl');hasher=hashlib.sha256();total=0
                with urllib.request.urlopen(url,timeout=30) as response,wheel.open('wb') as target:
                    while block:=response.read(1024**2):
                        total+=len(block)
                        if total>size:raise ValueError('Pacchetto downloader oltre la dimensione verificata.')
                        target.write(block);hasher.update(block)
                if total!=size or hasher.hexdigest()!=digest:raise ValueError('Verifica del pacchetto downloader non riuscita.')
                with zipfile.ZipFile(wheel) as archive:
                    for entry in archive.infolist():
                        path=Path(entry.filename)
                        if path.is_absolute() or '..' in path.parts or '\\' in entry.filename or entry.file_size>32*1024**2 or (entry.external_attr>>16)&0o170000==0o120000:raise ValueError('Pacchetto downloader non valido.')
                        if path.parts[0]==name+'-'+version+'.data':continue # CLI/manpage data is not installed into the system.
                        if path.parts[0] not in (name,name+'-'+version+'.dist-info'):raise ValueError('Contenuto del pacchetto downloader inatteso.')
                        output=packages/path
                        if entry.is_dir():output.mkdir(parents=True,exist_ok=True);continue
                        output.parent.mkdir(parents=True,exist_ok=True)
                        with archive.open(entry) as source,output.open('xb') as target:shutil.copyfileobj(source,target)
            manifest={'wheels':[{'name':n,'version':v,'sha256':h} for n,v,_,_,h in WHEELS]}
            (packages/'ready.json').write_text(json.dumps(manifest,indent=2),encoding='utf8')
            if folder.exists():raise ValueError('Cartella downloader esistente ma incompleta: controllala prima di sostituirla.')
            packages.rename(folder)
        return folder
    finally:lock.unlink(missing_ok=True)

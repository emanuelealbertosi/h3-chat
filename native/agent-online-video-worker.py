"""CPU-only original YouTube download into this action's private output folder."""
import hashlib,json,os,re,shutil,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
wire=sys.stdout;sys.stdout=sys.stderr
def emit(event,**value):wire.write(json.dumps({'event':event,**value},ensure_ascii=False)+'\n');wire.flush()

def own_tree():
    if os.name!='nt':return None
    import ctypes as C
    from ctypes import wintypes as W
    from h3chat.computer_process import dlls
    from h3chat.windows_sandbox import EXTENDED_LIMITS
    kernel,_,_=dlls();kernel.GetCurrentProcess.restype=W.HANDLE
    job=kernel.CreateJobObjectW(None,None)
    if not job:raise C.WinError(C.get_last_error())
    limits=EXTENDED_LIMITS();limits.BasicLimitInformation.LimitFlags=0x2000
    if not kernel.SetInformationJobObject(job,9,C.byref(limits),C.sizeof(limits)) or not kernel.AssignProcessToJobObject(job,kernel.GetCurrentProcess()):
        error=C.get_last_error();kernel.CloseHandle(job);raise C.WinError(error)
    return job # Non-inheritable owner handle: Stop closes it and all descendants.

def run(request):
    from h3chat.agent_online_video import youtube_url
    from h3chat.downloads import safe_join
    from h3chat.web_media_runtime import ensure,ensure_node,ensure_ffmpeg
    from h3chat.agent_browser_proxy import PublicProxy
    if not re.fullmatch('[a-f0-9]{32}',request['id']):raise ValueError('ID download video non valido.')
    url=youtube_url(request['url']);limit=request.get('max_megabytes',512);height=request.get('max_height',1080)
    if type(limit) is not int or not 1<=limit<=32768 or height not in (360,480,720,1080,1440,2160):raise ValueError('Limiti download video non validi.')
    data=Path(request['data']).resolve();folder=safe_join(data,'outputs/'+request['id']+'/online-video');folder.mkdir(parents=True,exist_ok=True)
    if any(folder.glob('video.*')):raise ValueError('Un download esiste già per questo passaggio: controllalo prima di ripetere.')
    if shutil.disk_usage(folder).free<limit*1024**2+512*1024**2:raise ValueError('Spazio insufficiente per il limite video richiesto.')
    dependencies=ensure(ROOT,lambda text:emit('stage',message=text));sys.path.insert(0,str(dependencies));sys.path.insert(0,str(ROOT/'runtime/tools/documents'))
    import yt_dlp
    runtime=ensure_node(ROOT,lambda text:emit('stage',message=text))
    ffmpeg=ensure_ffmpeg(ROOT,lambda text:emit('stage',message=text))
    samples={};reported=0;started=time.monotonic();reserve=512*1024**2
    class Logger:
        def debug(self,message):pass
        def warning(self,message):print('Downloader: '+str(message)[:800],file=sys.stderr,flush=True)
        def error(self,message):print('Downloader: '+str(message)[:1200],file=sys.stderr,flush=True)
    def progress(value):
        nonlocal reported
        filename=value.get('filename','download');samples[filename]=max(samples.get(filename,0),int(value.get('downloaded_bytes') or 0));total=sum(samples.values())
        if total>limit*1024**2 or shutil.disk_usage(folder).free<reserve:raise ValueError('Raggiunto il limite download video o lo spazio minimo libero.')
        if time.monotonic()-started>1700:raise TimeoutError('Download video oltre il tempo massimo.')
        if time.monotonic()-reported>2 or value.get('status')=='finished':
            emit('stage',message='Download YouTube · '+str(round(total/1024**2,1))+' MiB'+(' · unione audio/video su CPU' if value.get('status')=='finished' else ''));reported=time.monotonic()
    proxy=PublicProxy(maximum=limit*1024**2+64*1024**2)
    try:
        opts={'format':f'bv*[height<={height}][ext=mp4]+ba[ext=m4a]/b[height<={height}][ext=mp4]/b[height<={height}]',
            'outtmpl':str(folder/'video.%(ext)s'),'merge_output_format':'mp4','ffmpeg_location':str(ffmpeg),
            'noplaylist':True,'playlistend':1,'cachedir':False,'quiet':True,'no_warnings':False,
            'overwrites':False,'continuedl':False,'restrictfilenames':True,'max_filesize':limit*1024**2,
            'socket_timeout':20,'retries':2,'fragment_retries':2,'concurrent_fragment_downloads':1,
            'progress_hooks':[progress],'logger':Logger(),'proxy':proxy.address,
            'js_runtimes':{'node':{'path':runtime}},'remote_components':set(),'plugin_dirs':[],
            'allowed_extractors':['youtube'],'skip_unavailable_fragments':False}
        with yt_dlp.YoutubeDL(opts) as downloader:info=downloader.extract_info(url,download=True)
        if not isinstance(info,dict) or info.get('_type') in ('playlist','multi_video'):raise ValueError('Il link non ha restituito un singolo video.')
        files=[p for p in folder.glob('video.*') if p.suffix.lower() in ('.mp4','.mkv','.webm') and p.is_file() and not p.is_symlink()]
        if len(files)!=1:raise ValueError('Download o unione audio/video incompleti. Controlla il registro; nessun rilancio automatico.')
        file=files[0];size=file.stat().st_size
        if not 0<size<=limit*1024**2:raise ValueError('Il file finale supera il limite oppure è vuoto.')
        with file.open('rb') as stream:digest=hashlib.file_digest(stream,'sha256').hexdigest()
        import av
        with av.open(str(file),options={'protocol_whitelist':'file'}) as container:
            videos=list(container.streams.video);audios=list(container.streams.audio)
            if not videos:raise ValueError('Il file scaricato non contiene un flusso video.')
            duration=float(container.duration/av.time_base) if container.duration else float(info.get('duration') or 0)
            width=videos[0].width;height=videos[0].height
        return {'path':file.relative_to(data).as_posix(),'bytes':size,'sha256':digest,'title':str(info.get('title') or 'Video YouTube')[:150],
            'source_url':url,'duration':duration,'width':width,'height':height,'audio':bool(audios),'cpu_only':True}
    finally:proxy.close()

if __name__=='__main__':
    owner=own_tree();emit('hello',engine='public-online-video-cpu')
    try:emit('result',result=run(json.loads(sys.stdin.readline())))
    except Exception as exc:emit('error',message=str(exc))

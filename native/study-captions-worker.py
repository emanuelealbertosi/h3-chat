"""Bounded public YouTube captions only; no cookies, login or video download."""
import json,re,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
wire=sys.stdout;sys.stdout=sys.stderr
def emit(event,**value):wire.write(json.dumps({'event':event,**value},ensure_ascii=False)+'\n');wire.flush()

def own_tree():
    import os
    if os.name!='nt':return None
    import ctypes as C
    from ctypes import wintypes as W
    from h3chat.computer_process import dlls
    from h3chat.windows_sandbox import EXTENDED_LIMITS
    kernel,_,_=dlls();kernel.GetCurrentProcess.restype=W.HANDLE;job=kernel.CreateJobObjectW(None,None)
    if not job:raise C.WinError(C.get_last_error())
    limits=EXTENDED_LIMITS();limits.BasicLimitInformation.LimitFlags=0x2000
    if not kernel.SetInformationJobObject(job,9,C.byref(limits),C.sizeof(limits)) or not kernel.AssignProcessToJobObject(job,kernel.GetCurrentProcess()):
        error=C.get_last_error();kernel.CloseHandle(job);raise C.WinError(error)
    return job

def run(request):
    from h3chat.agent_online_video import youtube_url
    from h3chat.web_media_runtime import ensure,ensure_node
    from h3chat.agent_browser_proxy import PublicProxy
    url=youtube_url(request['url']);folder=Path(request['data']).resolve()/'outputs'/request['id']/'captions'
    if not re.fullmatch('[0-9a-f]{32}',request['id']):raise ValueError('ID lavoro non valido.')
    folder.mkdir(parents=True,exist_ok=True)
    packages=ensure(ROOT,lambda s:emit('progress',message=s));sys.path.insert(0,str(packages));runtime=ensure_node(ROOT,lambda s:emit('progress',message=s))
    import yt_dlp
    proxy=PublicProxy(maximum=32*1024**2)
    try:
        opts={'skip_download':True,'writesubtitles':True,'writeautomaticsub':True,'subtitleslangs':['it','en'],'subtitlesformat':'json3',
              'outtmpl':str(folder/'captions.%(ext)s'),'noplaylist':True,'playlistend':1,'cachedir':False,'quiet':True,
              'socket_timeout':15,'retries':1,'proxy':proxy.address,'js_runtimes':{'node':{'path':runtime}},'remote_components':set(),'plugin_dirs':[],
              'allowed_extractors':['youtube']}
        with yt_dlp.YoutubeDL(opts) as downloader:info=downloader.extract_info(url,download=True)
        rows=[];language=''
        for lang in ('it','en'):
            file=folder/f'captions.{lang}.json3'
            if not file.is_file():continue
            if file.stat().st_size>8*1024**2:raise ValueError('Sottotitoli oltre il limite di 8 MB.')
            data=json.loads(file.read_text(encoding='utf8'));last=''
            for event in data.get('events',[]):
                value=''.join(s.get('utf8','') for s in event.get('segs',[])).strip()
                if value and value!=last:rows.append(f"[{event.get('tStartMs',0)/1000:.1f} s] {value}");last=value
            if rows:language=lang;break
        if not rows:raise ValueError('Sottotitoli italiani o inglesi non disponibili. Puoi trascrivere un audio allegato con Whisper; nessun video è stato scaricato.')
        result='\n'.join(rows)
        if len(result)>1000000:raise ValueError('Trascrizione oltre il limite testuale.')
        return {'title':str(info.get('title') or 'YouTube')[:150],'language':language,'text':result}
    finally:proxy.close()

if __name__=='__main__':
    owner=own_tree();emit('hello',engine='study-captions-cpu')
    try:emit('result',result=run(json.loads(sys.stdin.readline())))
    except Exception as exc:emit('error',message=str(exc))

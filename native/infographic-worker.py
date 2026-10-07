"""Deterministic Edge frame capture and portable PyAV audio/video composition."""
import base64,hashlib,io,json,math,os,socket,struct,subprocess,sys,time,urllib.request
from fractions import Fraction
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'runtime/tools/documents')]
handle=os.add_dll_directory(str(ROOT/'runtime/tools/documents')) if os.name=='nt' else None
wire=sys.stdout;sys.stdout=sys.stderr
def emit(event,**kw):wire.write(json.dumps({'event':event,**kw})+'\n');wire.flush()

def own_process_tree():
    # The non-inheritable handle belongs only to this worker. Windows closes it
    # on exit or Stop, killing the private renderer and all its descendants.
    if os.name!='nt':return None
    import ctypes as C
    from ctypes import wintypes as W
    from h3chat.windows_sandbox import EXTENDED_LIMITS
    kernel=C.WinDLL('kernel32',use_last_error=True)
    kernel.CreateJobObjectW.argtypes=[C.c_void_p,W.LPCWSTR];kernel.CreateJobObjectW.restype=W.HANDLE
    kernel.SetInformationJobObject.argtypes=[W.HANDLE,C.c_int,C.c_void_p,W.DWORD];kernel.SetInformationJobObject.restype=W.BOOL
    kernel.GetCurrentProcess.restype=W.HANDLE
    kernel.AssignProcessToJobObject.argtypes=[W.HANDLE,W.HANDLE];kernel.AssignProcessToJobObject.restype=W.BOOL
    kernel.CloseHandle.argtypes=[W.HANDLE]
    job=kernel.CreateJobObjectW(None,None)
    if not job:raise C.WinError(C.get_last_error())
    limits=EXTENDED_LIMITS();limits.BasicLimitInformation.LimitFlags=0x2000
    if not kernel.SetInformationJobObject(job,9,C.byref(limits),C.sizeof(limits)) or not kernel.AssignProcessToJobObject(job,kernel.GetCurrentProcess()):
        error=C.get_last_error();kernel.CloseHandle(job);raise C.WinError(error)
    return job

class CDP:
    def __init__(self,url):
        from urllib.parse import urlsplit
        part=urlsplit(url);self.sock=socket.create_connection(('127.0.0.1',part.port),timeout=30);self.buf=b'';self.seq=0
        key=base64.b64encode(os.urandom(16)).decode();self.sock.sendall(('GET '+part.path+' HTTP/1.1\r\nHost: localhost\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Key: '+key+'\r\nSec-WebSocket-Version: 13\r\n\r\n').encode())
        while b'\r\n\r\n' not in self.buf:self.buf+=self.sock.recv(4096)
        header,self.buf=self.buf.split(b'\r\n\r\n',1)
        if not header.startswith(b'HTTP/1.1 101'):raise RuntimeError('Collegamento al renderer non riuscito.')
    def read(self,n):
        while len(self.buf)<n:
            data=self.sock.recv(max(4096,n-len(self.buf)))
            if not data:raise RuntimeError('Il renderer si è chiuso.')
            self.buf+=data
        value,self.buf=self.buf[:n],self.buf[n:];return value
    def send(self,body,opcode=1):
        payload=body if isinstance(body,bytes) else body.encode();n=len(payload);mask=os.urandom(4)
        header=bytes([128|opcode,128|(n if n<126 else 126 if n<65536 else 127)])+(b'' if n<126 else struct.pack('!H',n) if n<65536 else struct.pack('!Q',n))
        self.sock.sendall(header+mask+bytes(v^mask[i%4] for i,v in enumerate(payload)))
    def message(self):
        parts=[]
        while True:
            a,b=self.read(2);length=b&127
            if length==126:length=struct.unpack('!H',self.read(2))[0]
            elif length==127:length=struct.unpack('!Q',self.read(8))[0]
            if length>64*1024**2:raise ValueError('Frame renderer troppo grande.')
            mask=self.read(4) if b&128 else None;body=self.read(length)
            if mask:body=bytes(v^mask[i%4] for i,v in enumerate(body))
            if a&15==9:self.send(body,10);continue
            if a&15==8:raise RuntimeError('Renderer disconnesso.')
            parts.append(body)
            if a&128:return json.loads(b''.join(parts))
    def call(self,method,params=None):
        self.seq+=1;ident=self.seq;self.send(json.dumps({'id':ident,'method':method,'params':params or {}}))
        while True:
            value=self.message()
            if value.get('id')==ident:
                if value.get('error'):raise RuntimeError('Renderer: '+str(value['error']))
                return value.get('result',{})
    def evaluate(self,expression,await_promise=False):
        result=self.call('Runtime.evaluate',{'expression':expression,'returnByValue':True,'awaitPromise':await_promise})
        if result.get('exceptionDetails'):raise RuntimeError('Errore nella timeline del renderer.')
        return result.get('result',{}).get('value')

def audio(path,duration,rate,loop=None):
    import av,numpy as np
    result=np.zeros((2,math.ceil(duration*rate)),dtype=np.float32)
    if not path:return result
    cursor=0
    with av.open(str(path),options={'protocol_whitelist':'file'}) as inp:
        if not inp.streams.audio:return result
        resample=av.AudioResampler(format='fltp',layout='stereo',rate=rate)
        for frame in inp.decode(audio=0):
            for part in resample.resample(frame):
                data=part.to_ndarray();n=min(data.shape[1],result.shape[1]-cursor)
                if n>0:result[:,cursor:cursor+n]=data[:,:n];cursor+=n
            if cursor>=result.shape[1]:break
        else:
            for part in resample.resample(None):
                data=part.to_ndarray();n=min(data.shape[1],result.shape[1]-cursor)
                if n>0:result[:,cursor:cursor+n]=data[:,:n];cursor+=n
    if loop and cursor and cursor<result.shape[1]:
        cursor=max(1,min(cursor,round(loop*rate)))
        for start in range(cursor,result.shape[1],cursor):
            n=min(cursor,result.shape[1]-start);result[:,start:start+n]=result[:,:n]
    return result

def mix(request,cdp):
    import numpy as np
    motion=request['deck']['infographic'];duration=sum(motion['durations']);rate=48000
    voice=audio(request.get('voice'),duration,rate);music=audio(request.get('music'),duration,rate)
    # Envelope ducking based on measured speech energy, with smooth release.
    envelope=np.zeros(voice.shape[1],dtype=np.float32);size=2400;level=0
    for start in range(0,len(envelope),size):
        energy=float(np.sqrt(np.mean(voice[:,start:start+size]**2)));target=1 if energy>.008 else 0;level=target if target>level else level*.87;envelope[start:start+size]=level
    background=music*(.2-.13*envelope)[None,:]
    if request.get('music'):
        fade=min(rate, background.shape[1]//3);background[:,:fade]*=np.linspace(0,1,fade);background[:,-fade:]*=np.linspace(1,0,fade)
    sound=voice+background
    video=motion.get('video')
    if video and video['sound']!='mute' and video['audio']:
        from h3chat.infographic_video import asset
        original=audio(asset(request['data'],request['media'],video['asset_id'],'video/mp4'),duration,rate,video['duration'] if video['end']=='loop' else None)
        # Speech remains foreground when ducking is selected. Freeze has silence
        # after the source clip ends; it never stretches the source audio.
        sound+=original*((1-.8*envelope)[None,:] if video['sound']=='duck' else 1)
    if motion['sfx']!='none':
        cues=cdp.evaluate("[...document.querySelectorAll('[data-h3-scene]')].map(f=>[...f.contentDocument.querySelectorAll('[data-motion]')].slice(0,8).map(e=>({start:Number(e.dataset.start)||0,effect:e.dataset.motion})))")
        rng=np.random.default_rng(2718);offset=0
        for i,scene in enumerate(cues):
            events=[{'start':0,'effect':'slide'},*scene]
            last=-1
            for cue in sorted(events,key=lambda c:c['start']):
                if cue['start']<0 or cue['start']>=motion['durations'][i] or cue['start']-last<.22:continue
                last=cue['start'];start=round((offset+cue['start'])*rate);length=min(round(rate*.16),sound.shape[1]-start)
                if length<=0:continue
                t=np.arange(length)/rate;window=np.sin(np.linspace(0,np.pi,length))**2
                effect=(rng.standard_normal(length)*.15 if cue['effect'] in ('slide','pan','blur','wipe') else np.sin(2*np.pi*(720*t+850*t*t))) * window
                sound[:,start:start+length]+=effect*(.035 if motion['sfx']=='subtle' else .08)
            offset+=motion['durations'][i]
    peak=float(np.max(np.abs(sound)))
    if peak>.95:sound*=.95/peak
    return np.ascontiguousarray(sound),rate

def run(request):
    import av
    from PIL import Image
    from h3chat.infographic_document import document
    from h3chat.infographics import validate_motion
    from h3chat.slides import FORMATS
    from h3chat.engine import CREATE_NO_WINDOW
    deck=request['deck'];validate_motion(deck);width,height=FORMATS[deck['format']];height=round(height);duration=sum(deck['infographic']['durations']);fps=30
    size={'9:16':(1080,1920),'16:9':(1920,1080),'1:1':(1080,1080),'4:3':(1440,1080),'16:10':(1728,1080)}[deck['format']]
    if 'test_size' in request:size=tuple(request['test_size']);fps=10
    folder=Path(request['output']).parent;folder.mkdir(parents=True,exist_ok=True);source=folder/'infographic-render.html';source.write_text(document(ROOT,request['data'],deck,request['media']),encoding='utf-8')
    profile=folder/'renderer-profile';profile.mkdir(exist_ok=True)
    (profile/'DevToolsActivePort').unlink(missing_ok=True)
    edge=next((p for p in [Path(os.environ.get('PROGRAMFILES(X86)','C:/Program Files (x86)'))/'Microsoft/Edge/Application/msedge.exe',Path(os.environ.get('PROGRAMFILES','C:/Program Files'))/'Microsoft/Edge/Application/msedge.exe'] if p.is_file()),None)
    if not edge:raise ValueError('Per il rendering infografica serve Microsoft Edge.')
    browser=subprocess.Popen([str(edge),'--headless','--disable-gpu','--no-first-run','--no-default-browser-check','--remote-debugging-address=127.0.0.1','--remote-debugging-port=0','--user-data-dir='+str(profile),'--disable-background-networking','--disable-component-update','about:blank'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=CREATE_NO_WINDOW)
    cdp=None;decoder=None;partial=folder/'infografica.partial.mp4'
    try:
        deadline=time.monotonic()+40
        portfile=profile/'DevToolsActivePort'
        while not portfile.is_file():
            if time.monotonic()>deadline:raise RuntimeError('Il renderer non si è avviato.')
            time.sleep(.1)
        port=int(portfile.read_text().splitlines()[0])
        with urllib.request.urlopen('http://127.0.0.1:'+str(port)+'/json/list',timeout=10) as r:tabs=json.load(r)
        cdp=CDP(next(t['webSocketDebuggerUrl'] for t in tabs if t['type']=='page'))
        cdp.call('Page.enable');cdp.call('Emulation.setDeviceMetricsOverride',{'width':width,'height':height,'deviceScaleFactor':1,'mobile':False})
        cdp.call('Page.navigate',{'url':source.as_uri()})
        while cdp.evaluate("document.readyState==='complete' && document.querySelectorAll('[data-h3-scene]').length==="+str(len(deck['pages']))) is not True:
            if time.monotonic()>deadline:raise RuntimeError('Caricamento scene non riuscito.')
            time.sleep(.1)
        cdp.evaluate("Promise.all([...document.querySelectorAll('iframe')].map(async f=>{await f.contentDocument.fonts.ready;await Promise.all([...f.contentDocument.images].map(i=>i.decode().catch(()=>{})));}))",True)
        cdp.evaluate((ROOT/'static/vendor/infographic-renderer.js').read_text(encoding='utf-8'))
        cdp.evaluate('document.querySelectorAll("iframe").forEach(f=>H3Infographic.prepare(f.contentDocument,'+str(height)+'))')
        cdp.evaluate("Promise.all([...document.querySelectorAll('iframe')].map(f=>f.contentDocument.fonts.ready))",True)
        cdp.evaluate('globalThis.motion='+json.dumps(deck['infographic']))
        samples,rate=mix(request,cdp)
        source_video=deck['infographic'].get('video')
        if source_video:
            from h3chat.infographic_video import Frames,asset
            decoder=Frames(asset(request['data'],request['media'],source_video['asset_id'],'video/mp4'),source_video)
        count=math.ceil(duration*fps)
        with av.open(str(partial),'w',format='mp4',options={'movflags':'+faststart'}) as out:
            video=out.add_stream('libx264',rate=fps);video.width,video.height=size;video.pix_fmt='yuv420p';video.options={'crf':'20','preset':'fast'}
            audio_stream=out.add_stream('aac',rate=rate);audio_stream.layout='stereo';audio_stream.bit_rate=192000;audio_cursor=0
            for index in range(count):
                cdp.evaluate(f'H3Motion.render(document,motion,{index/fps})')
                if decoder:
                    buffer=io.BytesIO();decoder.image(index/fps).save(buffer,'JPEG',quality=90)
                    uri='data:image/jpeg;base64,'+base64.b64encode(buffer.getvalue()).decode()
                    cdp.evaluate('Promise.all([...document.querySelectorAll("iframe")].map(async f=>{const i=f.contentDocument.querySelector("[data-h3-video]");i.src='+json.dumps(uri)+';await i.decode();}))',True)
                shot=cdp.call('Page.captureScreenshot',{'format':'png','captureBeyondViewport':False,'fromSurface':True})['data']
                with Image.open(io.BytesIO(base64.b64decode(shot))) as image:frame=av.VideoFrame.from_image(image.convert('RGB').resize(size,Image.Resampling.LANCZOS))
                frame.pts=index;frame.time_base=Fraction(1,fps)
                for packet in video.encode(frame):out.mux(packet)
                limit=min(samples.shape[1],math.ceil((index+1)*rate/fps))
                while audio_cursor+1024<=limit:
                    part=av.AudioFrame.from_ndarray(samples[:,audio_cursor:audio_cursor+1024],format='fltp',layout='stereo');part.sample_rate=rate;part.pts=audio_cursor;part.time_base=Fraction(1,rate);audio_cursor+=1024
                    for packet in audio_stream.encode(part):out.mux(packet)
                if index%30==0:emit('stage',message=f'Infografica · rendering {round(index/count*100)}% · {index}/{count} fotogrammi')
            if audio_cursor<samples.shape[1]:
                part=av.AudioFrame.from_ndarray(samples[:,audio_cursor:],format='fltp',layout='stereo');part.sample_rate=rate;part.pts=audio_cursor;part.time_base=Fraction(1,rate)
                for packet in audio_stream.encode(part):out.mux(packet)
            for packet in video.encode(None):out.mux(packet)
            for packet in audio_stream.encode(None):out.mux(packet)
        partial.replace(request['output']);return {'duration':count/fps,'width':size[0],'height':size[1]}
    finally:
        if decoder:decoder.close()
        if cdp:
            try:cdp.call('Browser.close')
            except (OSError,RuntimeError):pass
            cdp.sock.close()
        try:browser.wait(timeout=10)
        except subprocess.TimeoutExpired:browser.kill();browser.wait()
        partial.unlink(missing_ok=True)

if __name__=='__main__':
    emit('hello')
    try:
        renderer_job=own_process_tree()
        emit('result',result=run(json.loads(sys.stdin.readline())))
    except Exception as exc:
        import traceback
        traceback.print_exc();emit('error',message=str(exc))

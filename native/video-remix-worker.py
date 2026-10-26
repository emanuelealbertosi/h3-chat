"""Private FFmpeg/audio.cpp processes; no calls into other H3 applications."""
import json,os,subprocess,sys,time,traceback,wave
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'native'),str(ROOT/'runtime/tools/documents')]
wire=sys.stdout;sys.stdout=sys.stderr
def emit(event,**kw):wire.write(json.dumps({'event':event,**kw})+'\n');wire.flush()

def process_tree():
    if os.name!='nt':return None
    import ctypes as C
    from ctypes import wintypes as W
    from h3chat.windows_sandbox import EXTENDED_LIMITS
    k=C.WinDLL('kernel32',use_last_error=True)
    k.CreateJobObjectW.argtypes=[C.c_void_p,W.LPCWSTR];k.CreateJobObjectW.restype=W.HANDLE
    k.SetInformationJobObject.argtypes=[W.HANDLE,C.c_int,C.c_void_p,W.DWORD];k.SetInformationJobObject.restype=W.BOOL
    k.GetCurrentProcess.restype=W.HANDLE
    k.AssignProcessToJobObject.argtypes=[W.HANDLE,W.HANDLE];k.AssignProcessToJobObject.restype=W.BOOL
    k.CloseHandle.argtypes=[W.HANDLE]
    job=k.CreateJobObjectW(None,None);limits=EXTENDED_LIMITS();limits.BasicLimitInformation.LimitFlags=0x2000
    if not job or not k.SetInformationJobObject(job,9,C.byref(limits),C.sizeof(limits)) or not k.AssignProcessToJobObject(job,k.GetCurrentProcess()):
        error=C.get_last_error()
        if job:k.CloseHandle(job)
        raise C.WinError(error)
    return job

def info(path):
    import av
    with av.open(str(path),options={'protocol_whitelist':'file'}) as f:
        duration=f.duration/1000000 if f.duration else max((float(s.duration*s.time_base) for s in f.streams if s.duration),default=0)
        video=next(iter(f.streams.video),None)
        return {'duration':duration,'has_audio':bool(f.streams.audio),'width':video.width if video else 0,'height':video.height if video else 0}

def frame_image(frame,path):
    import av
    with av.open(str(path),'w',format='image2') as png:
        encoder=png.add_stream('png',rate=1);encoder.width=frame.width;encoder.height=frame.height;encoder.pix_fmt='rgb24'
        rgb=frame.reformat(format='rgb24');rgb.pts=0
        for packet in encoder.encode(rgb):png.mux(packet)
        for packet in encoder.encode():png.mux(packet)

class Context:
    def __init__(self,request):
        self.ROOT=ROOT;self.DATA=ROOT/'data';self.config=request['runtime'];self.d=Path(request['folder'])/'remix-work';self.d.mkdir(parents=True,exist_ok=True)
        self.FFMPEG=ROOT/'runtime/remix/ffmpeg.exe';self.ENGINE=ROOT/'runtime/remix'/self.config['backend']/('audiocpp_cli.exe' if os.name=='nt' else 'audiocpp_cli')
        self.original=self.d/'excerpt.wav';self.reference=None;self.music={}
    def settings(self):return {'backend':self.config['backend'],'threads':self.config['threads']}
    def separation_model(self):return Path(self.config['separation_model'])
    def voice_model(self):return Path(self.config['conversion_model'])
    def voice_sample(self,name):return self.reference
    def check_cancel(self,ident):pass # Parent Stop closes the owning Windows job and kills all descendants.
    def audio_info(self,path):return info(path)
    def write_json(self,path,value):Path(path).write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')
    def read_abc(self,path):return Path(path).read_text(encoding='utf-8')
    def run_job_process(self,job,d,args,append=True,phase=None):
        if phase:emit('stage',message=self.config.get('stage_prefix','Remix')+' · '+phase[0])
        d=Path(d);d.mkdir(parents=True,exist_ok=True)
        env=os.environ.copy();env['H3_REMIX_MODELS']=json.dumps(self.config)
        # audio.cpp looks only in the app's private runtime and its own CUDA DLLs.
        env['PATH']=str(self.ENGINE.parent)+os.pathsep+str(ROOT/'runtime/music/cuda')+os.pathsep+env.get('PATH','')
        with (d/'engine.log').open('ab') as log:
            process=subprocess.Popen(list(map(str,args)),stdin=subprocess.DEVNULL,stdout=log,stderr=log,env=env,cwd=ROOT,creationflags=0x08000000 if os.name=='nt' else 0)
            deadline=time.monotonic()+14400
            while process.poll() is None:
                if time.monotonic()>deadline:process.kill();process.wait();raise RuntimeError('Tempo massimo Remix superato.')
                time.sleep(.2)
            if process.returncode:
                with (d/'engine.log').open('rb') as stream:
                    stream.seek(0,2);stream.seek(max(0,stream.tell()-2500));detail=stream.read().decode('utf-8','replace')
                raise RuntimeError('Il motore Remix ha restituito un errore. '+detail)
    def run(self,args,label='Preparazione audio'):
        self.run_job_process({},self.d,args,phase=(label,0))
    def ff(self,args,label='Preparazione audio'):
        self.run([self.FFMPEG,'-y','-v','error','-nostdin','-protocol_whitelist','file,pipe',*args],label)
    def extract(self,path,out,start=0,duration=None,mono=False):
        args=['-i',path,'-vn','-af',f'aresample=48000,atrim=start_sample={round(start*48000)}'+(f':end_sample={round((start+duration)*48000)}' if duration is not None else '')+',asetpts=N/SR/TB',
              '-ar','48000','-ac','1' if mono else '2','-c:a','pcm_s16le',out]
        self.ff(args);return out
    def separate(self,path,folder):
        folder.mkdir(parents=True,exist_ok=True);self.ff(['-i',path,'-ar','44100','-ac','2',folder/'input.wav'])
        self.run([self.ENGINE,'--task','sep','--family','htdemucs','--model',self.separation_model(),'--backend',self.config['backend'],'--threads',self.config['threads'],'--audio',folder/'input.wav','--out-dir',folder,'--log','--metrics'],'Separazione voce e base')
        if not all((folder/(n+'.wav')).is_file() for n in ('vocals','drums','bass','other')):raise RuntimeError('Separazione audio incompleta.')
        return folder
    def mix_voice(self,job,d,converted,source,runner):
        from remix.mixing import render
        return render(self,job,d,converted,source,runner)
    def command_for(self,job,d):
        req=job['request'];files=self.music['files'];options=dict(req['options'])
        options.update(style=req['style'],cot='full',abc=req['abc'],seed=str(req['seed']),h3_artifact_dir=str(d))
        self.write_json(d/'engine-request.json',[{'id':'audio','text':req['lyrics'],'options':options}])
        args=[self.ENGINE,'--task','gen','--family','yue2','--model',Path(files['model']).parent,'--backend',self.config['backend'],'--threads',self.config['threads']]
        for key,value in {'yue2.model_gguf':files['model'],'yue2.vae_gguf':files['vae']}.items():args+=['--session-option',f'{key}={value}']
        return args+['--request-sequence',d/'engine-request.json','--out-dir',d,'--log','--metrics']

def main(r):
    if r['op']=='install_score':
        emit('stage',message='Installazione del lettore spartiti · consulta runtime/remix/install-score.log')
        subprocess.run([str(ROOT/'runtime/python/python.exe'),'-X','utf8',str(ROOT/'scripts/install-remix-score.py')],check=True,creationflags=0x08000000 if os.name=='nt' else 0)
        return {'ready':True}
    app=Context(r);op=r['op'];source=Path(r['source']);folder=Path(r['folder'])
    if op=='timeline_audio':
        import math
        spans=r['intervals']
        if not isinstance(spans,list) or not spans:raise ValueError('Intervalli audio mancanti.')
        if any(set(s)!={'start','duration'} or any(type(s[k]) not in (int,float) or not math.isfinite(s[k]) for k in s) or s['start']<0 or s['duration']<=0 for s in spans):raise ValueError('Intervalli audio non validi.')
        filters=[f'[0:a]asplit={len(spans)}'+''.join(f'[a{i}]' for i in range(len(spans)))]
        for i,s in enumerate(spans):filters.append(f'[a{i}]atrim=start={s["start"]}:duration={s["duration"]},asetpts=PTS-STARTPTS,apad,atrim=duration={s["duration"]}[b{i}]')
        filters.append(''.join(f'[b{i}]' for i in range(len(spans)))+f'concat=n={len(spans)}:v=0:a=1[out]')
        script=folder/'audio-cuts.txt';script.write_text(';\n'.join(filters),encoding='utf-8')
        app.ff(['-i',source,'-filter_complex_script',script,'-map','[out]','-ar','48000','-ac','2','-c:a','pcm_s16le',r['output']],'Taglio dei tratti audio della timeline')
        return {'duration':sum(s['duration'] for s in spans)}
    if op=='pad_import_audio':
        import math
        duration=r['duration'];current=info(source)['duration']
        if type(duration) not in (int,float) or not math.isfinite(duration) or duration<=0:raise ValueError('Durata importazione audio non valida.')
        if current+1/48000>=duration:return {'padded_seconds':0}
        if duration-current>.5:raise ValueError('L’audio importato è più corto del video di oltre mezzo secondo: importa nuovamente il video originale.')
        target=folder/'audio-padded.wav'
        app.ff(['-i',source,'-af',f'apad,atrim=end_sample={round(duration*48000)}','-ar','48000','-ac','2','-c:a','pcm_s16le',target],'Allineamento della coda audio al video')
        target.replace(source)
        return {'padded_seconds':duration-current}
    if op in ('import_clips','fit_video'):app.config['stage_prefix']=r.get('stage_prefix','Post-produzione')
    if op=='extract_guides':
        from h3chat.video_guide_frames import extract
        return extract(source,r['start'],r['frames'],r['positions'],folder,frame_image)
    if op=='import_frame':
        import av
        from uuid import uuid4
        seconds=r['seconds']
        with av.open(str(source)) as f:
            f.seek(round(seconds*1000000),backward=True)
            frame=next((x for x in f.decode(f.streams.video[0]) if x.time is None or x.time>=seconds-1/48),None)
            if frame is None:raise ValueError('Fotogramma del tratto non disponibile.')
            ident=uuid4().hex;path=folder/(ident+'.png');frame_image(frame,path)
        return {'id':ident,'path':str(path)}
    if op=='import_manifest':
        from uuid import uuid4
        import av
        segment_seconds=r.get('segment_seconds',15)
        if type(segment_seconds) is not int or segment_seconds not in (10,15):raise ValueError('Segmenti del video esterno: scegli 10 o 15 secondi.')
        stat=source.stat();fingerprint=[stat.st_size,stat.st_mtime_ns];manifest=folder/'import.json'
        if manifest.is_file():
            cached=json.loads(manifest.read_text(encoding='utf-8'))
            if cached.get('fingerprint')==fingerprint and cached.get('segment_seconds',15)==segment_seconds and cached.get('segmentation_version',1)==r.get('segmentation_version',1) and all(Path(x['path']).is_file() for x in cached['images']) and (folder/'audio.wav').is_file():return cached
        result=info(source)
        from h3chat.video_import import validate_metadata
        validate_metadata(result)
        result.update(images=[],audio_id=uuid4().hex,fingerprint=fingerprint,segment_seconds=segment_seconds,segmentation_version=r.get('segmentation_version',1))
        if r.get('segmentation_version')==2:
            from h3chat.video_import_windows import windows
            starts=[start for start,frames in windows(round(result['duration']*24),segment_seconds)]
        else:starts=range(0,round(result['duration']*24),segment_seconds*24)
        from h3chat.video_conversion_progress import write as progress,ffmpeg as convert
        progress_file=folder/'progress.json';starts=list(starts)
        progress(progress_file,'Preparazione anteprime',done=0,total=len(starts))
        with av.open(str(source)) as f:
            stream=f.streams.video[0]
            for i,t in enumerate(starts):
                f.seek(round(t/24*1000000),backward=True)
                frame=next((x for x in f.decode(stream) if x.time is None or x.time>=t/24-1/48),None)
                if frame is None:raise ValueError('Fotogramma iniziale del clip non disponibile.')
                path=folder/f'frame-{i+1:03d}.png'
                # Video import uses the bundled media library, without Vision.
                frame_image(frame,path)
                result['images'].append({'id':uuid4().hex,'path':str(path)})
                progress(progress_file,f'Preparazione anteprime · {i+1}/{len(starts)} clip',done=i+1,total=len(starts))
        if result['has_audio']:
            args=['-i',source,'-vn','-af',f'aresample=48000,apad,atrim=end_sample={round(result["duration"]*48000)},asetpts=N/SR/TB','-ar','48000','-ac','2','-c:a','pcm_s16le',folder/'audio.wav']
        else:args=['-f','lavfi','-i','anullsrc=r=48000:cl=stereo','-t',str(result['duration']),folder/'audio.wav']
        convert([app.FFMPEG,'-y','-v','error','-nostdin','-protocol_whitelist','file,pipe',*args],progress_file,result['duration'],'Preparazione audio originale')
        progress(progress_file,'Salvataggio della suddivisione')
        part=manifest.with_suffix('.tmp');part.write_text(json.dumps(result),encoding='utf-8');part.replace(manifest)
        return result
    if op=='import_clips':
        total=len(r['timeline'])
        for position,scene in enumerate(r['timeline'],1):
            path=Path(scene['output']) if scene.get('output') else folder/f'clip-{scene["index"]+1:03d}.mp4'
            if path.resolve().parent!=folder.resolve():raise ValueError('Destinazione della clip fuori dalla cartella di lavoro.')
            if path.is_file():
                try:
                    if abs(info(path)['duration']-scene['duration'])<.05:continue
                except Exception:pass # Replace an incomplete cached clip after Stop.
            part=path.with_suffix('.pending.mp4')
            label=(f'Timeline · {r["timeline_total"]} clip totali · preparazione originali {r.get("prepare_offset",0)+position}/{r.get("prepare_total",total)} · clip {scene["index"]+1}'
                   if r.get('timeline_total') else f'Preparazione clip {scene["index"]+1}'+(f' · {position}/{total} da preparare' if total>1 else ''))
            app.ff(['-ss',str(scene['start']),'-i',source,'-t',str(scene['duration']),'-an','-vf','fps=24,scale=trunc(iw/2)*2:trunc(ih/2)*2','-frames:v',str(scene['frames']),'-c:v','libx264','-preset','fast','-crf','18',part],label)
            if abs(info(part)['duration']-scene['duration'])>.05:raise RuntimeError('Preparazione del clip esterno incompleta.')
            part.replace(path)
        return {'clips':total}
    if op=='fit_video':
        output=Path(r['output'])
        app.ff(['-i',source,'-an','-vf',f'scale={r["width"]}:{r["height"]}:force_original_aspect_ratio=decrease,pad={r["width"]}:{r["height"]}:(ow-iw)/2:(oh-ih)/2,fps=24','-c:v','libx264','-preset','fast','-crf','18',output],'Adattamento del tratto al video originale')
        return {'path':str(output)}
    if op=='probe':return info(source)
    if op=='reference':
        reference=Path(r['reference']) if r.get('reference') else source
        duration=info(reference)['duration'];start=r['start'];length=r['duration']
        if not 0<=start<duration or start+length>duration+.05:raise ValueError('Il campione vocale richiesto supera la durata della sorgente.')
        ref=app.extract(reference,app.d/'reference-excerpt.wav',start,length)
        if r['separate']:ref=app.separate(ref,app.d/'reference-stems')/'vocals.wav'
        out=app.extract(ref,folder/'voice-reference.wav',mono=True)
        return {'path':str(out)}
    if op=='vocal':
        from remix import resinging,cloning
        c=r['config'];app.extract(source,app.original,c['start'],c['end']-c['start'])
        app.reference=Path(r['reference']) if r.get('reference') else app.original
        if r.get('reference'):
            length=info(app.reference)['duration']
            if c['reference_start']+c['reference_duration']>length+.05:raise ValueError('Campione vocale troppo corto per il tratto scelto.')
            app.reference=app.extract(app.reference,app.d/'selected-reference.wav',c['reference_start'],c['reference_duration'],True)
        app.music=r.get('music',{})
        req={'style':c['style'],'lyrics':c['text'],'abc':c['abc'],'options':{},'seed':831001,'clone_enabled':c['clone_voice'],'clone_voice':'reference','voice_steps':app.config['voice_steps'],'base_import_id':'excerpt',
             'mix':{'automatic':True,'compression':True,'ambience':0,'voice_db':0}}
        if c['mode']=='singing':
            opts=dict(app.music['options']);req['seed']=opts.pop('seed',831001);opts.pop('cot',None);req['options']=opts
            if req['seed']<0:req['seed']=831001
            if req['clone_enabled'] and not r.get('reference'):
                ref=app.extract(source,app.d/'original-reference.wav',c['reference_start'],c['reference_duration'])
                app.reference=app.separate(ref,app.d/'original-reference-stems')/'vocals.wav'
            result=resinging.process(app,{'id':'remix','request':req},app.d)
            app.write_json(folder/'singing-report.json',result)
            return {'path':str(app.d/'audio.wav')}
        stems=app.separate(app.original,app.d/'stems')
        if c['mode']=='instrumental':
            inputs=sum((['-i',stems/(n+'.wav')] for n in ('drums','bass','other')),[])
            app.ff(inputs+['-filter_complex','[0:a][1:a][2:a]amix=inputs=3:duration=first:normalize=0','-ar','48000','-ac','2',app.d/'audio.wav'],'Salvataggio base originale')
        else:
            converted=app.d/'converted.wav';cloning.convert_voice(app,{'id':'remix','request':req},app.d,stems/'vocals.wav',app.reference,converted)
            app.mix_voice({'request':req},app.d,converted,stems,lambda args:app.run(args,'Bilanciamento voce e base'))
        return {'path':str(app.d/'audio.wav')}
    if op!='render':raise ValueError('Operazione Remix sconosciuta.')
    c=r['config'];duration=info(source)['duration'];span=c['end']-c['start'];replacement=Path(r['replacement'])
    produced=info(replacement)['duration']-c['audio_start']
    if produced<=0:raise ValueError('La nuova traccia non contiene audio dal punto scelto.')
    if c['fit']=='pad' and produced>span+.05:raise ValueError(f'Il nuovo audio dura {produced:.2f} s; il tratto {span:.2f} s. Scegli Adatta durata oppure un tratto più lungo: non taglio le parole.')
    original=app.d/'full-original.wav'
    if info(source)['has_audio']:app.extract(source,original,duration=duration)
    else:app.ff(['-f','lavfi','-i','anullsrc=r=48000:cl=stereo','-t',str(duration),original])
    local=app.d/'new-excerpt.wav'
    tempo=''
    if c['fit']=='stretch':
        ratio=produced/span
        if not .5<=ratio<=2:raise ValueError('Adatta durata richiede un rapporto tra 0,5 e 2; scegli un tratto più adatto.')
        tempo=f',atempo={ratio:.10f}'
    loop=['-stream_loop','-1'] if c['fit']=='loop' else []
    app.ff([*loop,'-i',replacement,'-af',f'aresample=48000,atrim=start={c["audio_start"]:.8f},asetpts=N/SR/TB{tempo},volume={c["gain_db"]:.8f}dB,apad,atrim=end_sample={round(span*48000)},asetpts=N/SR/TB','-ar','48000','-ac','2','-c:a','pcm_s16le',local],'Adattamento della nuova traccia')
    if c['preserve_base']:
        excerpt=app.extract(original,app.d/'base-excerpt.wav',c['start'],span)
        stems=app.separate(excerpt,app.d/'base-stems');mixed=app.d/'base-with-voice.wav'
        inputs=['-i',local]+sum((['-i',stems/(n+'.wav')] for n in ('drums','bass','other')),[])
        app.ff(inputs+['-filter_complex','[0:a][1:a][2:a][3:a]amix=inputs=4:duration=first:normalize=0,alimiter=limit=0.95:level=false:latency=true','-ar','48000','-ac','2',mixed],'Nuova voce sulla base originale');local=mixed
    # Sample-accurate patch: untouched PCM samples outside the range are copied.
    import numpy as np
    if local!=app.d/'new-excerpt.wav':
        normalized=app.d/'patch-pcm.wav';app.extract(local,normalized,duration=span);local=normalized
    start,end=c['start'],c['end']
    first,last=round(start*48000),round(end*48000)
    edge=min(720,(last-first)//4)
    with wave.open(str(original),'rb') as old,wave.open(str(local),'rb') as fresh,wave.open(str(folder/'audio.wav'),'wb') as out:
        out.setparams((2,2,48000,0,'NONE','not compressed'));cursor=0
        while cursor<round(duration*48000):
            count=min(48000,round(duration*48000)-cursor)
            raw=old.readframes(count);values=np.frombuffer(raw,dtype='<i2').copy().reshape(-1,2)
            if len(values)<count:values=np.pad(values,((0,count-len(values)),(0,0)))
            a,b=max(cursor,first),min(cursor+count,last)
            if a<b:
                n=b-a;local_pos=np.arange(a-first,b-first)
                new=np.frombuffer(fresh.readframes(n),dtype='<i2').reshape(-1,2)
                if len(new)<n:new=np.pad(new,((0,n-len(new)),(0,0)))
                weight=np.minimum(1,np.minimum((local_pos+1)/max(1,edge),(last-first-local_pos)/max(1,edge)))[:,None]
                values[a-cursor:b-cursor]=np.clip(np.rint(values[a-cursor:b-cursor]*(1-weight)+new*weight),-32768,32767).astype('<i2')
            out.writeframes(values.astype('<i2').tobytes());cursor+=count
    part=folder/'remix.part.mp4'
    app.ff(['-i',source,'-i',folder/'audio.wav','-map','0:v:0','-map','1:a:0','-c:v','copy','-c:a','aac','-b:a','192k','-t',str(duration),'-movflags','+faststart',part],'Montaggio senza ricodificare le immagini')
    result=info(part)
    if abs(result['duration']-duration)>.1 or not result['has_audio']:raise RuntimeError('Durata del montaggio audio non valida.')
    part.replace(folder/'remix.mp4');return result

if __name__=='__main__':
    owned=process_tree();emit('hello')
    try:
        request=json.loads(sys.stdin.readline());emit('result',result=main(request))
    except Exception as exc:traceback.print_exc();emit('error',message=str(exc));sys.exit(1)

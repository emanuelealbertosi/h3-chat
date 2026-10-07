"""Deterministic, streaming audio/video composition with the private PyAV."""
import json
import math
import os
from pathlib import Path
import sys
from fractions import Fraction

ROOT=Path(__file__).resolve().parents[1]
RUNTIME=ROOT/'runtime/tools/documents'
sys.path.insert(0,str(RUNTIME))
dll=os.add_dll_directory(str(RUNTIME)) if os.name=='nt' and RUNTIME.is_dir() else None
wire=sys.stdout;sys.stdout=sys.stderr

def emit(event,**kw):wire.write(json.dumps({'event':event,**kw},ensure_ascii=False)+'\n');wire.flush()

def probe(path):
    import av
    with av.open(str(path),options={'protocol_whitelist':'file'}) as source:
        if not source.streams.audio:raise ValueError('Il file non contiene audio.')
        stream=source.streams.audio[0];samples=0;rate=stream.codec_context.sample_rate
        if not rate or not 8000<=rate<=192000:raise ValueError('Frequenza audio non supportata.')
        for frame in source.decode(stream):
            samples+=frame.samples
            if samples>rate*3600:raise ValueError('La traccia supera un’ora.')
        if not samples:raise ValueError('Traccia audio vuota.')
        return {'duration':samples/rate,'sample_rate':rate,'samples':samples}

def compose(videos,audio,output,retime=False,durations=None):
    import av
    info=probe(audio) if audio else None;clips=[]
    for path in videos:
        with av.open(path,options={'protocol_whitelist':'file'}) as source:
            if not source.streams.video:raise ValueError('Il file non contiene video.')
            s=source.streams.video[0];duration=float(s.duration*s.time_base) if s.duration else float(source.duration/av.time_base)
            if not math.isfinite(duration) or duration<=0:raise ValueError('Durata video non valida.')
            clips.append((path,duration,s.width,s.height,float(s.average_rate or 24)))
    if not clips:raise ValueError('Nessuna scena da montare.')
    if durations is not None and (not isinstance(durations,list) or len(durations)!=len(clips) or any(type(t) not in (int,float) or not math.isfinite(t) or t<=0 for t in durations)):raise ValueError('Tempi delle scene non validi.')
    total=sum(c[1] for c in clips)
    target=info['duration'] if info else sum(durations) if durations is not None else total
    scale=target/total if retime else 1
    if durations is not None:
        if not isinstance(durations,list) or len(durations)!=len(clips) or any(type(t) not in (int,float) or not math.isfinite(t) or t<=0 for t in durations):raise ValueError('Tempi delle scene non validi.')
        if abs(sum(durations)-target)>max(2/info['sample_rate'] if info else 1e-6,1e-6):raise ValueError('I tempi delle scene non coprono esattamente la narrazione.')
    if durations is None and not retime and total+1/24<target:raise ValueError('Le scene non coprono tutta la traccia audio.')
    width,height=clips[0][2:4];fps=min(60,max(5,round(clips[0][4])))
    if any(c[2:4]!=(width,height) for c in clips):raise ValueError('Le scene hanno formati diversi.')
    destination=Path(output);partial=destination.with_suffix('.partial.mp4');destination.parent.mkdir(parents=True,exist_ok=True)
    count=math.ceil(target*fps);written=0;offset=0
    try:
        with av.open(str(partial),'w',format='mp4',options={'movflags':'+faststart'}) as out:
            video=out.add_stream('libx264',rate=fps);video.width=width;video.height=height;video.pix_fmt='yuv420p';video.options={'crf':'18','preset':'fast'}
            sound=out.add_stream('aac',rate=48000) if audio else None
            if sound:sound.layout='stereo';sound.bit_rate=192000
            for index,(path,length,*_) in enumerate(clips):
                emit('stage',message=f'Montaggio · scena {index+1}/{len(clips)}')
                clip_scale=durations[index]/length if durations is not None else scale
                clip_start=offset if durations is not None else offset*scale
                previous=None
                with av.open(path,options={'protocol_whitelist':'file'}) as source:
                    s=source.streams.video[0];base=None
                    for i,frame in enumerate(source.decode(s)):
                        stamp=float(frame.pts*frame.time_base) if frame.pts is not None else i/clips[index][4]
                        if base is None:base=stamp
                        next_time=clip_start+(stamp-base)*clip_scale
                        if previous is not None:
                            while written<count and written/fps<next_time-1e-7:
                                copy=previous.reformat(format='yuv420p');copy.pts=written;copy.time_base=Fraction(1,fps)
                                for packet in video.encode(copy):out.mux(packet)
                                written+=1
                        previous=frame
                    if previous is None:raise ValueError('Una scena è vuota.')
                    until=min(target,clip_start+length*clip_scale)
                    while written<count and written/fps<until-1e-7:
                        copy=previous.reformat(format='yuv420p');copy.pts=written;copy.time_base=Fraction(1,fps)
                        for packet in video.encode(copy):out.mux(packet)
                        written+=1
                offset+=durations[index] if durations is not None else length
            for packet in video.encode(None):out.mux(packet)
            if audio:
                emit('stage',message='Montaggio · codifica della traccia originale')
                with av.open(audio,options={'protocol_whitelist':'file'}) as source:
                    resampler=av.AudioResampler(format='fltp',layout='stereo',rate=48000)
                    cursor=0
                    def write(parts):
                        nonlocal cursor
                        for part in parts:
                            part.pts=cursor;part.time_base=Fraction(1,48000);cursor+=part.samples
                            for packet in sound.encode(part):out.mux(packet)
                    for frame in source.decode(source.streams.audio[0]):
                        frame.pts=None;write(resampler.resample(frame))
                    write(resampler.resample(None))
                for packet in sound.encode(None):out.mux(packet)
        partial.replace(destination)
        return {'path':str(destination),'duration':target,'frames':written,'fps':fps,'audio_preserved':bool(audio),'retimed':retime or durations is not None,'speed_factor':1/scale,'scene_durations':durations,'synchronization':'per-scene' if durations is not None else 'global'}
    finally:partial.unlink(missing_ok=True)

if __name__=='__main__':
    emit('hello')
    try:
        request=json.loads(sys.stdin.readline())
        result=probe(request['path']) if request['op']=='probe' else compose(request['videos'],request['audio'],request['output'],request.get('retime',False),request.get('durations'))
        emit('result',result=result)
    except Exception as error:emit('error',message=str(error))

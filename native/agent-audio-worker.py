"""Bounded CPU soundtrack fit. Original audio is never modified."""
import json
import math
import os
from pathlib import Path
import sys
import wave
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'runtime/tools/documents')]
handle=os.add_dll_directory(str(ROOT/'runtime/tools/documents')) if os.name=='nt' else None
wire=sys.stdout;sys.stdout=sys.stderr
def emit(event,**kw):wire.write(json.dumps({'event':event,**kw})+'\n');wire.flush()

def fit(request):
    import av
    import numpy as np
    from h3chat.downloads import safe_join
    data=Path(request['data']).resolve();source=safe_join(data,request['source']);target=safe_join(data,request['output'])
    if not request['source'].startswith(('uploads/','outputs/')) or not request['output'].startswith('outputs/'):raise ValueError('File audio non autorizzato.')
    duration=request['duration'];loop=request.get('loop',True)
    if type(duration) not in (int,float) or not math.isfinite(duration) or not .1<=duration<=900 or type(loop) is not bool:raise ValueError('Durata audio: da 0,1 a 900 secondi.')
    rate=48000;count=round(duration*rate);audio=np.zeros((2,count),dtype=np.float32);cursor=0
    with av.open(str(source),options={'protocol_whitelist':'file'}) as stream:
        if not stream.streams.audio:raise ValueError('Il file non contiene audio.')
        resample=av.AudioResampler(format='fltp',layout='stereo',rate=rate)
        for frame in stream.decode(audio=0):
            for part in resample.resample(frame):
                values=part.to_ndarray();n=min(values.shape[1],count-cursor)
                if n>0:audio[:,cursor:cursor+n]=values[:,:n];cursor+=n
            if cursor>=count:break
        if cursor<count:
            for part in resample.resample(None):
                values=part.to_ndarray();n=min(values.shape[1],count-cursor)
                if n>0:audio[:,cursor:cursor+n]=values[:,:n];cursor+=n
    if not cursor:raise ValueError('Audio vuoto.')
    decoded=cursor;repeated=loop and cursor<count
    if repeated:
        # Short boundary ramps avoid sample discontinuities without changing pitch.
        ramp=min(round(.015*rate),max(1,decoded//10));base=audio[:,:decoded].copy()
        base[:,:ramp]*=np.linspace(0,1,ramp);base[:,-ramp:]*=np.linspace(1,0,ramp)
        for start in range(0,count,decoded):
            n=min(decoded,count-start);audio[:,start:start+n]=base[:,:n]
    fade=min(round(.3*rate),max(1,count//10));audio[:,-fade:]*=np.linspace(1,0,fade)
    target.parent.mkdir(parents=True,exist_ok=True);partial=target.with_suffix('.partial.wav')
    try:
        with wave.open(str(partial),'wb') as out:
            out.setnchannels(2);out.setsampwidth(2);out.setframerate(rate)
            for start in range(0,count,48000):
                values=np.nan_to_num(audio[:,start:start+48000],nan=0,posinf=1,neginf=-1)
                out.writeframes((np.clip(values,-1,1).T*32767).astype('<i2').tobytes())
        partial.replace(target)
    finally:partial.unlink(missing_ok=True)
    return {'duration':count/rate,'source_decoded_seconds':decoded/rate,'looped':repeated,'fade_seconds':fade/rate,'pitch_changed':False,'sample_rate':rate,'renderer':'CPU'}

if __name__=='__main__':
    emit('hello',engine='agent-audio-cpu')
    try:emit('result',result=fit(json.loads(sys.stdin.readline())))
    except Exception as error:emit('error',message=str(error))

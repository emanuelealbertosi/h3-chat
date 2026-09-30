"""CPU INT8 speech-to-text; entirely offline and released after each request."""
import json
import os
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1];RUNTIME=ROOT/'runtime/tools/asr'
sys.path.insert(0,str(RUNTIME))
dll=os.add_dll_directory(str(RUNTIME)) if os.name=='nt' and RUNTIME.is_dir() else None
os.environ.update(HF_HUB_OFFLINE='1',HF_HUB_DISABLE_TELEMETRY='1',HF_HOME=str(ROOT/'runtime/tools/cache'))
wire=sys.stdout;sys.stdout=sys.stderr
def emit(event,**kw):wire.write(json.dumps({'event':event,**kw},ensure_ascii=False)+'\n');wire.flush()

def audio(path):
    import av
    import numpy as np
    chunks=[];count=0
    with av.open(path) as container:
        if not container.streams.audio:raise ValueError('Il file non contiene audio.')
        if container.duration and container.duration/av.time_base>1801:raise ValueError('Trascrizione: massimo 30 minuti per allegato.')
        resampler=av.AudioResampler(format='flt',layout='mono',rate=16000)
        for frame in container.decode(audio=0):
            for part in resampler.resample(frame):
                arr=part.to_ndarray().reshape(-1);count+=len(arr)
                if count>1800*16000:raise ValueError('Trascrizione: massimo 30 minuti per allegato.')
                chunks.append(arr)
        for part in resampler.resample(None):
            arr=part.to_ndarray().reshape(-1);count+=len(arr)
            if count>1800*16000:raise ValueError('Trascrizione: massimo 30 minuti per allegato.')
            chunks.append(arr)
    if not count:raise ValueError('La traccia audio è vuota.')
    return np.concatenate(chunks).astype(np.float32,copy=False)

emit('hello',engine='transcription')
model=None;key=None
for line in sys.stdin:
    try:
        request=json.loads(line);opts=request['settings'];wanted=(request['model'],opts['asr_threads'])
        if key!=wanted:
            emit('stage',message='Trascrizione · caricamento Whisper CPU INT8')
            from faster_whisper import WhisperModel
            model=WhisperModel(request['model'],device='cpu',compute_type='int8',cpu_threads=opts['asr_threads'],local_files_only=True);key=wanted
        emit('stage',message='Trascrizione · lettura audio')
        signal=audio(request['path']);duration=len(signal)/16000
        segments,info=model.transcribe(signal,language=None if opts['asr_language']=='auto' else opts['asr_language'],beam_size=opts['asr_beam'],vad_filter=True,condition_on_previous_text=False)
        result=[];chars=0
        for s in segments:
            chars+=len(s.text)
            if chars>500000:raise ValueError('Trascrizione troppo lunga.')
            result.append({'start':s.start,'end':s.end,'text':s.text.strip()});emit('stage',message=f'Trascrizione audio · {min(s.end,duration):.0f}/{duration:.0f} secondi')
        data={'language':info.language,'language_probability':info.language_probability,'duration':duration,'segments':result,'text':'\n'.join(s['text'] for s in result),'model':request['model'],'device':'cpu','compute_type':'int8'}
        target=Path(request['output']);target.parent.mkdir(parents=True,exist_ok=True);part=target.with_suffix('.writing');part.write_text(json.dumps(data,ensure_ascii=False),encoding='utf-8');part.replace(target);emit('result',result={'path':str(target)})
    except Exception as e:emit('error',message=str(e))

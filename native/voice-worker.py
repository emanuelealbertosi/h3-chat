"""Portable speech worker. Process exit/cancellation releases all model memory."""
import importlib.util
import json
import os
from pathlib import Path
import sys
import wave
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'native'),str(ROOT/'runtime/voice/packages'),str(ROOT/'runtime/vision/packages')]
dll=os.add_dll_directory(str(ROOT/'runtime/vision/dlls')) if os.name=='nt' and (ROOT/'runtime/vision/dlls').is_dir() else None
wire=sys.stdout;sys.stdout=sys.stderr
def emit(event,**kw):wire.write(json.dumps({'event':event,**kw},ensure_ascii=False)+'\n');wire.flush()
def stamp(t):
    ms=round(t*1000);return f'{ms//3600000:02}:{ms//60000%60:02}:{ms//1000%60:02},{ms%1000:03}'

def run(request):
    import numpy as np
    spec=importlib.util.spec_from_file_location('h3_voice_backend',ROOT/'native/voice-backend.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    count=len(request['segments']);index=0
    def progress(**kw):emit('stage',message=f"Voice · segmento {index+1}/{count} · "+kw.get('message',f"sintesi · {kw.get('frames',0)} fotogrammi audio"))
    engine=module.Engine(request['config'],progress);rate=engine.sample_rate
    folder=Path(request['output']);partial=folder/'voce.partial.wav';cursor=0;srt=[];timeline=[]
    try:
        with wave.open(str(partial),'wb') as out:
            out.setnchannels(1);out.setsampwidth(2);out.setframerate(rate)
            for index,segment in enumerate(request['segments']):
                progress(message='sintesi vocale');wav=engine.generate(segment['spoken'],segment['voice'])
                if not len(wav) or not np.isfinite(wav).all():raise ValueError('Il modello ha prodotto audio vuoto o non valido.')
                peak=float(np.max(np.abs(wav)))
                if peak>.98:wav*=.98/peak
                start=cursor/rate;out.writeframes((wav*32767).astype('<i2').tobytes());cursor+=len(wav)
                srt.append(f'{index+1}\n{stamp(start)} --> {stamp(cursor/rate)}\n{segment["text"].strip()}')
                timeline.append({'scene_id':segment.get('scene_id'),'text':segment['text'],'start':start,'end':cursor/rate,'start_sample':round(start*rate),'end_sample':cursor})
                if index<count-1:
                    pause=round(rate*request['config']['pause_ms']/1000);out.writeframes(bytes(pause*2));cursor+=pause
        partial.replace(folder/'voce.wav');(folder/'voce.srt').write_text('\n\n'.join(srt),encoding='utf-8')
        result={'duration':cursor/rate,'sample_rate':rate,'segments':count,'timeline':timeline}
        (folder/'voce-timeline.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
        return result
    finally:partial.unlink(missing_ok=True)

if __name__=='__main__':
    emit('hello')
    try:emit('result',result=run(json.loads(sys.stdin.readline())))
    except Exception as exc:
        import traceback
        traceback.print_exc();emit('error',message=str(exc))

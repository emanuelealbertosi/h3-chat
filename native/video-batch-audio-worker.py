"""CPU-only track for a generated take, including a silent video fallback."""
import json,subprocess,sys,os,importlib.util
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
print(json.dumps({'event':'hello'}),flush=True)
try:
    spec=importlib.util.spec_from_file_location('clip_worker',ROOT/'native/video-clip-worker.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);handle=module.process_tree()
    request=json.loads(sys.stdin.readline());output=Path(request['output']);duration=request['duration']
    import av
    with av.open(request['source']) as container:has_audio=bool(container.streams.audio)
    cmd=[str(ROOT/'runtime/remix/ffmpeg.exe'),'-nostdin','-v','error','-y']
    cmd+=['-i',request['source'],'-map','0:a:0','-af','apad'] if has_audio else ['-f','lavfi','-i','anullsrc=r=48000:cl=stereo']
    cmd+=['-t',str(duration),'-ar','48000','-ac','2','-c:a','pcm_s16le','-threads','2',str(output)]
    result=subprocess.run(cmd,capture_output=True,creationflags=0x08000000 if os.name=='nt' else 0)
    if result.returncode:raise ValueError('Preparazione audio della variante non riuscita.')
    print(json.dumps({'event':'result','result':{'path':str(output),'duration':duration,'source_audio':has_audio}}),flush=True)
except Exception as exc:print(json.dumps({'event':'error','message':str(exc)}),flush=True)

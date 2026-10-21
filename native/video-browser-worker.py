"""QuickTime and other browser-incompatible videos to H.264/AAC, CPU only."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'runtime/tools/documents'),str(ROOT)]
dll=os.add_dll_directory(str(ROOT/'runtime/tools/documents')) if os.name=='nt' else None


def render(request):
    import av
    source=Path(request['source']);output=Path(request['output']);partial=output.with_suffix('.pending.mp4')
    if source.resolve()==output.resolve():raise ValueError('Il file originale deve essere conservato.')
    with av.open(str(source),options={'protocol_whitelist':'file'}) as container:
        if not container.streams.video:raise ValueError('Il file non contiene video.')
        codec=container.streams.video[0].codec_context.name;pixel_format=container.streams.video[0].pix_fmt;has_audio=bool(container.streams.audio)
        duration=container.duration/1_000_000 if container.duration else max((float(s.duration*s.time_base) for s in container.streams if s.duration),default=0)
    command=[str(ROOT/'runtime/remix/ffmpeg.exe'),'-nostdin','-hide_banner','-loglevel','error','-y','-threads','2','-protocol_whitelist','file,pipe','-i',str(source),'-map','0:v:0']
    # Lossless remux when H.264 is already browser compatible; other codecs
    # receive a preview copy. Never re-encode the generation/editing source.
    if codec=='h264' and pixel_format in ('yuv420p','yuvj420p'):command+=['-c:v','copy']
    else:command+=['-vf','scale=trunc(iw/2)*2:trunc(ih/2)*2','-c:v','libx264','-preset','veryfast','-crf','21','-pix_fmt','yuv420p','-threads','2']
    if has_audio:command+=['-map','0:a:0','-c:a','aac','-b:a','192k','-ac','2']
    command+=['-movflags','+faststart',str(partial)]
    try:
        from h3chat.video_conversion_progress import ffmpeg,write
        progress_file=output.parent/'progress.json'
        ffmpeg(command,progress_file,duration,'Conversione anteprima compatibile')
        write(progress_file,'Verifica del video convertito')
        with av.open(str(partial)) as container:
            if not container.streams.video or not next(container.decode(video=0),None):raise ValueError('Anteprima video non leggibile.')
        partial.replace(output);return {'path':str(output)}
    finally:partial.unlink(missing_ok=True)


if __name__=='__main__':
    print(json.dumps({'event':'hello'}),flush=True)
    try:
        spec=importlib.util.spec_from_file_location('clip_worker',ROOT/'native/video-clip-worker.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        handle=module.process_tree();result=render(json.loads(sys.stdin.readline()))
        print(json.dumps({'event':'result','result':result}),flush=True)
    except Exception as exc:print(json.dumps({'event':'error','message':str(exc)}),flush=True)

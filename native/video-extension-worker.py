"""CPU-only exact boundary frames and soundtrack insertion for video extensions."""
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
LIB=ROOT/'runtime/tools/documents'
sys.path[:0]=[str(ROOT),str(LIB)]
dll=os.add_dll_directory(str(LIB)) if os.name=='nt' and LIB.is_dir() else None


def frames(request):
    import av
    from h3chat.video_guide_frames import sample_frames
    source=Path(request['source']);folder=Path(request['folder']);folder.mkdir(parents=True,exist_ok=True)
    start=request['start'];count=request['frames']
    if type(count) is not int or not 1<=count<=5 or type(start) not in (int,float) or start<0:raise ValueError('Raccordo non valido.')
    with av.open(str(source),options={'protocol_whitelist':'file'}) as container:
        video=container.streams.video[0];video.codec_context.thread_count=2
        base=float((video.start_time or 0)*video.time_base)
        container.seek(max(0,int((base+start)/video.time_base)),stream=video,backward=True)
        result=[]
        for name,index,frame in sample_frames(container.decode(video),start=start,count=count,
                positions={str(i):i for i in range(count)},time_of=lambda f:float(f.pts*video.time_base)-base if f.pts is not None else None):
            path=folder/f'frame-{index:02d}.png';frame.to_image().save(path);result.append(str(path))
        if len(result)!=count:raise ValueError('Fotogrammi di raccordo mancanti.')
        return {'paths':result}


def audio(request):
    total=request['total'];cut=request['cut'];duration=request['duration'];start=request.get('audio_start',0)
    if not 0<=cut<=total or duration not in (5,10,15) or start<0:raise ValueError('Inserimento audio non valido.')
    output=Path(request['output']);output.parent.mkdir(parents=True,exist_ok=True)
    filters=[];labels=[]
    def part(index,begin,length,label):
        filters.append(f'[{index}:a:0]atrim=start={begin}:duration={length},asetpts=PTS-STARTPTS,aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo,apad,atrim=duration={length}[{label}]')
        labels.append(f'[{label}]')
    if cut:part(0,start,cut,'prefix')
    part(1,request.get('new_start',0),duration,'insert')
    if total-cut>1e-6:part(0,start+cut,total-cut,'suffix')
    filters.append(''.join(labels)+f'concat=n={len(labels)}:v=0:a=1[out]')
    cmd=[str(ROOT/'runtime/remix/ffmpeg.exe'),'-nostdin','-hide_banner','-loglevel','error','-y']
    for path in (request['original'],request['new']):cmd+=['-protocol_whitelist','file,pipe','-i',str(path)]
    cmd+=['-filter_complex',';'.join(filters),'-map','[out]','-t',str(total+duration),'-c:a','pcm_s16le','-threads','2',str(output)]
    run=subprocess.run(cmd,capture_output=True,text=True,encoding='utf-8',errors='replace',creationflags=0x08000000 if os.name=='nt' else 0)
    if run.returncode:raise ValueError('Inserimento audio non riuscito: '+run.stderr[-1500:])
    import av
    with av.open(str(output)) as container:
        stream=container.streams.audio[0];actual=float(stream.duration*stream.time_base)
    if abs(actual-total-duration)>1/24:raise ValueError('La traccia montata non copre la nuova timeline.')
    return {'duration':actual,'path':str(output)}


if __name__=='__main__':
    # The same kill-on-close process tree as the CPU clip worker.
    import importlib.util
    spec=importlib.util.spec_from_file_location('clip_worker',ROOT/'native/video-clip-worker.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    print(json.dumps({'event':'hello'}),flush=True)
    try:
        handle=module.process_tree();request=json.loads(sys.stdin.readline())
        result=frames(request) if request['op']=='frames' else audio(request) if request['op']=='audio' else None
        if result is None:raise ValueError('Operazione sconosciuta.')
        print(json.dumps({'event':'result','result':result}),flush=True)
    except Exception as exc:print(json.dumps({'event':'error','message':str(exc)}),flush=True)

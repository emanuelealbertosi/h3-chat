"""Standalone GPU restoration with bounded chunks, original timestamps and audio."""
import contextlib
from fractions import Fraction
import hashlib
import json
import math
import os
import re
from pathlib import Path
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
wire=sys.stdout
DLLS=[]

def emit(event,**value):
    wire.write(json.dumps({'event':event,**value},ensure_ascii=False)+'\n');wire.flush()

def bootstrap():
    paths=[ROOT/'runtime/upscale/packages',ROOT/'runtime/vision/packages',ROOT/'runtime/tools/documents']
    sys.path[:0]=[str(p) for p in paths]
    if os.name=='nt':
        for p in paths+[ROOT/'runtime/vision/packages/torch/lib',ROOT/'runtime/vision/dlls']:
            if p.is_dir():DLLS.append(os.add_dll_directory(str(p)))

def dimensions(width,height,target):
    if target in ('2x','4x'):scale=int(target[0])
    else:scale=int(target[:-1])/min(width,height)
    # Avoid rounding each dimension independently to a large model grid.
    w=round(width*scale/2)*2;h=round(height*scale/2)*2
    if w<=width or h<=height:raise ValueError('Scegli una risoluzione più grande del video originale.')
    if max(w,h)>7680 or w*h>33554432:raise ValueError('Il formato richiesto supera il limite di 8K.')
    return w,h

def stat(path):
    p=Path(path);s=p.stat()
    return {'path':str(p.resolve()),'size':s.st_size,'mtime':s.st_mtime_ns}

def digest(path):
    value=hashlib.sha256()
    with path.open('rb') as source:
        while block:=source.read(1024*1024):value.update(block)
    return value.hexdigest()

def publish_json(path,value):
    part=path.with_suffix('.tmp');part.write_text(json.dumps(value),encoding='utf-8');os.replace(part,path)

def rtx_processor(config,width,height):
    import torch
    from nvvfx import VideoSuperRes
    from nvvfx.effects import QualityLevel
    effect=VideoSuperRes(quality=getattr(QualityLevel,config['rtx_quality'].upper()))
    effect.output_width=width;effect.output_height=height;effect.load()
    def run(arrays,overlap):
        output=[]
        with torch.inference_mode():
            for array in arrays[overlap:]:
                tensor=torch.from_numpy(array).to(device='cuda',dtype=torch.float32).permute(2,0,1).contiguous()/255
                result=effect.run(tensor)
                restored=torch.from_dlpack(result.image).clone().permute(1,2,0).mul(255).clamp(0,255).to(torch.uint8).cpu().numpy()
                output.append(restored)
        return output
    return run,effect.close

def seed_processor(config,width,height,model,vae):
    import numpy as np
    import torch
    folder=ROOT/'runtime/upscale/seedvr2';sys.path.insert(0,str(folder))
    import inference_cli as cli
    original_log=cli.debug.log
    def report(message,*args,**kw):
        original_log(message,*args,**kw)
        match=re.search(r'(Encoding|Upscaling|Decoding) batch (\d+)/(\d+)',str(message))
        if match:
            label={'Encoding':'codifica VAE','Upscaling':'ricostruzione dettagli','Decoding':'decodifica VAE'}[match[1]]
            emit('stage',message=f'Upscale · SeedVR2 · {label} · gruppo {match[2]}/{match[3]}')
    cli.debug.log=report
    import src.core.model_configuration as model_configuration
    from src.utils.model_registry import DEFAULT_VAE
    dit_name='seedvr2_ema_3b_fp8_e4m3fn.safetensors'
    # Resolve the selected files in place, even when DiT and VAE are in different directories.
    def find(filename,base=None,*args,**kw):
        if filename==dit_name:return str(Path(model).resolve())
        if filename==DEFAULT_VAE:return str(Path(vae).resolve())
        raise ValueError('Componente SeedVR2 non selezionato: '+str(filename))
    model_configuration.find_model_file=find
    # The upstream registry can check for files before loading: never permit implicit downloads.
    import src.utils.constants as constants
    constants.find_model_file=find
    argv=sys.argv[:]
    try:
        sys.argv=['seedvr2',str(model),'--cuda_device','0','--dit_model',dit_name,'--model_dir',str(Path(model).parent),
            '--resolution',str(min(width,height)),'--max_resolution',str(max(width,height)),
            '--batch_size',str(config['seed_batch']),'--uniform_batch_size','--seed',str(config['seed']),
            '--color_correction',config['seed_color'],'--vae_encode_tiled','--vae_decode_tiled',
            '--vae_encode_tile_size',str(config['seed_tile']),'--vae_decode_tile_size',str(config['seed_tile']),
            '--vae_encode_tile_overlap','64','--vae_decode_tile_overlap','64',
            '--cache_dit','--cache_vae','--dit_offload_device','cpu','--vae_offload_device','cpu',
            '--blocks_to_swap',str(config['seed_swap']),'--attention_mode','sdpa']
        args=cli.parse_arguments()
    finally:sys.argv=argv
    cache={}
    def run(arrays,overlap):
        frames=torch.from_numpy(np.stack(arrays)).float().div_(255)
        with torch.inference_mode():result=cli._single_gpu_direct_processing(frames,args,'0',cache)
        if len(result)!=len(arrays):raise ValueError('SeedVR2 ha cambiato il numero di fotogrammi.')
        return result[overlap:].mul(255).clamp(0,255).to(torch.uint8).cpu().numpy()
    def close():cache.clear()
    return run,close

def encode_chunk(path,arrays,stamps,durations,width,height,rate,crf,sar):
    import av
    part=path.with_suffix('.partial.mp4');base=stamps[0]
    try:
        with av.open(str(part),'w',format='mp4') as out:
            stream=out.add_stream('libx264',rate=rate);stream.width=width;stream.height=height;stream.pix_fmt='yuv420p'
            stream.time_base=Fraction(1,90000);stream.codec_context.time_base=Fraction(1,90000)
            stream.sample_aspect_ratio=sar
            stream.options={'crf':str(crf),'preset':'fast','bf':'0','threads':'4'}
            lengths={round((stamp-base)*90000):duration for stamp,duration in zip(stamps,durations)}
            def mux_packet(packet):
                if packet.pts in lengths:packet.duration=round(lengths[packet.pts]/float(packet.time_base))
                out.mux(packet)
            for array,stamp in zip(arrays,stamps):
                frame=av.VideoFrame.from_ndarray(array,format='rgb24').reformat(width=width,height=height,format='yuv420p')
                frame.time_base=Fraction(1,90000);frame.pts=round((stamp-base)*90000)
                for packet in stream.encode(frame):mux_packet(packet)
            for packet in stream.encode(None):mux_packet(packet)
        os.replace(part,path)
    finally:part.unlink(missing_ok=True)

def mux(chunks,source,output,start,end,origin,audio=True,display_matrix=None):
    """Copy restored video packets; keep source audio timing, including leading silence."""
    import av
    import numpy as np
    partial=output.with_suffix('.partial.mp4')
    try:
        with av.open(str(chunks[0][0]),options={'protocol_whitelist':'file'}) as template, av.open(str(source),options={'protocol_whitelist':'file'}) as original, av.open(str(partial),'w',format='mp4',options={'movflags':'+faststart'}) as out:
            video=out.add_stream_from_template(template.streams.video[0])
            if display_matrix is not None:video.set_display_matrix(display_matrix)
            # Full AAC tracks are copied bit for bit; excerpts/other codecs are encoded as AAC.
            track=original.streams.audio[0] if original.streams.audio and audio else None
            passthrough=track is not None and start==0 and end is None and track.codec_context.name=='aac'
            sound=out.add_stream_from_template(track) if passthrough else out.add_stream('aac',rate=48000) if track else None
            if sound and not passthrough:sound.layout='stereo';sound.bit_rate=192000
            for path,offset in chunks:
                with av.open(str(path),options={'protocol_whitelist':'file'}) as item:
                    for packet in item.demux(item.streams.video[0]):
                        if packet.dts is None:continue
                        shift=round(offset/float(packet.time_base))
                        packet.pts+=shift;packet.dts+=shift;packet.stream=video;out.mux(packet)
            if passthrough:
                for packet in original.demux(track):
                    if packet.dts is None:continue
                    shift=round(origin/float(packet.time_base));packet.pts-=shift;packet.dts-=shift
                    packet.stream=sound;out.mux(packet)
            elif track:
                resampler=av.AudioResampler(format='fltp',layout='stereo',rate=48000)
                first=round((origin+start)*48000);last=round((origin+end)*48000) if end is not None else None
                fallback=0
                def write(parts):
                    nonlocal fallback
                    for frame in parts:
                        stamp=round(float(frame.pts*frame.time_base)*48000) if frame.pts is not None else fallback
                        fallback=stamp+frame.samples
                        lo=max(0,first-stamp);hi=min(frame.samples,last-stamp) if last is not None else frame.samples
                        if hi<=lo:continue
                        array=frame.to_ndarray()[:,lo:hi]
                        piece=av.AudioFrame.from_ndarray(np.ascontiguousarray(array),format='fltp',layout='stereo')
                        piece.sample_rate=48000;piece.time_base=Fraction(1,48000);piece.pts=stamp+lo-first
                        for packet in sound.encode(piece):out.mux(packet)
                for frame in original.decode(track):write(resampler.resample(frame))
                write(resampler.resample(None))
                for packet in sound.encode(None):out.mux(packet)
        os.replace(partial,output)
        return bool(track)
    finally:partial.unlink(missing_ok=True)

def upscale(request,processor_factory=None):
    import av
    source=Path(request['source']);output=Path(request['output']);cache=Path(request['cache']);config=request['config']
    if source.resolve()==output.resolve():raise ValueError('L’upscale deve creare un nuovo file.')
    output.parent.mkdir(parents=True,exist_ok=True);cache.mkdir(parents=True,exist_ok=True)
    started=time.monotonic();preview=config.get('preview',False);start=config.get('start',0) if preview else 0
    end=start+config.get('duration',10) if preview else None
    with av.open(str(source),options={'protocol_whitelist':'file'}) as reader:
        if not reader.streams.video:raise ValueError('Il file non contiene un video.')
        stream=reader.streams.video[0];rate=stream.average_rate or stream.guessed_rate or Fraction(24)
        width,height=dimensions(stream.width,stream.height,config['target'])
        if config['engine']=='rtx' and max(width/stream.width,height/stream.height)>4.01:raise ValueError('RTX VSR supporta al massimo 4×. Scegli SeedVR2 o un formato più piccolo.')
        chunk_size=min(32,config['seed_batch']*4-4) if config['engine']=='seed' else 32
        signature={'chunk_frames':chunk_size,'source':stat(source),'config':config,'width':width,'height':height}
        if config['engine']=='seed':signature.update(model=stat(request['model']),vae=stat(request['vae']))
        checkpoint=cache/'checkpoint.json'
        saved=json.loads(checkpoint.read_text(encoding='utf-8')) if checkpoint.exists() else {'signature':signature,'chunks':[]}
        if saved['signature']!=signature:raise ValueError('Il video o i parametri sono cambiati: avvia un nuovo upscale.')
        overlap=4 if config['engine']=='seed' else 0
        sar=stream.sample_aspect_ratio or Fraction(1);display_matrix=None
        tail=[];arrays=[];stamps=[];durations=[];parts=[];index=0;count=0;origin=None;final_stamp=0;final_end=0;process=None;close=lambda:None;load_seconds=0;restore_seconds=0;encode_seconds=0
        def flush():
            nonlocal arrays,stamps,durations,tail,index,count,process,close,load_seconds,restore_seconds,encode_seconds
            if not arrays:return
            index+=1;offset=stamps[0]-start;path=cache/f'chunk-{index:06d}.mp4'
            entry={'index':index,'frames':len(arrays),'offset':offset,'first':stamps[0],'last':stamps[-1],'last_end':stamps[-1]+durations[-1]}
            existing=saved['chunks'][index-1] if index<=len(saved['chunks']) else None
            if existing is not None:
                valid=existing.get('entry')==entry and path.is_file() and path.stat().st_size==existing.get('size')
                if valid:valid=digest(path)==existing.get('sha256')
                if valid:
                    with path.open('rb') as file:valid=file.read(12)[4:8]==b'ftyp'
                if not valid:raise ValueError('Un blocco salvato non è più valido: avvia una nuova elaborazione.')
                emit('stage',message=f'Upscale · recupero blocco {index}')
            else:
                emit('stage',message=f'Upscale · {"RTX VSR" if config["engine"]=="rtx" else "SeedVR2"} · {stamps[-1]-start:.1f} s')
                if process is None:
                    load_started=time.monotonic()
                    emit('stage',message='Upscale · caricamento '+('RTX VSR' if config['engine']=='rtx' else 'SeedVR2'))
                    if processor_factory:process,close=processor_factory(config,width,height)
                    else:
                        # Upstream CLI selects this allocator; choose it before importing PyTorch.
                        if config['engine']=='seed':os.environ.setdefault('PYTORCH_CUDA_ALLOC_CONF','backend:cudaMallocAsync')
                        import torch
                        if not torch.cuda.is_available():raise ValueError('L’upscale richiede una GPU NVIDIA compatibile e il runtime CUDA installato.')
                        process,close=rtx_processor(config,width,height) if config['engine']=='rtx' else seed_processor(config,width,height,request['model'],request['vae'])
                    load_seconds+=time.monotonic()-load_started
                restore_started=time.monotonic()
                restored=process(tail+arrays,len(tail))
                restore_seconds+=time.monotonic()-restore_started
                if len(restored)!=len(arrays):raise ValueError('Il motore upscale ha cambiato il numero di fotogrammi.')
                encode_started=time.monotonic()
                encode_chunk(path,restored,stamps,durations,width,height,rate,config['crf'],sar)
                encode_seconds+=time.monotonic()-encode_started
                saved['chunks'].append({'entry':entry,'size':path.stat().st_size,'sha256':digest(path)});publish_json(checkpoint,saved)
            parts.append((path,offset));count+=len(arrays)
            tail=(tail+arrays)[-overlap:] if overlap else [];arrays=[];stamps=[];durations=[]
        try:
            for i,frame in enumerate(reader.decode(stream)):
                raw=float(frame.pts*frame.time_base) if frame.pts is not None else i/float(rate)
                if origin is None:
                    audio_start=float(reader.streams.audio[0].start_time*reader.streams.audio[0].time_base) if reader.streams.audio and reader.streams.audio[0].start_time is not None else raw
                    origin=min(raw,audio_start)
                    import struct
                    try:display_matrix=list(struct.unpack('=9i',bytes(frame.side_data['DISPLAYMATRIX'])))
                    except KeyError:pass
                stamp=raw-origin
                if stamp<start-1e-7:continue
                if end is not None and stamp>=end-1e-7:break
                if stamps and stamp<=stamps[-1]:raise ValueError('Il video contiene tempi dei fotogrammi non validi.')
                length=float(frame.duration*frame.time_base) if frame.duration else 1/float(rate)
                if end is not None:length=min(length,end-stamp)
                arrays.append(frame.to_ndarray(format='rgb24'));stamps.append(stamp);durations.append(length);final_stamp=stamp;final_end=stamp+length
                if len(arrays)>=chunk_size:flush()
            flush()
        finally:close()
        if not count:raise ValueError('L’intervallo selezionato non contiene fotogrammi.')
        if len(saved['chunks'])!=index:raise ValueError('Il numero di blocchi non coincide con il video originale.')
        duration=final_end-start
    emit('stage',message='Upscale · montaggio e conservazione audio originale')
    mux_started=time.monotonic()
    sound=mux(parts,source,output,start,min(end,final_end) if end is not None else None,origin,display_matrix=display_matrix)
    return {'path':str(output),'width':width,'height':height,'frames':count,'duration':duration,'fps':float(rate),
            'audio_preserved':sound,'engine':config['engine'],'preview':preview,'elapsed':round(time.monotonic()-started,2),'load_seconds':round(load_seconds,2),
            'restore_seconds':round(restore_seconds,2),'encode_seconds':round(encode_seconds,2),'mux_seconds':round(time.monotonic()-mux_started,2)}

if __name__=='__main__':
    emit('hello')
    try:
        request=json.loads(sys.stdin.readline());bootstrap()
        with contextlib.redirect_stdout(sys.stderr):result=upscale(request)
        emit('result',result=result)
    except Exception as error:emit('error',message=str(error))

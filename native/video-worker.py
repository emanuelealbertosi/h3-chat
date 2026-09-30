# SPDX-License-Identifier: GPL-3.0-or-later
# H3-Chat standalone MiniMax H3 worker using the bundled ComfyUI inference
# library (GPL-3.0). No ComfyUI server, external custom nodes or Studio install.
import json
import logging
import math
import os
from pathlib import Path
import sys
import traceback

ROOT=Path(__file__).resolve().parents[1]
RUNTIME=ROOT/'runtime/vision'
dll_directory=os.add_dll_directory(str(RUNTIME/'dlls')) if os.name=='nt' and (RUNTIME/'dlls').is_dir() else None
sys.path[:0]=[str(RUNTIME/'packages'),str(RUNTIME/'core')]
os.environ.update(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',HF_HUB_DISABLE_TELEMETRY='1',HF_HOME=str(RUNTIME/'cache'))
wire=sys.stdout;sys.stdout=sys.stderr
logging.basicConfig(level=logging.INFO,stream=sys.stderr)

def emit(event,**values):
    wire.write(json.dumps({'event':event,**values},ensure_ascii=False)+'\n');wire.flush()

def read_audio(path,start,seconds,exact=False):
    """Decode a bounded source interval. PyAV is bundled; no external ffmpeg."""
    import av
    import numpy as np
    import torch
    chunks=[];count=0
    with av.open(path) as source:
        if not source.streams.audio:raise ValueError('L’allegato non contiene una traccia audio.')
        stream=source.streams.audio[0]
        rate=stream.codec_context.sample_rate if exact else 32000
        if not 8000<=rate<=192000:raise ValueError('Frequenza audio non supportata.')
        skip=round(start*rate);wanted=round(seconds*rate)
        resampler=av.AudioResampler(format='fltp',layout='stereo',rate=rate)
        for frame in source.decode(stream):
            for converted in resampler.resample(frame):
                data=converted.to_ndarray()
                if skip:
                    n=min(skip,data.shape[-1]);data=data[:,n:];skip-=n
                n=min(wanted-count,data.shape[-1])
                if n:chunks.append(data[:,:n].copy());count+=n
            if count>=wanted:break
        for converted in resampler.resample(None):
            data=converted.to_ndarray()
            if skip:
                n=min(skip,data.shape[-1]);data=data[:,n:];skip-=n
            n=min(wanted-count,data.shape[-1])
            if n:chunks.append(data[:,:n].copy());count+=n
        if not count:raise ValueError('La posizione richiesta è oltre la fine dell’audio.')
    waveform=np.concatenate(chunks,axis=-1)
    # Padding belongs only to the unused model grid, never fake missing input.
    if exact and count<wanted:raise ValueError(f'Audio troppo corto: servono {seconds:g} secondi dalla posizione {start:g}.')
    return {'waveform':torch.from_numpy(waveform)[None],'sample_rate':rate}

def write_video(path,pixels,audio,frames):
    import av
    import numpy as np
    from fractions import Fraction
    waveform=audio['waveform'][0].float().cpu().numpy()
    if waveform.ndim!=2:raise ValueError('Audio generato non valido.')
    if waveform.shape[0]==1:waveform=np.repeat(waveform,2,axis=0)
    rate=audio['sample_rate'];samples=round(frames/24*rate)
    if waveform.shape[-1]<samples:waveform=np.pad(waveform,((0,0),(0,samples-waveform.shape[-1])))
    with av.open(path,'w',format='mp4',options={'movflags':'+faststart'}) as output:
        video=output.add_stream('libx264',rate=24);video.width=int(pixels.shape[2]);video.height=int(pixels.shape[1]);video.pix_fmt='yuv420p';video.options={'crf':'18','preset':'fast'}
        sound=output.add_stream('aac',rate=rate);sound.layout='stereo';sound.bit_rate=192000
        audio_pos=0
        for index in range(frames):
            array=(pixels[index].clamp(0,1).cpu().numpy()*255).round().astype(np.uint8)
            frame=av.VideoFrame.from_ndarray(array,format='rgb24');frame.pts=index;frame.time_base=Fraction(1,24)
            for packet in video.encode(frame):output.mux(packet)
            until=min(samples,round((index+1)/24*rate))
            if until>audio_pos:
                frame=av.AudioFrame.from_ndarray(np.ascontiguousarray(waveform[:2,audio_pos:until]),format='fltp',layout='stereo')
                frame.sample_rate=rate;frame.pts=audio_pos;frame.time_base=Fraction(1,rate)
                for packet in sound.encode(frame):output.mux(packet)
                audio_pos=until
        for stream in (video,sound):
            for packet in stream.encode(None):output.mux(packet)

class Worker:
    def load(self,request):
        import comfy.cli_args
        args=comfy.cli_args.args
        args.cpu=False;args.highvram=not request['offload'];args.lowvram=request['offload']
        args.disable_dynamic_vram=True;args.reserve_vram=2.5;args.gpu_only=not request['offload']
        import torch
        if not torch.cuda.is_available():raise ValueError('MiniMax H3 richiede una GPU NVIDIA CUDA. Nessun passaggio automatico al calcolo CPU.')
        torch.set_num_threads(request.get('threads',4));self.torch=torch
        import comfy.sd
        import comfy.utils
        import comfy.sample
        from comfy_extras import nodes_minimax_h3
        self.comfy=comfy;self.h3=nodes_minimax_h3
        # Loading/PCIe transfers can take longer than sampling on a SATA drive.
        # Expose those transitions rather than leaving a generic sampling label.
        self.phase='Video · caricamento componenti';self.last_load=()
        original_load=comfy.model_management.load_models_gpu
        def load_gpu(models,*args,**kwargs):
            ids=tuple(id(m.model) for m in models)
            changed=ids!=self.last_load
            if changed:
                names=', '.join(type(m.model).__name__ for m in models)
                emit('stage',message='Video · caricamento / trasferimento GPU · '+names)
            result=original_load(models,*args,**kwargs)
            self.last_load=ids
            if changed:emit('stage',message=self.phase)
            return result
        comfy.model_management.load_models_gpu=load_gpu
        comfy.utils.PROGRESS_BAR_ENABLED=False
        files=request['files']
        emit('stage',message='Video · lettura diffusore MiniMax H3')
        self.model=comfy.sd.load_diffusion_model(files['diffusion'])
        if self.model is None or type(self.model.model.model_config).__name__!='MiniMaxH3':raise ValueError('Scegli un diffusore MiniMax H3 standard, compatibile FL2VA / REF2VA.')
        head=self.model.model.diffusion_model.final_layer
        if head.video_out.weight.shape[0]!=96 or head.audio_out.weight.shape[0]!=32:raise ValueError('PDD/Turbo non supportato: scegli un modello H3 standard FL2VA / REF2VA.')
        emit('stage',message='Video · lettura encoder Qwen3-VL MiniMax H3')
        # LOW_VRAM defaults text encoding to CPU in the underlying library.
        # Override placement: offload stores weights in RAM, all inference is CUDA.
        device=comfy.model_management.get_torch_device()
        self.clip=comfy.sd.load_clip([files['llm']],clip_type=comfy.sd.CLIPType.MINIMAX,
            model_options={'load_device':device,'offload_device':torch.device('cpu') if request['offload'] else device,'initial_device':torch.device('cpu')})
        emit('stage',message='Video · lettura VAE video e audio')
        self.vae=comfy.sd.VAE(sd=comfy.utils.load_torch_file(files['vae'],safe_load=True))
        self.audio_vae=comfy.sd.VAE(sd=comfy.utils.load_torch_file(files['audio_vae'],safe_load=True))
        if self.vae.latent_channels!=24 or self.audio_vae.latent_channels!=32:raise ValueError('VAE non compatibili con MiniMax H3: video 24 canali, audio 32 canali.')
        emit('ready')

    def images(self,paths):
        import numpy as np
        from PIL import Image,ImageOps
        images=[]
        for path in paths:
            with Image.open(path) as source:
                if max(source.size)>8192:raise ValueError('Immagine oltre 8192 pixel.')
                rgb=ImageOps.exif_transpose(source).convert('RGB')
                images.append(self.torch.from_numpy(np.asarray(rgb).copy().astype(np.float32)/255)[None])
        return images

    def condition(self,request):
        torch,comfy,h3=self.torch,self.comfy,self.h3
        opts=request['options'];plan=request['plan'];width,height=opts['width'],opts['height']
        latent,grid_frames=h3._empty_av_latent(width,height,opts['frames'])
        images=self.images(request['images']);items=[];blocks=[];guides=[]
        for entry in plan['images']:
            image=images[entry['index']-1]
            if entry['role']=='keyframe':
                frame=min(round(entry['seconds']*24),opts['frames']-1)
                image=h3._resize(image,width,height,'disabled' if frame==0 else 'center')
                z=self.vae.encode(image)
                guides.append({'resolved_frame_index':frame,'latent':z})
            else:
                ih,iw=image.shape[1:3];scale=min(1,math.sqrt(width*height/(iw*ih)))
                w,h=max(32,round(iw*scale/32)*32),max(32,round(ih*scale/32)*32)
                image=h3._resize(image,w,h,'disabled');z=self.vae.encode(image)
                blocks.append({'kind':'image','latent_h':h//16,'latent_w':w//16,'latent':z})
            items.append({'type':'image','data':image})
        master=None;master_z=None
        for entry in plan['audios']:
            audio=read_audio(request['audios'][entry['index']-1],entry['start'],opts['frames']/24,entry['role'] in ('lipsync','reuse'))
            z,t=h3._encode_ref_audio(self.audio_vae,audio)
            blocks.append({'kind':'audio','ref_audio_t':t,'audio_latent':z});items.append({'type':'audio'})
            if entry['role'] in ('lipsync','reuse'):master,master_z=audio,z
        tokens=self.clip.tokenize(plan['prompt'],minimax_ref_items=items) if items else self.clip.tokenize(plan['prompt'])
        positive=self.clip.encode_from_tokens_scheduled(tokens)
        import node_helpers
        values={}
        if blocks:values['minimax_refs']=blocks
        if guides:values['minimax_keyframes']=guides
        positive=node_helpers.conditioning_set_values(positive,values)
        if master is not None:
            video,template=latent['samples'].unbind()
            z=master_z[...,:template.shape[-1]]
            if z.shape[-1]<template.shape[-1]:z=torch.nn.functional.pad(z,(0,template.shape[-1]-z.shape[-1]))
            z=z.to(template)
            latent['samples']=comfy.nested_tensor.NestedTensor((video,z))
            latent['noise_mask']=comfy.nested_tensor.NestedTensor((torch.ones_like(video),torch.zeros_like(z)))
        return positive,latent,master,grid_frames

    def generate(self,request):
        torch,comfy=self.torch,self.comfy;opts=request['options']
        # Quantized parameters are rewrapped while offloading. no_grad avoids
        # inference tensors without version counters in PyTorch's .to() path.
        with torch.no_grad():
            emit('stage',message='Video · preparazione istruzioni, fotogrammi e audio')
            self.phase='Video · preparazione istruzioni, fotogrammi e audio'
            positive,latent,master,grid_frames=self.condition(request)
            negative=[[torch.zeros_like(value),info.copy()] for value,info in positive]
            model=self.h3.MiniMaxH3SigmaShift.execute(self.model,opts['shift_video'],opts['shift_audio'])[0]
            noise=comfy.sample.prepare_noise(latent['samples'],opts['seed'])
            emit('stage',message='Video · generazione MiniMax H3')
            self.phase='Video · generazione MiniMax H3'
            samples=comfy.sample.sample(model,noise,opts['steps'],opts['cfg'],opts['sampler'],opts['scheduler'],positive,negative,latent['samples'],noise_mask=latent.get('noise_mask'),disable_pbar=True,seed=opts['seed'],
                callback=lambda step,x0,x,total:emit('progress',step=step+1,steps=total))
            emit('stage',message='Video · decodifica fotogrammi sulla GPU')
            self.phase='Video · decodifica fotogrammi sulla GPU'
            pixels=self.vae.decode(samples.unbind()[0])
            if pixels.ndim==5:pixels=pixels.reshape(-1,*pixels.shape[-3:])
            if len(pixels)<opts['frames']:raise RuntimeError('Il VAE non ha decodificato tutti i fotogrammi.')
            emit('stage',message='Video · preparazione audio e salvataggio MP4')
            self.phase='Video · preparazione audio e salvataggio MP4'
            if master is None:
                from comfy_extras.nodes_audio import vae_decode_audio
                master=vae_decode_audio(self.audio_vae,{'samples':samples})
            write_video(request['output'],pixels,master,opts['frames'])
        emit('done',parameters={'fps':24,'duration':opts['frames']/24,'model_frames':grid_frames,'output_frames':opts['frames'],'engine':'minimax-h3','audio_sample_rate':master['sample_rate'],'audio_preserved':any(x['role'] in ('lipsync','reuse') for x in request['plan']['audios'])})

def main():
    emit('hello');worker=Worker()
    for line in sys.stdin:
        try:
            request=json.loads(line)
            if request['op']=='load':worker.load(request)
            elif request['op']=='generate':worker.generate(request)
            else:raise ValueError('Operazione video sconosciuta.')
        except Exception as exc:
            traceback.print_exc(file=sys.stderr);emit('error',message=str(exc));return 1
    return 0

if __name__=='__main__':raise SystemExit(main())

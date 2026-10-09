# SPDX-License-Identifier: GPL-3.0-or-later
# H3-Chat standalone MiniMax H3 worker using the bundled ComfyUI inference
# library (GPL-3.0). No ComfyUI server, external custom nodes or Studio install.
import json
import logging
import math
import os
from pathlib import Path
import sys
import time
import traceback
import faulthandler

ROOT=Path(__file__).resolve().parents[1]
RUNTIME=ROOT/'runtime/vision'
dll_directory=os.add_dll_directory(str(RUNTIME/'dlls')) if os.name=='nt' and (RUNTIME/'dlls').is_dir() else None
sys.path[:0]=[str(RUNTIME/'packages'),str(RUNTIME/'core')]
os.environ.update(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',HF_HUB_DISABLE_TELEMETRY='1',HF_HOME=str(RUNTIME/'cache'))
os.environ['TRITON_CACHE_DIR']=str(RUNTIME/'cache/triton')
# Triton's default sysconfig paths point at Python/Lib/site-packages. Our
# optional packages live in a separate app-local directory, so select its
# bundled compiler and CUDA headers explicitly instead of a system toolkit.
triton_home=RUNTIME/'packages/triton'
if (triton_home/'runtime/tcc/tcc.exe').is_file():
    os.environ['CC']=str(triton_home/'runtime/tcc/tcc.exe')
if (triton_home/'backends/nvidia/include/cuda.h').is_file():
    os.environ['CUDA_PATH']=str(triton_home/'backends/nvidia')
    os.environ['CUDA_HOME']=os.environ['CUDA_PATH']
wire=sys.stdout;sys.stdout=sys.stderr
logging.basicConfig(level=logging.INFO,stream=sys.stderr)
faulthandler.enable(file=sys.stderr)

def emit(event,**values):
    wire.write(json.dumps({'event':event,**values},ensure_ascii=False)+'\n');wire.flush()

def read_safetensors(path,torch,types):
    """Own writable CPU buffers; avoid c10 storage slicing and duplicate maps."""
    import struct
    values={}
    with open(path,'rb') as source:
        size=os.fstat(source.fileno()).st_size
        prefix=source.read(8)
        if len(prefix)!=8:raise ValueError('Header safetensors incompleto.')
        header_size=struct.unpack('<Q',prefix)[0]
        if header_size>100_000_000 or header_size+8>size:raise ValueError('Header safetensors non valido.')
        header=json.loads(source.read(header_size))
        if not isinstance(header,dict):raise ValueError('Header safetensors non valido.')
        base=8+header_size
        for name,info in header.items():
            if name=='__metadata__':continue
            if not isinstance(info,dict):raise ValueError('Tensore safetensors non valido.')
            shape=info.get('shape');offsets=info.get('data_offsets');dtype=types.get(info.get('dtype'))
            if dtype is None or not isinstance(shape,list) or any(type(d) is not int or d<0 for d in shape):raise ValueError('Tipo/forma safetensors non validi.')
            if not isinstance(offsets,list) or len(offsets)!=2 or any(type(d) is not int for d in offsets):raise ValueError('Offset safetensors non validi.')
            start,end=offsets
            if start<0 or end<start or base+end>size or math.prod(shape)*dtype.itemsize!=end-start:raise ValueError('Dimensione/offset safetensors non validi.')
            if start==end:values[name]=torch.empty(shape,dtype=dtype)
            else:
                # torch keeps the buffer owner. It is writable for CUDA host
                # registration and uses one allocation, without a second full
                # file mapping competing with model weights in system RAM.
                buffer=bytearray(end-start);source.seek(base+start)
                if source.readinto(buffer)!=len(buffer):raise ValueError('Tensore safetensors incompleto.')
                tensor=torch.frombuffer(buffer,dtype=dtype).view(shape)
                values[name]=tensor
    return values,header.get('__metadata__',{})

def chunked_attention(torch,attention,chunks):
    """Heads are independent: bound Sage's workspace without changing tokens."""
    @attention.wrap_attn
    def run(q,k,v,heads,mask=None,attn_precision=None,skip_reshape=False,skip_output_reshape=False,**kwargs):
        base=attention.attention_sage
        if chunks<=1 or not skip_reshape or mask is not None or q.shape[1]!=heads or k.shape[1]!=heads or v.shape[1]!=heads:
            return base(q,k,v,heads,mask=mask,attn_precision=attn_precision,skip_reshape=skip_reshape,skip_output_reshape=skip_output_reshape,**kwargs)
        b,_,seq,dim=q.shape
        # Store directly in the final NHD layout to avoid a second full-sized
        # allocation when the model reshapes the completed head output.
        output=torch.empty((b,seq,heads,dim),device=q.device,dtype=q.dtype).transpose(1,2)
        group=max(1,math.ceil(heads/chunks))
        for start in range(0,heads,group):
            end=min(heads,start+group)
            output[:,start:end]=base(q[:,start:end],k[:,start:end],v[:,start:end],end-start,
                mask=None,attn_precision=attn_precision,skip_reshape=True,skip_output_reshape=True,**kwargs)
        return output if skip_output_reshape else output.transpose(1,2).reshape(b,seq,heads*dim)
    return run

def read_audio(path,start,seconds,exact=False,tail_padding=False):
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
    if exact and count<wanted:
        # The final clip is rounded UP to a 24 fps boundary. Conditioning may
        # pad that sub-frame tail; final composition uses the original track.
        from h3chat.video_timeline import tail_padding_samples
        try:padding=tail_padding_samples(count,wanted,rate,tail=tail_padding)
        except ValueError:raise ValueError(f'Audio troppo corto: servono {seconds:g} secondi dalla posizione {start:g}.') from None
        waveform=np.pad(waveform,((0,0),(0,padding)))
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
    def restore_memory(self,record):
        import av
        import numpy as np
        def frame(path,first=False):
            image=None
            with av.open(path,options={'protocol_whitelist':'file'}) as source:
                for decoded in source.decode(source.streams.video[0]):
                    image=decoded
                    if first:break
            if image is None:raise ValueError('La scena salvata per la memoria visiva è vuota.')
            return self.torch.from_numpy(image.to_ndarray(format='rgb24').astype(np.float32)/255)[None]
        emit('stage',message='Video · recupero apertura e memoria visiva delle scene salvate')
        self.anchor=frame(record['opening'],True)
        self.recent=[frame(path) for path in record['recent'][-2:]]

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
        # safetensors' PyTorch reader slices UntypedStorage and can fault in
        # c10 on Windows when large files are reopened after CUDA offload.
        # Own writable CPU buffers without a duplicate file mapping, while
        # preserving BF16 and quantization metadata.
        original_reader=comfy.utils.load_torch_file
        def read_weights(path,safe_load=False,device=None,return_metadata=False):
            if str(path).lower().endswith(('.safetensors','.sft')) and (device is None or device.type=='cpu'):
                values,metadata=read_safetensors(str(path),torch,comfy.utils._TYPES)
                return (values,metadata) if return_metadata else values
            return original_reader(path,safe_load=safe_load,device=device,return_metadata=return_metadata)
        comfy.utils.load_torch_file=read_weights
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
        self.files=request['files'];self.offload=request['offload']
        # On a 16 GB GPU the encoder and diffuser cannot coexist. Do not even
        # map the large diffuser into RAM until conditioning has finished.
        # This keeps the two weight sets out of the working set together.
        self.model=None;self.clip=None;self.vae=None;self.audio_vae=None
        if not self.offload:self.load_diffuser()
        self.load_conditioners()
        emit('ready')

    def load_diffuser(self):
        comfy=self.comfy;files=self.files
        emit('stage',message='Video · lettura diffusore MiniMax H3')
        self.model=comfy.sd.load_diffusion_model(files['diffusion'])
        if self.model is None or type(self.model.model.model_config).__name__!='MiniMaxH3':raise ValueError('Scegli un diffusore MiniMax H3 standard, compatibile FL2VA / REF2VA.')
        head=self.model.model.diffusion_model.final_layer
        if head.video_out.weight.shape[0]!=96 or head.audio_out.weight.shape[0]!=32:raise ValueError('PDD/Turbo non supportato: scegli un modello H3 standard FL2VA / REF2VA.')

    def load_conditioners(self):
        comfy,torch,files=self.comfy,self.torch,self.files
        emit('stage',message='Video · lettura encoder Qwen3-VL MiniMax H3')
        # LOW_VRAM defaults text encoding to CPU in the underlying library.
        # Override placement: offload stores weights in RAM, all inference is CUDA.
        device=comfy.model_management.get_torch_device()
        self.clip=comfy.sd.load_clip([files['llm']],clip_type=comfy.sd.CLIPType.MINIMAX,
            model_options={'load_device':device,'offload_device':torch.device('cpu') if self.offload else device,'initial_device':torch.device('cpu')})
        emit('stage',message='Video · lettura VAE video e audio')
        self.vae=comfy.sd.VAE(sd=comfy.utils.load_torch_file(files['vae'],safe_load=True))
        self.audio_vae=comfy.sd.VAE(sd=comfy.utils.load_torch_file(files['audio_vae'],safe_load=True))
        if self.vae.latent_channels!=24 or self.audio_vae.latent_channels!=32:raise ValueError('VAE non compatibili con MiniMax H3: video 24 canali, audio 32 canali.')

    def configure_attention(self, preference, chunks=0, veda_options=None):
        from comfy.ldm.modules import attention
        if getattr(self,'veda_base_model',None) is not None:
            self.model=self.veda_base_model
            from h3chat.veda import release
            release(getattr(self,'veda_patch',None))
        self.veda_base_model=None;self.veda_patch=None
        available=attention.SAGE_ATTENTION_IS_AVAILABLE
        if preference=='sage' and not available:
            raise ValueError('SageAttention non installato. Installa l’acceleratore dal Setup video, oppure scegli Auto / PyTorch.')
        backend='sage' if preference!='pytorch' and available else 'pytorch'
        if not chunks:
            gb=self.torch.cuda.get_device_properties(0).total_memory/1024**3
            chunks=8 if gb<=20 else 4 if gb<=32 else 1
        self.attention_chunks=chunks if backend=='sage' or preference=='veda' else 1
        # VEDA owns head grouping for sparse AND declined dense calls. Passing
        # already grouped Sage would split those calls twice and slow fallback.
        function=(attention.attention_sage if preference=='veda' else chunked_attention(self.torch,attention,chunks)) if backend=='sage' else attention.attention_pytorch
        self.model.set_model_optimized_attention(function)
        if preference=='veda':
            from h3chat.veda import attach
            emit('stage',message='Video · VEDA · caricamento predictor e verifica kernel')
            self.veda_base_model=self.model
            self.model,self.veda_patch=attach(ROOT,self.model,veda_options or {},chunks,emit)
            backend='veda'
        logging.info('Video attention backend: %s (requested: %s, head chunks: %d)',backend,preference,self.attention_chunks)
        emit('stage',message='Video · attenzione '+{'sage':'SageAttention','pytorch':'PyTorch','veda':'VEDA · sparsità opzionale'}[backend])
        return backend

    def discard(self, *names):
        # Finished stages do not need their weights. Deleting them avoids the
        # quantized encoder's unsafe CUDA->CPU .to() path in torch/c10 on Windows.
        # Comfy's loaded-model list has weak references, not ownership.
        import gc
        for name in names:setattr(self,name,None)
        gc.collect()
        self.comfy.model_management.cleanup_models()
        self.comfy.model_management.soft_empty_cache(force=True)

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

    def fit_frame(self,image,opts):
        """Contain the complete guide, then pad to the latent grid, never stretch."""
        width,height=opts['output_width'],opts['output_height']
        ih,iw=image.shape[1:3];scale=min(width/iw,height/ih)
        w,h=max(1,round(iw*scale)),max(1,round(ih*scale))
        image=self.h3._resize(image,w,h,'disabled')
        left=(opts['width']-w)//2;top=(opts['height']-h)//2
        return self.torch.nn.functional.pad(image,(0,0,left,opts['width']-w-left,top,opts['height']-h-top))

    def condition(self,request,images=None):
        torch,comfy,h3=self.torch,self.comfy,self.h3
        opts=request['options'];plan=request['plan'];width,height=opts['width'],opts['height']
        latent,grid_frames=h3._empty_av_latent(width,height,opts['frames'])
        if images is None:images=self.images(request['images'])
        items=[];blocks=[];guides=[]
        for entry in plan['images']:
            image=images[entry['index']-1]
            if entry['role']=='keyframe':
                frame=min(round(entry['seconds']*24),opts['frames']-1)
                image=self.fit_frame(image,opts)
                z=self.vae.encode(image)
                guides.append({'resolved_frame_index':frame,'latent':z})
            else:
                ih,iw=image.shape[1:3];scale=min(1,math.sqrt(width*height/(iw*ih)))
                w,h=max(32,round(iw*scale/32)*32),max(32,round(ih*scale/32)*32)
                image=self.fit_frame(image,{'width':w,'height':h,'output_width':w,'output_height':h});z=self.vae.encode(image)
                blocks.append({'kind':'image','latent_h':h//16,'latent_w':w//16,'latent':z})
            items.append({'type':'image','data':image})
        master=None;master_z=None
        for entry in plan['audios']:
            audio=read_audio(request['audios'][entry['index']-1],entry['start'],opts['frames']/24,entry['role'] in ('lipsync','reuse'),request.get('audio_tail_padding',False))
            z,t=h3._encode_ref_audio(self.audio_vae,audio)
            blocks.append({'kind':'audio','ref_audio_t':t,'audio_latent':z});items.append({'type':'audio'})
            if entry['role'] in ('lipsync','reuse'):master,master_z=audio,z
        # Internal memory follows explicit references, preserving Picture ordinals.
        # Opening anchor and two recent endings are visible to the text encoder.
        if request.get('scene_index',0)>0 and request.get('continuity')!='cut':
            memory=[self.anchor,*self.recent]
            for image in memory:
                if image is not None:items.append({'type':'image','data':image})
            if self.recent and not any(g['resolved_frame_index']==0 for g in guides):
                z=self.vae.encode(self.fit_frame(self.recent[-1],opts))
                guides.append({'resolved_frame_index':0,'latent':z})
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
        from h3chat.video_options import resolve_canvas
        generation_started=time.monotonic();timings={}
        torch,comfy=self.torch,self.comfy
        images=self.images(request['images'])
        if request.get('sequence')!=getattr(self,'sequence',None) or request.get('scene_index',0)==0 or request.get('continuity')=='cut':
            self.sequence=request.get('sequence');self.anchor=None;self.recent=[]
        if request.get('resume_memory'):self.restore_memory(request['resume_memory'])
        opts=resolve_canvas(request['options'],request['plan'],[(im.shape[2],im.shape[1]) for im in images],request.get('format_prompt',request['plan'].get('prompt','')))
        if request.get('canvas'):opts.update(request['canvas'])
        request=request|{'options':opts}
        emit('stage',message=f"Video · formato {opts['aspect']} · {opts['output_width']}×{opts['output_height']} · "+('dall’immagine guida' if opts['aspect_source']=='image' else 'dal prompt' if opts['aspect_source']=='prompt' else 'dal preset'))
        preparation_started=time.monotonic()
        if self.model is None and not self.offload:self.load_diffuser()
        if self.clip is None:self.load_conditioners()
        timings['conditioner_reload']=time.monotonic()-preparation_started
        # Quantized parameters are rewrapped while offloading. no_grad avoids
        # inference tensors without version counters in PyTorch's .to() path.
        with torch.no_grad():
            emit('stage',message='Video · preparazione istruzioni, fotogrammi e audio')
            self.phase='Video · preparazione istruzioni, fotogrammi e audio'
            conditioning_started=time.monotonic()
            positive,latent,master,grid_frames=self.condition(request,images)
            timings['conditioning']=time.monotonic()-conditioning_started
            images=None
            diffuser_started=time.monotonic()
            if self.offload:
                emit('stage',message='Video · rilascio encoder e VAE dopo il condizionamento')
                self.discard('clip','vae','audio_vae')
            if self.model is None:self.load_diffuser()
            if opts.get('attention')=='veda':
                attention_backend=self.configure_attention('veda',opts.get('attention_chunks',0),opts)
            else:attention_backend=self.configure_attention(opts.get('attention','auto'),opts.get('attention_chunks',0))
            timings['diffuser_load']=time.monotonic()-diffuser_started
            negative=[[torch.zeros_like(value),info.copy()] for value,info in positive]
            model=self.h3.MiniMaxH3SigmaShift.execute(self.model,opts['shift_video'],opts['shift_audio'])[0]
            noise=comfy.sample.prepare_noise(latent['samples'],opts['seed'])
            emit('stage',message='Video · generazione MiniMax H3')
            self.phase='Video · generazione MiniMax H3'
            sampling_started=time.monotonic();last_step=sampling_started;step_seconds=[]
            def progress(step,x0,x,total):
                nonlocal last_step
                now=time.monotonic();seconds=now-last_step;last_step=now
                step_seconds.append(seconds)
                logging.info('H3 sampling step %d/%d: %.2f s',step+1,total,seconds)
                emit('progress',step=step+1,steps=total,step_seconds=seconds)
            samples=comfy.sample.sample(model,noise,opts['steps'],opts['cfg'],opts['sampler'],opts['scheduler'],positive,negative,latent['samples'],noise_mask=latent.get('noise_mask'),disable_pbar=True,seed=opts['seed'],
                callback=progress)
            sampling_seconds=time.monotonic()-sampling_started
            veda_result={}
            if getattr(self,'veda_patch',None) is not None:
                from h3chat.veda import report
                veda_result=report(self.veda_patch)
                if not veda_result['active']:
                    from comfy.ldm.modules import attention
                    attention_backend='sage' if attention.SAGE_ATTENTION_IS_AVAILABLE else 'pytorch'
                    emit('stage',message='Video · VEDA non utilizzata · '+veda_result['fallback_reason'])
            decoder_started=time.monotonic()
            if self.offload:
                emit('stage',message='Video · rilascio diffusore prima della decodifica')
                model=None
                if getattr(self,'veda_patch',None) is not None:
                    from h3chat.veda import release
                    release(self.veda_patch)
                self.veda_base_model=None;self.veda_patch=None
                self.discard('model')
                self.vae=comfy.sd.VAE(sd=comfy.utils.load_torch_file(self.files['vae'],safe_load=True))
            timings['decoder_load']=time.monotonic()-decoder_started
            emit('stage',message='Video · decodifica fotogrammi sulla GPU')
            self.phase='Video · decodifica fotogrammi sulla GPU'
            decode_started=time.monotonic()
            pixels=self.vae.decode(samples.unbind()[0])
            if pixels.ndim==5:pixels=pixels.reshape(-1,*pixels.shape[-3:])
            if len(pixels)<opts['frames']:raise RuntimeError('Il VAE non ha decodificato tutti i fotogrammi.')
            left=(opts['width']-opts['output_width'])//2;top=(opts['height']-opts['output_height'])//2
            pixels=pixels[:,top:top+opts['output_height'],left:left+opts['output_width'],:]
            if request.get('sequence'):
                if self.anchor is None:self.anchor=pixels[:1].detach().cpu().clone()
                self.recent=[*self.recent[-1:],pixels[opts['frames']-1:opts['frames']].detach().cpu().clone()]
            timings['video_decode']=time.monotonic()-decode_started
            emit('stage',message='Video · preparazione audio e salvataggio MP4')
            self.phase='Video · preparazione audio e salvataggio MP4'
            audio_started=time.monotonic()
            if master is None:
                from comfy_extras.nodes_audio import vae_decode_audio
                if self.audio_vae is None:
                    self.audio_vae=comfy.sd.VAE(sd=comfy.utils.load_torch_file(self.files['audio_vae'],safe_load=True))
                master=vae_decode_audio(self.audio_vae,{'samples':samples})
            timings['audio_decode']=time.monotonic()-audio_started
            saving_started=time.monotonic()
            write_video(request['output'],pixels,master,opts['frames'])
            timings['saving']=time.monotonic()-saving_started
        timings['sampling']=sampling_seconds;timings['generation']=time.monotonic()-generation_started
        emit('done',parameters={'fps':24,'duration':opts['frames']/24,'model_frames':grid_frames,'output_frames':opts['frames'],'width':opts['output_width'],'height':opts['output_height'],'canvas_width':opts['width'],'canvas_height':opts['height'],'aspect':opts['aspect'],'aspect_source':opts['aspect_source'],'format_image':opts['format_image'],'engine':'minimax-h3','attention_backend':attention_backend,'attention_requested':opts.get('attention','auto'),'veda':veda_result,'attention_chunks':self.attention_chunks,'sampling_seconds':sampling_seconds,'step_seconds':step_seconds,'timings':timings,'audio_sample_rate':master['sample_rate'],'audio_preserved':any(x['role'] in ('lipsync','reuse') for x in request['plan']['audios'])})

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

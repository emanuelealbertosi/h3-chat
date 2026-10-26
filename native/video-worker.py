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

def configure_cuda_allocator(environ,torch_version):
    """Match ComfyUI's CUDA allocator setup before importing PyTorch.

    Keep explicit operator configuration, including the newer variable name.
    The bundled CUDA runtime supports async allocation; non-CUDA/old builds
    retain PyTorch's default. Comfy's weight-transfer path must use the same
    allocator setting rather than its native cast-buffer path.
    """
    config=environ.get('PYTORCH_ALLOC_CONF') or environ.get('PYTORCH_CUDA_ALLOC_CONF')
    if config is None:
        try:
            major=int(torch_version.split('.',1)[0])
            cuda=int(torch_version.split('+cu',1)[1].split('.',1)[0])
        except (ValueError,IndexError):major=cuda=0
        if major>=2 and cuda>=114:
            config='backend:cudaMallocAsync'
            environ['PYTORCH_CUDA_ALLOC_CONF']=config
    options=dict(item.strip().split(':',1) for item in (config or '').split(',') if ':' in item)
    return options.get('backend','native').strip()=='cudaMallocAsync'

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

def conditioning_memory(tokens,device=None):
    """Budget expanded Qwen3-VL image tokens before placing encoder weights.

    H3's bundled encoder has no activation estimator. Counting just the image
    placeholder leaves too little CUDA workspace for the expanded multimodal
    sequence; Windows may spill allocations instead of raising an OOM.
    Keep all supplied pixels/tokens and leave headroom for fp32 Qwen activations.
    """
    sequence=0;images=0;largest_vision=0
    for batch in tokens.get('qwen3vl_32b',[]):
        for token,*_ in batch:
            if isinstance(token,dict) and token.get('type')=='image':
                h,w=token['data'].shape[-3:-1]
                merged=math.ceil(h/32)*math.ceil(w/32)
                sequence+=merged;images+=1;largest_vision=max(largest_vision,merged*4)
            else:sequence+=1
    reserve=sequence*5120*96+largest_vision*1152*48
    logging.info('H3 encoder workspace: %d expanded tokens, %d images, %.2f MB reserved',sequence,images,reserve/1024**2)
    return reserve

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
        from importlib.metadata import version,PackageNotFoundError
        try:torch_version=version('torch')
        except PackageNotFoundError:torch_version=''
        args.cuda_malloc=configure_cuda_allocator(os.environ,torch_version)
        import torch
        if not torch.cuda.is_available():raise ValueError('MiniMax H3 richiede una GPU NVIDIA CUDA. Nessun passaggio automatico al calcolo CPU.')
        torch.set_num_threads(request.get('threads',4));self.torch=torch
        logging.info('H3 CUDA allocator: %s',torch.cuda.get_allocator_backend())
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
            if changed:
                from h3chat.video_memory import diffuser_placement
                placement=diffuser_placement(models)
                if placement:
                    self.diffuser_placement=placement;logging.info('H3 diffuser placement: %s',json.dumps(placement))
                note=' · pesi in streaming dalla RAM; il primo passo può essere molto lento' if placement and placement['streaming_from_ram'] else ''
                emit('stage',message=self.phase+note)
            return result
        comfy.model_management.load_models_gpu=load_gpu
        comfy.utils.PROGRESS_BAR_ENABLED=False
        self.files=request['files'];self.offload=request['offload'];self.fast_omni=request.get('checkpoint_family')=='fasth3-omni'
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
        from h3chat.video_mlp import require_supported_weights
        require_supported_weights(self.model.model.diffusion_model)
        from h3chat.video_activation_memory import install as install_activation_memory
        self.activation_memory_report=install_activation_memory(self.model.model.diffusion_model)
        logging.info('H3 packed activation lifetime: %s',self.activation_memory_report)
        head=self.model.model.diffusion_model.final_layer
        from h3chat.fasth3 import check_heads
        check_heads(head.video_out.weight.shape[0],head.audio_out.weight.shape[0],getattr(self,'fast_omni',False))
        self.mlp_chunk_mb=0
        if self.offload and self.torch.cuda.get_device_properties(0).total_memory<=24*1024**3:
            from h3chat.video_mlp import install
            import comfy.ops
            blocks=install(self.model.model.diffusion_model,self.torch,comfy.ops)
            if blocks:
                self.mlp_chunk_mb=512
                logging.info('H3 quantized MLP workspace: %d blocks, %d MB per token batch, weights transferred once',blocks,self.mlp_chunk_mb)

    def load_conditioners(self):
        comfy,torch,files=self.comfy,self.torch,self.files
        emit('stage',message='Video · lettura encoder Qwen3-VL MiniMax H3')
        # LOW_VRAM defaults text encoding to CPU in the underlying library.
        # Override placement: offload stores weights in RAM, all inference is CUDA.
        device=comfy.model_management.get_torch_device()
        self.clip=comfy.sd.load_clip([files['llm']],clip_type=comfy.sd.CLIPType.MINIMAX,
            model_options={'load_device':device,'offload_device':torch.device('cpu') if self.offload else device,'initial_device':torch.device('cpu')})
        if not hasattr(self.clip.cond_stage_model,'memory_estimation_function'):
            self.clip.cond_stage_model.memory_estimation_function=conditioning_memory
        emit('stage',message='Video · lettura VAE video e audio')
        self.vae=comfy.sd.VAE(sd=comfy.utils.load_torch_file(files['vae'],safe_load=True))
        self.audio_vae=comfy.sd.VAE(sd=comfy.utils.load_torch_file(files['audio_vae'],safe_load=True))
        if self.vae.latent_channels!=24 or self.audio_vae.latent_channels!=32:raise ValueError('VAE non compatibili con MiniMax H3: video 24 canali, audio 32 canali.')

    def configure_attention(self, preference, chunks=0, veda_options=None):
        from comfy.ldm.modules import attention
        if preference=='vsa':
            if not getattr(self,'fast_omni',False):raise ValueError('VSA richiede il caricamento con profilo FastH3 Omni.')
            if getattr(self,'fast_base_model',None) is not None:self.model=self.fast_base_model
            self.fast_base_model=self.model
            # The fallback is dense, while the learned VSA branch uses the
            # bundled ComfyKitchen block-sparse kernels and compression gates.
            dense=getattr(attention,'attention_comfy_kitchen_int8',None) if getattr(attention,'COMFY_KITCHEN_INT8_ATTENTION_IS_AVAILABLE',False) else None
            self.model.set_model_optimized_attention(dense or attention.attention_pytorch)
            from comfy_extras.nodes_sparse_attention import apply_block_sparse_attention
            from h3chat.fasth3 import attach
            self.model=attach(self.model,apply_block_sparse_attention);self.attention_chunks=1
            emit('stage',message='Video · FastH3 Omni · VSA 10% · 8 passi')
            logging.info('FastH3 Omni: trained VSA 10%%, start=0, end=1, sink=exact_kv_and_rows, no extra PDD')
            return 'vsa'
        if getattr(self,'veda_base_model',None) is not None:
            self.model=self.veda_base_model
            from h3chat.veda import release
            release(getattr(self,'veda_patch',None))
        self.veda_base_model=None;self.veda_patch=None
        if preference=='comfy_kitchen':
            function=getattr(attention,'attention_comfy_kitchen_int8',None)
            if not getattr(attention,'COMFY_KITCHEN_INT8_ATTENTION_IS_AVAILABLE',False) or not callable(function):
                raise ValueError('ComfyKitchen INT8 attention non disponibile nel runtime o sulla GPU. Scegli VEDA, Sage o PyTorch; nessun backend alternativo è stato attivato.')
            # Use the native implementation, including its container path that
            # releases floating-point Q/K/V after prequantization. No Sage wrapper.
            self.attention_chunks=1
            self.model.set_model_optimized_attention(function)
            logging.info('Video attention backend: comfy_kitchen (requested: %s, head chunks: 1)',preference)
            emit('stage',message='Video · attenzione ComfyKitchen INT8')
            return 'comfy_kitchen'
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
        # ComfyUI resets these at graph node boundaries. The standalone worker
        # has no graph executor: release transfer buffers and their module
        # references explicitly before dropping the finished phase's weights.
        self.comfy.model_management.reset_cast_buffers()
        for name in names:setattr(self,name,None)
        gc.collect()
        self.comfy.model_management.cleanup_models()
        self.comfy.model_management.soft_empty_cache(force=True)

    def memory_snapshot(self, phase):
        cuda=self.torch.cuda
        if not callable(getattr(cuda,'memory_allocated',None)):return None
        free,total=cuda.mem_get_info()
        loaded=[]
        for item in self.comfy.model_management.current_loaded_models:
            model=item.model
            if model is not None:loaded.append(type(model.model).__name__)
        allocator=getattr(cuda,'get_allocator_backend',None)
        snapshot={'phase':phase,'allocator':allocator() if callable(allocator) else 'unknown','allocated_mb':round(cuda.memory_allocated()/1024**2,2),
            'reserved_mb':round(cuda.memory_reserved()/1024**2,2),'free_mb':round(free/1024**2,2),
            'total_mb':round(total/1024**2,2),'pinned_mb':round(self.comfy.model_management.TOTAL_PINNED_MEMORY/1024**2,2),
            'loaded_models':loaded}
        logging.info('H3 memory: %s',json.dumps(snapshot))
        return snapshot

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
        self.source_info=None
        if request.get('extension_context'):
            from h3chat.video_extension import window
            context=request['extension_context'];spec=window(opts['frames']-5,context['side'])
            frames=torch.cat([self.fit_frame(image,opts) for image in self.images(context['paths'])],dim=0)
            guides.append({'resolved_frame_index':spec['guide_start'],'latent':self.vae.encode(frames)})
            emit('stage',message='Estensione video · contesto temporale nativo di 5 fotogrammi al raccordo')
        if request.get('source_video'):
            from h3chat.video_reference import decode_source,video_block,anchor_positions,source_still
            emit('stage',message='Modifica video · lettura della clip sorgente e dei suoi movimenti')
            aligned=opts.get('source_conditioning')=='aligned'
            source_frames,qwen_frames,self.source_info=decode_source(request['source_video'],opts if aligned else None)
            emit('stage',message=f"Modifica video · codifica {self.source_info['frames']} fotogrammi sorgente")
            z=self.vae.encode(source_frames)
            if aligned:
                guides.insert(0,{'resolved_frame_index':0,'latent':z})
                emit('stage',message='Modifica video · guida allineata sul canvas di uscita')
            else:blocks.append(video_block(z))
            source_anchors=[]
            for frame in ([] if aligned else anchor_positions(request['source_video'])):
                # A supplied edited keyframe overrides the original at this time.
                if any(g['resolved_frame_index']==frame for g in guides):continue
                image=self.fit_frame(source_still(source_frames,self.source_info,frame),opts)
                guides.append({'resolved_frame_index':frame,'latent':self.vae.encode(image)})
                source_anchors.append(frame)
            self.source_info['anchored_frames']=sorted({g['resolved_frame_index'] for g in guides})
            logging.info('H3 source video: start=%.6f s, frames=%d, guide=%.2f MP, size=%dx%d, keyframes=%s',
                self.source_info['start'],self.source_info['frames'],self.source_info['megapixels'],
                self.source_info['content_width'],self.source_info['content_height'],self.source_info['anchored_frames'])
            emit('stage',message=f"Modifica video · sorgente {self.source_info['megapixels']:g} MP · {len(guides)} fotogrammi guida · uscita {opts['megapixels']:g} MP")
            if source_anchors:emit('stage',message='Modifica video · ancoraggio sorgente · fotogrammi '+', '.join(map(str,source_anchors)))
            if not aligned:
                items.append({'type':'video','data':qwen_frames,
                              'timestamps':[i/2 for i in range(qwen_frames.shape[0])]})
            del source_frames,qwen_frames
        master=None;master_z=None
        for entry in plan['audios']:
            audio_frames=opts['frames']-5 if request.get('extension_context') else opts['frames']
            audio=read_audio(request['audios'][entry['index']-1],entry['start'],audio_frames/24,entry['role'] in ('lipsync','reuse'),request.get('audio_tail_padding',False))
            if request.get('extension_context'):
                from h3chat.video_extension import window,pad_audio
                audio=pad_audio(audio,window(audio_frames,request['extension_context']['side']))
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
        generation_started=time.monotonic();timings={};memory=[]
        torch,comfy=self.torch,self.comfy
        images=self.images(request['images'])
        if request.get('sequence')!=getattr(self,'sequence',None) or request.get('scene_index',0)==0 or request.get('continuity')=='cut':
            self.sequence=request.get('sequence');self.anchor=None;self.recent=[]
        if request.get('resume_memory'):self.restore_memory(request['resume_memory'])
        opts=resolve_canvas(request['options'],request['plan'],[(im.shape[2],im.shape[1]) for im in images],request.get('format_prompt',request['plan'].get('prompt','')),force_aspect=request.get('forced_aspect'))
        if getattr(self,'fast_omni',False):
            from h3chat.fasth3 import validate as validate_fast
            validate_fast(opts)
        if request.get('canvas'):opts.update(request['canvas'])
        extension=None
        if request.get('extension_context'):
            from h3chat.video_extension import window
            extension=window(opts['frames'],request['extension_context']['side'])
            opts=opts|{'frames':extension['frames']}
        request=request|{'options':opts}
        emit('stage',message=f"Video · formato {opts['aspect']} · {opts['output_width']}×{opts['output_height']} · "+('dall’immagine guida' if opts['aspect_source']=='image' else 'dal prompt' if opts['aspect_source']=='prompt' else 'dalle impostazioni della richiesta' if opts['aspect_source']=='request' else 'dal preset'))
        preparation_started=time.monotonic()
        if any(x['weight'] for x in opts.get('loras',[])) and self.model is not None:
            self.discard('model')
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
            memory.append(self.memory_snapshot('after_conditioning'))
            images=None
            diffuser_started=time.monotonic()
            if self.offload:
                emit('stage',message='Video · rilascio encoder e VAE dopo il condizionamento')
                self.discard('clip','vae','audio_vae')
                memory.append(self.memory_snapshot('conditioners_released'))
            if self.model is None:self.load_diffuser()
            if opts.get('attention')=='veda':
                from h3chat.veda_memory import head_chunks_for_edit
                marker=Path(request['output']).with_name('sampling-diagnostics.json')
                diagnostic=marker.is_file() and json.loads(marker.read_text(encoding='utf-8')).get('first_block_probe') is True
                requested_chunks=opts.get('attention_chunks',0)
                effective_chunks=head_chunks_for_edit(requested_chunks,aligned=bool(request.get('source_video')) and opts.get('source_conditioning')=='aligned',
                    width=opts['width'],height=opts['height'],frames=opts['frames'],total_bytes=torch.cuda.get_device_properties(0).total_memory,diagnostic=diagnostic,
                    source_shape=(self.source_info['width'],self.source_info['height'],self.source_info['frames']) if self.source_info else None,
                    manual=opts.get('attention_chunks_mode')=='manual')
                if effective_chunks!=requested_chunks:emit('stage',message=f'Video · VEDA · suddivisione memoria automatica: {effective_chunks} gruppi di teste')
                attention_backend=self.configure_attention('veda',effective_chunks,opts)
            else:attention_backend=self.configure_attention(opts.get('attention','auto'),opts.get('attention_chunks',0))
            timings['diffuser_load']=time.monotonic()-diffuser_started
            memory.append(self.memory_snapshot('before_sampling'))
            negative=[[torch.zeros_like(value),info.copy()] for value,info in positive]
            lora_result=[]
            if any(x['weight'] for x in opts.get('loras',[])):
                emit('stage',message='Video · preparazione LoRA di editing una sola volta')
                from h3chat.video_loras import apply as apply_loras
                started=time.monotonic()
                self.model,lora_result=apply_loras(self.model,opts['loras'],progress=lambda done,total:emit('stage',message=f'Video · preparazione LoRA · {done}/{total} parametri'),merge=not opts.get('pdd_enabled'))
                timings['lora_load']=time.monotonic()-started
            model=self.h3.MiniMaxH3SigmaShift.execute(self.model,opts['shift_video'],opts['shift_audio'])[0]
            pdd_sigmas=None;pdd_result={}
            if opts.get('pdd_enabled'):
                emit('stage',message='Video · PDD 8 passi · caricamento adattatore e proiezioni')
                pdd_started=time.monotonic()
                from h3chat.video_pdd import apply as apply_pdd
                def pdd_progress(done,total):
                    emit('stage',message=f'Video · preparazione PDD una sola volta · {done}/{total} parametri')
                model,pdd_sigmas,pdd_result=apply_pdd(model,opts,progress=pdd_progress)
                if lora_result:
                    pdd_result['editing_loras_merged_together']=True
                    for item in lora_result:
                        item['merged_patch_keys']=item['prepared_patch_keys']
                        item['merge_deferred_to_pdd']=False
                        item['merged_with_pdd']=True
                logging.info('H3 PDD: %s',pdd_result['info'])
                timings['pdd_load']=time.monotonic()-pdd_started
                Path(request['output']).with_name('pdd-info.json').write_text(json.dumps(pdd_result,ensure_ascii=False,indent=2),encoding='utf-8')
            noise=comfy.sample.prepare_noise(latent['samples'],opts['seed'])
            emit('stage',message='Video · generazione MiniMax H3')
            self.phase='Video · generazione MiniMax H3'
            sampling_started=time.monotonic();last_step=sampling_started;step_seconds=[]
            sampling_memory=Path(request['output']).with_name('sampling-memory.jsonl')
            diagnostic_file=Path(request['output']).with_name('sampling-diagnostics.json')
            diagnostics={}
            if diagnostic_file.is_file():
                value=json.loads(diagnostic_file.read_text(encoding='utf-8'))
                if isinstance(value,dict):diagnostics={k:value.get(k) is True for k in ('synchronize_steps','trim_unused_cache','first_block_probe')}
            def record_sampling_memory(value):
                with sampling_memory.open('a',encoding='utf-8') as stream:
                    stream.write(json.dumps(value,ensure_ascii=False)+'\n')
            def progress(step,x0,x,total):
                nonlocal last_step
                sync_seconds=0
                if diagnostics.get('synchronize_steps'):
                    started=time.monotonic();torch.cuda.synchronize();sync_seconds=time.monotonic()-started
                now=time.monotonic();seconds=now-last_step;last_step=now
                step_seconds.append(seconds)
                snapshot=self.memory_snapshot('step_'+str(step+1))
                if step in (0,total-1):memory.append(snapshot)
                logging.info('H3 sampling step %d/%d: %.2f s',step+1,total,seconds)
                record_sampling_memory({'step':step+1,'seconds':seconds,'completion_sync_seconds':sync_seconds,'memory':snapshot})
                emit('progress',step=step+1,steps=total,step_seconds=seconds)
                from h3chat.video_memory import should_trim_sampling_cache
                if diagnostics.get('trim_unused_cache') and step+1<total and should_trim_sampling_cache(snapshot,self.offload):
                    emit('stage',message='Video · rilascio cache GPU inutilizzata fra i passi')
                    started=time.monotonic()
                    comfy.model_management.soft_empty_cache(force=True)
                    after=self.memory_snapshot('cache_released_after_step_'+str(step+1))
                    record_sampling_memory({'after_step':step+1,'cache_trim_seconds':time.monotonic()-started,'memory':after})
            # A private opt-in diagnostic, consumed by a dedicated native
            # process. Normal render requests never synchronize individual
            # phases or stop at this boundary, and no user preset changes.
            probe=None
            if diagnostics.get('first_block_probe'):
                from h3chat.video_phase_diagnostics import FirstBlockProbe,ProbeComplete
                probe=FirstBlockProbe(torch,Path(request['output']).parent,
                    head_chunks=self.attention_chunks).install(model.model.diffusion_model,getattr(self,'veda_patch',None))
                emit('stage',message='Video · diagnosi primo blocco · nessun rendering completo')
            try:
                samples=comfy.sample.sample(model,noise,opts['steps'],opts['cfg'],opts['sampler'],opts['scheduler'],positive,negative,latent['samples'],noise_mask=latent.get('noise_mask'),disable_pbar=True,seed=opts['seed'],
                    callback=progress,sigmas=pdd_sigmas)
            except BaseException as error:
                if probe is not None and isinstance(error,ProbeComplete):
                    probe.close('done')
                    emit('diagnostic_done',parameters={'completed_blocks':probe.completed_blocks,
                        'report':str(probe.result),'events':str(probe.events),
                        'head_chunks':self.attention_chunks,'activation_memory':getattr(self,'activation_memory_report',{}),
                        'timings':timings,'sampling_seconds':time.monotonic()-sampling_started})
                    return
                if probe is not None:probe.close('error')
                raise
            finally:
                if probe is not None and not probe.closed:probe.close('boundary_not_reached')
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
            if self.offload or opts.get('pdd_enabled') or lora_result:
                emit('stage',message='Video · rilascio diffusore prima della decodifica')
                model=None
                if getattr(self,'veda_patch',None) is not None:
                    from h3chat.veda import release
                    release(self.veda_patch)
                self.veda_base_model=None;self.veda_patch=None
                self.discard('model')
                memory.append(self.memory_snapshot('diffuser_released'))
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
            if extension:
                from h3chat.video_extension import trim_audio
                pixels=pixels[extension['trim_start']:extension['trim_start']+extension['output_frames']]
                master=trim_audio(master,extension)
                opts=opts|{'frames':extension['output_frames']}
            write_video(request['output'],pixels,master,opts['frames'])
            timings['saving']=time.monotonic()-saving_started
        timings['sampling']=sampling_seconds;timings['generation']=time.monotonic()-generation_started
        emit('done',parameters={'fps':24,'duration':opts['frames']/24,'model_frames':grid_frames,'output_frames':opts['frames'],'width':opts['output_width'],'height':opts['output_height'],'canvas_width':opts['width'],'canvas_height':opts['height'],'aspect':opts['aspect'],'aspect_source':opts['aspect_source'],'format_image':opts['format_image'],'engine':'minimax-h3','attention_backend':attention_backend,'attention_requested':opts.get('attention','auto'),'veda':veda_result,'attention_chunks':self.attention_chunks,'attention_chunks_requested':opts.get('attention_chunks',0),'mlp_chunk_mb':getattr(self,'mlp_chunk_mb',0),'activation_memory':getattr(self,'activation_memory_report',{'active':False,'temporaries_released':[],'source_guard':'not_loaded'}),'sampling_seconds':sampling_seconds,'step_seconds':step_seconds,'timings':timings,'loras_applied':lora_result,'memory':[x for x in memory if x is not None],'audio_sample_rate':master['sample_rate'],'audio_preserved':any(x['role'] in ('lipsync','reuse') for x in request['plan']['audios']),**({'video_edit_mode':'source','source_video':self.source_info} if self.source_info else {})})

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

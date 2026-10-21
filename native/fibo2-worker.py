"""Offline FIBO 2.0 worker. Model changes/cancellation are owned by Engine."""
import gc,json,logging,os,sys,time,traceback
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'runtime/fibo2/packages'),str(ROOT/'runtime/vision/packages')]
os.environ.update(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',HF_HUB_DISABLE_TELEMETRY='1',
    HF_HOME=str(ROOT/'runtime/fibo2/cache'),TEMP='F:/H3-TestTmp',TMP='F:/H3-TestTmp')
dll=os.add_dll_directory(str(ROOT/'runtime/vision/dlls')) if os.name=='nt' else None
wire=sys.stdout;sys.stdout=sys.stderr
logging.basicConfig(level=logging.INFO,stream=sys.stderr)
from h3chat.fibo2 import pipeline_root,prompt,negative,validate_options


def emit(event,**values):
    wire.write(json.dumps({'event':event,**values},ensure_ascii=False)+'\n');wire.flush()


class Worker:
    def load(self,request):
        emit('stage',message='FIBO 2.0 · caricamento librerie e pesi locali')
        import torch
        from diffusers import BriaFibo2Pipeline
        root=pipeline_root(request['files']);self.backend=request['backend'];self.torch=torch
        if self.backend not in ('cpu','cuda'):raise ValueError('Backend FIBO non valido.')
        torch.set_num_threads(request.get('threads',6))
        # Explicit offline mode: missing configuration is an error, never an
        # implicit model/code download or a remote inference call.
        from h3chat.fibo2 import quantized
        self.int8=quantized(request['files']);quant_info={}
        extra={}
        if self.int8:
            if self.backend!='cuda':raise ValueError('FIBO INT8: la prima integrazione richiede NVIDIA CUDA.')
            sys.path.insert(0,str(ROOT/'runtime/vision/core'))
            import comfy.cli_args
            comfy.cli_args.args.cpu=False
            from h3chat.fibo2_int8 import load_components
            emit('stage',message='FIBO INT8 · pesi e encoder quantizzati, senza riconversione completa in BF16')
            transformer,encoder,quant_info=load_components(root,request['files'],torch)
            extra={'transformer':transformer,'text_encoder':encoder}
        self.pipe=BriaFibo2Pipeline.from_pretrained(str(root),torch_dtype=torch.bfloat16 if self.backend=='cuda' else torch.float32,
            local_files_only=True,low_cpu_mem_usage=True,**extra)
        self.fonts=[str(root/'fonts'/name) for name in ('Aileron-Regular.otf','DejaVuSans.ttf')]
        self.offload='cpu'
        self.memory_info=quant_info
        if self.backend=='cuda':
            # 8.1B BF16 weights alone almost fill a 16 GiB card. Whole-model
            # offload is insufficient; leaf modules are moved only as needed.
            self.offload=request.get('fibo_offload','sequential')
            if self.int8:
                # Quantization makes each complete component fit on a 16 GiB
                # GPU. Move components only between phases, not every layer.
                self.pipe.enable_model_cpu_offload()
                self.offload='int8-components'
            elif self.offload=='full':
                # Explicit experiment: let the CUDA driver handle any system
                # memory fallback. This does not enable or promise fallback.
                emit('stage',message='FIBO 2.0 · caricamento completo CUDA · memoria condivisa gestita dal driver, se disponibile')
                self.pipe.to('cuda')
            elif self.offload=='resident':
                from h3chat.fibo2_placement import resident
                self.memory_info=resident(self.pipe,torch)
                emit('stage',message='FIBO 2.0 · '+str(self.memory_info['resident_blocks'])+' blocchi stabili sulla GPU, '+str(self.memory_info['offloaded_blocks'])+' trasferiti a richiesta')
            elif self.offload=='group':
                from diffusers.hooks import apply_group_offloading
                # No asynchronous prefetch/pinned copy: avoid doubling host
                # weights on 40 GiB systems. Keep the small VAE on CUDA; its
                # encode/decode entry points do not pass through root forward.
                self.pipe.transformer.enable_group_offload(onload_device=torch.device('cuda'),offload_device=torch.device('cpu'),
                    offload_type='block_level',num_blocks_per_group=16,use_stream=False)
                apply_group_offloading(self.pipe.text_encoder,onload_device=torch.device('cuda'),offload_device=torch.device('cpu'),
                    offload_type='block_level',num_blocks_per_group=16,use_stream=False)
                self.pipe.vae.to('cuda')
            elif self.offload=='sequential':self.pipe.enable_sequential_cpu_offload()
            else:raise ValueError('Gestione memoria FIBO non valida.')
            self.pipe.vae.enable_tiling()
        self.pipe.set_progress_bar_config(disable=True)
        emit('ready')

    def generate(self,request):
        validate_options(request)
        if request.get('loras'):raise ValueError('LoRA FIBO 2.0: supporto non ancora verificato in questa integrazione.')
        from PIL import Image
        references=request.get('references',[])
        if len(references)>4:raise ValueError('FIBO: massimo 4 riferimenti per questa integrazione.')
        images=[]
        for path in references:
            with Image.open(path) as image:images.append(image.convert('RGB'))
        kwargs={'prompt':prompt(request['prompt'],bool(images)),
            'negative_prompt':negative(request.get('negative_prompt',''),bool(images)),
            'num_inference_steps':request['steps'],'guidance_scale':request['cfg'],
            'generator':self.torch.Generator(device='cpu').manual_seed(request['seed']),
            'fonts':self.fonts}
        if images:kwargs['image']=images if len(images)>1 else images[0]
        if not images or not request.get('preserve_reference_aspect',True):
            kwargs.update(width=request['width'],height=request['height'])
        started=last=time.monotonic();step_times=[]
        def progress(pipe,index,timestep,values):
            nonlocal last
            now=time.monotonic();step_times.append(now-last);last=now
            emit('progress',step=index+1,steps=request['steps'],step_seconds=step_times[-1]);return values
        kwargs['callback_on_step_end']=progress
        memory='a componenti INT8' if self.offload=='int8-components' else 'nessuno · allocazione completa CUDA' if self.offload=='full' else 'parzialmente residente' if self.offload=='resident' else 'gruppi di 16 blocchi' if self.offload=='group' else 'sequenziale' if self.offload=='sequential' else 'CPU'
        emit('stage',message='FIBO 2.0 · encoder '+('dei riferimenti e del prompt' if images else 'del prompt')+' · offload '+memory)
        if self.backend=='cuda':self.torch.cuda.reset_peak_memory_stats()
        with self.torch.no_grad() if getattr(self,'int8',False) else self.torch.inference_mode():image=self.pipe(**kwargs).images[0]
        output=Path(request['output']);output.parent.mkdir(parents=True,exist_ok=True);image.save(output,format='PNG')
        params={k:request[k] for k in ('steps','cfg','seed','sampler','scheduler')}
        params.update(width=image.width,height=image.height,megapixels=image.width*image.height/1e6,
            reference_count=len(images),seconds=round(time.monotonic()-started,2),offload=self.offload,
            step_seconds=[round(t,3) for t in step_times])
        if self.backend=='cuda':params['peak_allocated_gib']=round(self.torch.cuda.max_memory_allocated()/1024**3,3)
        params.update(getattr(self,'memory_info',{}))
        emit('done',parameters=params)


def main():
    worker=Worker();emit('hello')
    for line in sys.stdin:
        try:
            request=json.loads(line)
            if request['op']=='load':worker.load(request)
            elif request['op']=='generate':worker.generate(request)
            elif request['op']=='unload':worker.pipe=None;gc.collect();emit('unloaded')
            elif request['op']=='stop':return 0
            else:raise ValueError('Operazione FIBO non valida.')
        except Exception as exc:
            traceback.print_exc();emit('error',message=str(exc))
    return 0
if __name__=='__main__':raise SystemExit(main())

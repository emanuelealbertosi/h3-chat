# SPDX-License-Identifier: GPL-3.0-or-later
"""Headless P-H3 worker using a pinned separate Comfy core, not its server."""
import importlib.util
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('h3_vision_worker',ROOT/'native/vision-worker.py')
base=importlib.util.module_from_spec(spec);spec.loader.exec_module(base)
# The shared module has not imported Comfy/Torch yet. Select this process's
# isolated core and quantization extensions before initializing either one.
sys.path[:0]=[str(ROOT/'runtime/ph3/packages'),str(ROOT/'runtime/ph3/core')]
emit=base.emit


class Worker(base.Worker):
    def load(self,request):
        self.initialize(request)
        comfy=self.comfy;self.architecture='ph3';self.files=request['files']
        self.torch.set_num_threads(request.get('threads',4))
        emit('stage',message='P-H3 · caricamento diffusore W4A8')
        self.base_model=comfy.sd.load_diffusion_model(self.files['diffusion'])
        if self.base_model is None or type(self.base_model.model.model_config).__name__!='MiniMaxH3':raise ValueError('Diffusore P-H3-Image non riconosciuto.')
        emit('stage',message='P-H3 · encoder Qwen3-VL e VAE immagini')
        self.base_clip=comfy.sd.load_clip([self.files['llm']],clip_type=comfy.sd.CLIPType.MINIMAX)
        self.vae=comfy.sd.VAE(sd=comfy.utils.load_torch_file(self.files['vae'],safe_load=True))
        emit('ready')

    def generate(self,request):
        import gc,time
        import numpy as np
        from PIL import Image
        from h3chat.ph3_image import SIGMAS,validate,upsample_input,apply_loras
        from comfy_extras.nodes_minimax_h3 import PH3ImageConditioning,MiniMaxH3SigmaShift
        import comfy.nested_tensor
        validate({'architecture':'ph3'},request)
        if len(request.get('references',[]))>8:raise ValueError('P-H3 accetta fino a otto immagini.')
        torch,comfy=self.torch,self.comfy;prompt=request['prompt'];expanded=False
        images=self.images(request.get('references',[]));reference_count=len(images)
        if images and request.get('preserve_reference_aspect',True):
            import math
            area=request['width']*request['height'];ratio=images[0].shape[2]/images[0].shape[1]
            width=math.ceil(math.sqrt(area*ratio)/32)*32;height=math.ceil(area/width/32)*32
            if min(width,height)<256 or max(width,height)>8192:raise ValueError('Riferimento P-H3 con proporzioni troppo estreme: scegli un formato di uscita.')
            request=request|{'width':width,'height':height}
        if request.get('ph3_upsample',True) and not self.files.get('upsampler'):
            raise ValueError('Collega l’espansore prompt P-H3 oppure disattivalo nelle impostazioni immagini.')
        with torch.no_grad():
            if request.get('ph3_upsample',True) and self.files.get('upsampler'):
                self.phase='P-H3 · espansione del prompt';emit('stage',message=self.phase)
                up=comfy.sd.load_clip([self.files['upsampler']],clip_type=comfy.sd.CLIPType.MINIMAX)
                try:
                    from comfy_extras.nodes_textgen import TextGenerateV2
                    brief=upsample_input(prompt,request['width'],request['height'])
                    if images:brief='\n'.join(f'<Picture {i}>' for i in range(1,len(images)+1))+'\n'+brief
                    small={}
                    for i,im in enumerate(images,1):
                        h,w=im.shape[1:3];scale=min(1.,(1_000_000/(h*w))**.5)
                        small[f'image_{i}']=comfy.utils.common_upscale(im.movedim(-1,1),max(32,round(w*scale/32)*32),max(32,round(h*scale/32)*32),'bilinear','disabled').movedim(1,-1)
                    output=TextGenerateV2.execute(up,brief,2048,{'sampling_mode':'off'},thinking=True,images=small,mtp='off')
                    text=output[0].strip()
                    if not text:raise ValueError('P-H3: l’espansore non ha restituito istruzioni complete.')
                    prompt=text;expanded=True
                finally:self.release_gpu(up.patcher);del up;gc.collect()
            self.phase='P-H3 · codifica istruzioni e riferimenti';emit('stage',message=self.phase)
            try:
                positive,latent=PH3ImageConditioning.execute(self.base_clip,prompt,request['width'],request['height'],
                    vae=self.vae,images={f'image_{i}':im for i,im in enumerate(images,1)})
            finally:self.release_gpu(self.base_clip.patcher);self.release_gpu(self.vae.patcher)
            model=MiniMaxH3SigmaShift.execute(self.base_model,1.,1.)[0]
            model,loras_applied=apply_loras(model,request.get('loras',[]),comfy)
            samples=latent['samples'];noise=comfy.sample.prepare_noise(samples,request['seed'])
            self.phase='P-H3 · generazione immagine · 8 passi';emit('stage',message=self.phase);last=time.monotonic()
            def progress(step,x0,x,total):
                nonlocal last
                now=time.monotonic();emit('progress',step=step+1,steps=total,step_seconds=now-last);last=now
            try:
                sampled=comfy.sample.sample(model,noise,8,1.,'euler','simple',positive,[],samples,
                    sigmas=torch.tensor(SIGMAS,dtype=torch.float32),callback=progress,disable_pbar=True,seed=request['seed'])
            finally:self.release_gpu(model)
            video=sampled.unbind()[0] if sampled.is_nested else sampled
            self.phase='P-H3 · decodifica VAE';emit('stage',message=self.phase)
            try:
                pixels=self.vae.decode(video)
                if pixels.ndim==5:pixels=pixels.reshape(-1,*pixels.shape[-3:])
                array=(pixels[0].clamp(0,1).cpu().numpy()*255).round().astype(np.uint8)
                Image.fromarray(array).save(request['output'],format='PNG')
            finally:self.release_gpu(self.vae.patcher)
        emit('done',parameters={'width':int(array.shape[1]),'height':int(array.shape[0]),'steps':8,'cfg':1,
            'sampler':'euler','scheduler':'ph3_image','sigmas':list(SIGMAS),'seed':request['seed'],
            'reference_count':reference_count,'engine':'vision','ph3_upsample':expanded,'effective_prompt':prompt,'loras_applied':loras_applied})


base.Worker=Worker
if __name__=='__main__':raise SystemExit(base.main())

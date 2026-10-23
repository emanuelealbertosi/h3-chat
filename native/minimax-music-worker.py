# SPDX-License-Identifier: GPL-3.0-or-later
"""Headless MiniMax Music 3 using the application's private inference library."""
import importlib.util,json,sys,traceback,wave
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('h3_vision_worker',ROOT/'native/vision-worker.py')
vision=importlib.util.module_from_spec(spec);spec.loader.exec_module(vision)
emit=vision.emit

class Worker(vision.Worker):
    def load(self,request):
        self.initialize(request);torch,comfy=self.torch,self.comfy
        torch.set_num_threads(request.get('threads',4));comfy.utils.PROGRESS_BAR_ENABLED=False
        files=request['files'];emit('stage',message='Caricamento MiniMax Music 3 · diffusore')
        self.base_model=comfy.sd.load_diffusion_model(files['diffusion'])
        if self.base_model is None or type(self.base_model.model.model_config).__name__!='MiniMaxMusic3':raise ValueError('Diffusore MiniMax Music 3 incompatibile.')
        emit('stage',message='Caricamento MiniMax Music 3 · encoder musicale')
        self.base_clip=comfy.sd.load_clip([files['llm']],clip_type=comfy.sd.CLIPType.MINIMAX)
        self.vae=comfy.sd.VAE(sd=comfy.utils.load_torch_file(files['vae'],safe_load=True))
        if self.vae.latent_channels!=128 or self.vae.latent_dim!=1:raise ValueError('Decoder MiniMax Music 3 incompatibile.')
        emit('ready')

    def generate(self,request):
        from comfy.ldm.minimax_music.dit import latent_length
        from h3chat.minimax_music import validate
        torch,comfy=self.torch,self.comfy;p=validate(request['parameters']);seed=p['seed']
        if seed<0:raise ValueError('Seed effettivo non valido.')
        with torch.inference_mode():
            self.phase='Pianificazione musicale autoregressiva · MiniMax Music 3';emit('stage',message=self.phase)
            try:
                tokens=self.base_clip.tokenize(request['style'],lyrics=request['lyrics'],seed=seed,max_audio_frames=max(1,round(p['max_duration']*25)),cfg_scale=p['cfg_scale'],top_k=p['top_k'])
                positive=self.base_clip.encode_from_tokens_scheduled(tokens)
                frames=positive[0][0].shape[1]
                if not 1<=frames<=9000:raise RuntimeError('Sequenza musicale vuota o troppo lunga.')
                for hidden,extra in positive:extra['conditioning_scale']=torch.ones((hidden.shape[0],1,1),device=hidden.device,dtype=hidden.dtype)
                negative=[[torch.zeros_like(hidden),dict(extra)|{'conditioning_scale':torch.zeros_like(extra['conditioning_scale'])}] for hidden,extra in positive]
            finally:self.release_gpu(self.base_clip.patcher)
            latent=torch.zeros((1,128,latent_length(frames)),device=comfy.model_management.intermediate_device(),dtype=comfy.model_management.intermediate_dtype())
            noise=comfy.sample.prepare_noise(latent,seed);self.phase='Sintesi audio · MiniMax Music 3';emit('stage',message=self.phase)
            def progress(step,x0,x,total):emit('progress',step=step+1,steps=total)
            try:samples=comfy.sample.sample(self.base_model,noise,p['num_inference_steps'],p['diffusion_cfg'],p['sampler'],p['scheduler'],positive,negative,latent,disable_pbar=True,seed=seed,callback=progress)
            finally:self.release_gpu(self.base_model)
            del positive,negative,noise,latent
            self.phase='Decodifica audio · MiniMax Music 3';emit('stage',message=self.phase)
            try:audio=self.vae.decode(samples)
            finally:self.release_gpu(self.vae.patcher)
            # VAE.decode returns [batch, samples, channels] for audio.
            audio=audio[0].detach().float().cpu()
            if audio.ndim!=2:raise RuntimeError('Dimensioni audio MiniMax non valide.')
            if audio.shape[-1]!=2 and audio.shape[0]==2:audio=audio.transpose(0,1)
            if audio.shape[-1]!=2 or not torch.isfinite(audio).all():raise RuntimeError('Audio MiniMax non valido.')
            pcm=(audio.clamp(-1,1)*32767).round().to(torch.int16).numpy().astype('<i2',copy=False)
            with wave.open(request['output'],'wb') as out:out.setparams((2,2,44100,0,'NONE','not compressed'));out.writeframes(pcm.tobytes())
        emit('done',parameters=p|{'sample_rate':44100,'channels':2,'duration':len(pcm)/44100,'engine':'minimax-music','conditioning_frames':frames})

def main():
    worker=Worker();emit('hello')
    for line in sys.stdin:
        try:
            request=json.loads(line)
            if request['op']=='load':worker.load(request)
            elif request['op']=='probe':
                worker.initialize({'backend':'cpu'})
                from comfy.ldm.minimax_music.ar import CFG_SCALE,CFG_TOP_K
                emit('probed',cfg_scale=CFG_SCALE,top_k=CFG_TOP_K)
            elif request['op']=='generate':worker.generate(request)
            elif request['op']=='unload':worker.unload()
            else:raise ValueError('Operazione musica sconosciuta.')
        except Exception as exc:traceback.print_exc();emit('error',message=str(exc))

if __name__=='__main__':main()

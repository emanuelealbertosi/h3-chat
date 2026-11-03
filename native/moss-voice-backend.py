"""Pinned local MOSS v1.5 + codec v2; staged GPU residency, native stereo."""
import os,time,gc
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

class Engine:
    sample_rate=48000
    channels=2
    precision='bf16'
    def __init__(self,config,progress=lambda **_:None):
        start=time.monotonic();self.config=dict(config);self.progress=progress
        os.environ.update(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',HF_HOME=str(ROOT/'runtime/voice/moss-cache'),HF_MODULES_CACHE=str(ROOT/'runtime/voice/moss-cache/modules'))
        import torch
        self.torch=torch;torch.set_num_threads(min(8,os.cpu_count() or 4))
        from h3_moss_audio import install
        install()
        from transformers import AutoProcessor,AutoModel
        from h3chat.moss_tts import resolve,CODEC_QUALITIES
        model=resolve(config['model_path']);codec=resolve(config['codec_path'],True)
        codec_weight,codec_compute=CODEC_QUALITIES[config.get('codec_quality','balanced')]
        if codec_compute=='fp32':
            torch.set_float32_matmul_precision('highest')
            torch.backends.cuda.matmul.allow_tf32=False
            torch.backends.cudnn.allow_tf32=False
        self.device=config['device'];self.temperature=config['temperature'];self.seed=config['seed'];self.instruction=''
        if self.device=='cuda':
            if not torch.cuda.is_available():raise RuntimeError('GPU NVIDIA non disponibile per MOSS-TTS.')
            free,_=torch.cuda.mem_get_info()
            needed=11 if codec_weight=='bf16' else 13
            if free<needed*1024**3:raise RuntimeError(f'MOSS-TTS: per questo profilo libera circa {needed} GiB di VRAM prima della prova.')
            torch.backends.cuda.enable_cudnn_sdp(False)
        else:
            import psutil
            if psutil.virtual_memory().available<24*1024**3:raise RuntimeError('MOSS-TTS CPU richiede circa 24 GiB di RAM libera.')
        progress(message='Caricamento codec MOSS v2 · pesi locali')
        # The official codec supports SDPA on CPU too; it has no 'eager' backend.
        # Official processor forwards unknown loading kwargs to ProcessorMixin,
        # where Transformers 5 rejects local_files_only. Offline environment and
        # both absolute, verified local directories enforce local loading here.
        self.processor=AutoProcessor.from_pretrained(model,codec_path=codec,trust_remote_code=True,codec_weight_dtype=codec_weight,codec_compute_dtype=codec_compute,codec_attention_implementation='sdpa')
        self.codec_precision={'codec_weight_dtype':self.processor.audio_tokenizer.codec_weight_dtype_name,'codec_compute_dtype':self.processor.audio_tokenizer.compute_dtype_name}
        progress(message='Caricamento MOSS-TTS Local v1.5 · BF16')
        self.model=AutoModel.from_pretrained(model,trust_remote_code=True,local_files_only=True,dtype=torch.bfloat16,attn_implementation='sdpa' if self.device=='cuda' else 'eager',low_cpu_mem_usage=True).eval()
        self.processor.audio_tokenizer.eval();self.load_seconds=time.monotonic()-start;self.last_timings={}
    def stage(self,model,device):
        model.to(device)
        if self.device=='cuda' and device=='cpu':gc.collect();self.torch.cuda.empty_cache()
    def generate(self,text,voice):
        torch=self.torch;start=time.monotonic();cfg=self.config
        seed=self.seed if self.seed>=0 else int.from_bytes(os.urandom(4),'big')%2147483647;torch.manual_seed(seed)
        if self.device=='cuda':torch.cuda.manual_seed_all(seed);torch.cuda.reset_peak_memory_stats()
        reference=voice.get('reference');codec=self.processor.audio_tokenizer
        with torch.inference_mode():
            self.progress(message='MOSS · codifica riferimento e testo')
            self.stage(codec,self.device)
            target=cfg.get('target_seconds',0)
            # Official duration conditioning: 12.5 audio frames per second.
            # This guides EOS; it does not trim, pad or speed-change the waveform.
            user=self.processor.build_user_message(text=text,reference=[reference] if reference else None,language=cfg['language'],instruction=self.instruction or None,tokens=max(1,round(target*12.5)) if target>0 else None)
            batch=self.processor([[user]],mode='generation');ids=batch['input_ids'].cpu();mask=batch['attention_mask'].cpu()
            self.stage(codec,'cpu');self.stage(self.model,self.device)
            self.progress(message='MOSS · generazione del parlato')
            outputs=self.model.generate(input_ids=ids.to(self.device),attention_mask=mask.to(self.device),max_new_tokens=cfg['max_new_tokens'],do_sample=True,audio_temperature=self.temperature,audio_top_p=cfg['top_p'],audio_top_k=cfg['top_k'],audio_repetition_penalty=cfg['repetition_penalty'])
            outputs=[(length,codes.cpu()) for length,codes in outputs]
            # Official output retains the opening audio token plus the prompt rows.
            if any(codes.shape[0]-1-int(length)>=cfg['max_new_tokens'] for length,codes in outputs):raise RuntimeError('MOSS ha raggiunto il limite di token audio: aumenta il limite o riduci il testo per segmento.')
            self.stage(self.model,'cpu');self.stage(codec,self.device)
            self.progress(message='MOSS · decodifica stereo 48 kHz')
            messages=self.processor.decode(outputs);parts=[audio.detach().float().cpu() for message in messages if message is not None for audio in message.audio_codes_list]
            self.stage(codec,'cpu')
        if not parts:raise RuntimeError('MOSS non ha prodotto parlato.')
        waveform=torch.cat(parts,dim=-1)
        if waveform.ndim!=2 or waveform.shape[0]!=2:raise RuntimeError('MOSS v1.5: uscita stereo attesa.')
        self.last_timings={'generation_seconds':round(time.monotonic()-start,3),'resolved_seed':seed,'staged_gpu':self.device=='cuda','sample_rate':48000,'channels':2,**self.codec_precision,'tts_dtype':str(next(self.model.parameters()).dtype)}
        if self.device=='cuda':self.last_timings['peak_gpu_bytes']=torch.cuda.max_memory_allocated()
        return waveform.T.contiguous().numpy()

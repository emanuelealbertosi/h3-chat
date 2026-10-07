# SPDX-License-Identifier: MIT
# Adapted from H3-Audio; see licenses/H3-Audio-MIT.txt.
"""H3-Audio inference adapter. No import, server or runtime from HiggsAudio-Studio."""
import os
from pathlib import Path
import sys
import time
from h3chat.voice import resolve_model
import hashlib
def stable_seed(value):
    # Preserve H3-Audio's speaker seed, including its signed 31-bit range.
    return int.from_bytes(hashlib.sha256(value.encode()).digest()[:4], "big") % (2**31)


def reference_waveform(path, rate, torch):
    """Decode at the original rate, average channels and use Higgs' sinc filter.

    A different downmix/resampler changes the codec tokens used for voice cloning.
    Keep the same preparation as H3-Audio's soundfile + _encode_reference,
    while supporting the portable PyAV runtime and compressed references.
    """
    import av
    import numpy as np
    parts=[];samples=0
    with av.open(str(path),options={'protocol_whitelist':'file'}) as inp:
        if not inp.streams.audio:raise ValueError('Il campione non contiene audio.')
        stream=inp.streams.audio[0];sr=stream.codec_context.sample_rate
        if not sr or not 8000<=sr<=192000:raise ValueError('Frequenza del campione non supportata.')
        decoder=av.AudioResampler(format='fltp')
        def collect(pieces):
            nonlocal samples
            for piece in pieces:
                if piece.sample_rate!=sr:raise ValueError('Frequenza del campione variabile.')
                samples+=piece.samples
                if samples>sr*30:raise ValueError('Il riferimento deve durare al massimo 30 secondi.')
                parts.append(piece.to_ndarray().mean(axis=0))
        for frame in inp.decode(stream):collect(decoder.resample(frame))
        collect(decoder.resample(None))
    if not parts:raise ValueError('Campione vocale vuoto.')
    signal=np.concatenate(parts)
    if not np.isfinite(signal).all():raise ValueError('Campione vocale non valido.')
    wav=torch.from_numpy(signal)[None,None,:]
    if sr!=rate:
        from h3_voice_resample import resample
        wav=resample(wav,sr,rate)
    if wav.shape[-1]<rate:wav=torch.nn.functional.pad(wav,(0,rate-wav.shape[-1]))
    return wav
DATA=Path(__file__).resolve().parents[1]/"runtime/voice"


class IncompleteAudio(RuntimeError):
    pass


class Engine:
    def __init__(self, config, progress=lambda **kw: None):
        os.environ['HF_HUB_OFFLINE'] = '1'
        os.environ['TRANSFORMERS_OFFLINE'] = '1'
        os.environ['HF_HOME'] = str(DATA / 'cache')
        os.environ['HF_MODULES_CACHE'] = str(DATA / 'cache' / 'modules')
        import torch
        from transformers import AutoTokenizer, BitsAndBytesConfig
        self.torch, self.progress = torch, progress
        torch.set_num_threads(min(8,os.cpu_count() or 4))
        model_path = resolve_model(config['model_path'])
        codec_path = resolve_model(config['codec_path'], 'codec')
        use_cuda = config['device'] == 'cuda'
        if use_cuda and not torch.cuda.is_available():
            raise RuntimeError('GPU NVIDIA non disponibile. Scegli CPU nelle Preferenze oppure controlla il driver.')
        if use_cuda:
            free, _ = torch.cuda.mem_get_info()
            required = {'bf16': 12, '8bit': 7.0, '4bit': 5.5}[config['precision']] * 1024**3
            if free < required:
                raise RuntimeError(f'Memoria GPU libera insufficiente ({free / 1024**3:.1f} GB). Libera i modelli nelle altre app o scegli una precisione più leggera.')
        else:
            import psutil
            if psutil.virtual_memory().available<20*1024**3:raise RuntimeError('Voice CPU: servono circa 20 GB di RAM libera per questo modello. Libera memoria o scegli GPU.')
        device = 'cuda' if use_cuda else 'cpu'
        dtype = torch.bfloat16 if use_cuda else torch.float32
        # Load local adapter modules without resolving HF snapshot symlinks to blobs.
        import importlib.util
        import types
        package_name = 'h3_selected_higgs_model'
        package = types.ModuleType(package_name)
        package.__path__ = [model_path]
        sys.modules[package_name] = package
        def load_module(name):
            full_name = package_name + '.' + name
            spec = importlib.util.spec_from_file_location(full_name, Path(model_path) / (name + '.py'))
            module = importlib.util.module_from_spec(spec)
            sys.modules[full_name] = module
            spec.loader.exec_module(module)
            return module
        config_module = load_module('configuration_higgs_multimodal_qwen3')
        model_module = load_module('modeling_higgs_multimodal_qwen3')
        model_config = config_module.HiggsMultimodalQwen3Config.from_pretrained(model_path, local_files_only=True)
        model_config.audio_tokenizer_id = codec_path
        kwargs = {'config': model_config, 'trust_remote_code': True, 'local_files_only': True,
                  'dtype': dtype, 'attn_implementation': 'sdpa'}
        if use_cuda and config['precision'] in {'4bit', '8bit'}:
            skip = ['audio_head', 'audio_embedding']
            quant = BitsAndBytesConfig(load_in_8bit=True, llm_int8_skip_modules=skip) if config['precision'] == '8bit' else BitsAndBytesConfig(
                load_in_4bit=True, bnb_4bit_quant_type='nf4', bnb_4bit_compute_dtype=torch.bfloat16,
                bnb_4bit_use_double_quant=True, llm_int8_skip_modules=skip)
            kwargs.update(quantization_config=quant, device_map={'': 0})
        progress(stage='loading', message='Caricamento del modello locale…')
        self.tokenizer = AutoTokenizer.from_pretrained(model_path, local_files_only=True)
        self.model = model_module.HiggsMultimodalQwen3ForConditionalGeneration.from_pretrained(model_path, **kwargs)
        # The checkpoint stores this shared matrix only once. Bind explicitly
        # after loading, including when Transformers reports the alias missing.
        self.model.tie_weights()
        if self.model._tie_audio_head and self.model.audio_head.weight is not self.model.audio_embedding.weight:raise RuntimeError('Pesi condivisi della voce non caricati correttamente.')
        if 'quantization_config' not in kwargs:
            self.model = self.model.to(device)
        self.model.eval()
        from h3_voice_codec import HiggsAudioV2TokenizerModel
        progress(stage='loading',message='Caricamento del codec vocale…')
        self.model._audio_codec=HiggsAudioV2TokenizerModel.from_pretrained(codec_path,local_files_only=True,dtype=torch.float32).to(device).eval()
        self.refs = {}
        self.sample_rate = int(self.model.config.sample_rate)
        self.temperature = float(config['temperature'])
        self.seed = config.get('seed',-1)

    def reference(self, voice):
        key = voice['reference']
        if key not in self.refs:
            wav=reference_waveform(key,self.sample_rate,self.torch).to(self.model.device,dtype=self.torch.float32)
            with self.torch.inference_mode():
                self.refs[key]=self.model.get_audio_codec().encode(wav).audio_codes.squeeze(0).transpose(0,1).long().cpu()
        return self.refs[key]

    def generate(self, text, voice, max_frames=None):
        """Observe the sampler's EOS; never return a token-limited clip as complete."""
        torch, m = self.torch, self.model
        mod = sys.modules[type(m).__module__]
        required = ['apply_delay_pattern', 'reverse_delay_pattern', '_SamplerState', '_sampler_step']
        if not all(hasattr(mod, item) for item in required):
            raise RuntimeError('Versione del modello non compatibile con questo adattatore. Consulta il README.')
        torch.manual_seed(self.seed if self.seed>=0 else stable_seed(voice['id']))
        codes = self.reference(voice)
        cap = max_frames or min(4096, max(1000, len(text) * 7))
        with torch.inference_mode():
            delayed = mod.apply_delay_pattern(codes.to(torch.long))
            ids = m._build_prompt_ids(self.tokenizer, text, num_ref_tokens=delayed.shape[0], reference_text=voice.get('transcript') or None)
            embedded = m._prefill_embeds(ids, delayed)
            output = m.model(inputs_embeds=embedded, use_cache=True)
            past = output.past_key_values
            hidden = output.last_hidden_state[:, -1, :]
            position = embedded.shape[1]
            state = mod._SamplerState(num_codebooks=m.num_codebooks)
            rows = []
            started = time.monotonic()
            for index in range(cap):
                logits = m.audio_head(hidden).to(torch.float32)[0]
                row = mod._sampler_step(logits, state, temperature=self.temperature, top_p=0.95, top_k=50)
                if state.generation_done:
                    break
                rows.append(row.cpu())
                if index % 40 == 0:
                    self.progress(stage='synthesis', frames=index, elapsed=round(time.monotonic()-started, 1))
                next_embed = m.audio_embedding(row.unsqueeze(0)).unsqueeze(1)
                output = m.model(inputs_embeds=next_embed.to(embedded.dtype), past_key_values=past,
                                 use_cache=True, cache_position=torch.tensor([position], device=m.device))
                past, hidden = output.past_key_values, output.last_hidden_state[:, -1, :]
                position += 1
            if not state.generation_done:
                raise IncompleteAudio('La frase ha raggiunto il limite del modello. Riduci la lunghezza dei segmenti nelle Preferenze e ripeti: nessun audio troncato è stato pubblicato.')
            if len(rows) < m.num_codebooks:
                raise IncompleteAudio('Il modello non ha prodotto parlato. Prova un altro campione o ripeti.')
            waveform = m._decode_codes(mod.reverse_delay_pattern(torch.stack(rows)))
        return waveform.numpy().astype('float32')

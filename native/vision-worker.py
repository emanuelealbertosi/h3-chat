# SPDX-License-Identifier: GPL-3.0-or-later
# H3-Chat headless image worker. Conditioning adapted from ComfyUI's
# nodes_ming.py, nodes_qwen.py and nodes.py (ComfyUI contributors, GPL-3.0).
# This process imports the bundled inference library only, never the server,
# custom nodes, user's workflows, or any external Python installation.
import json
import math
import logging
import os
from pathlib import Path
import sys
import traceback

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / 'runtime/vision'
dll_directory = os.add_dll_directory(str(RUNTIME / 'dlls')) if os.name=='nt' and (RUNTIME/'dlls').is_dir() else None
sys.path[:0] = [str(RUNTIME / 'packages'), str(RUNTIME / 'core')]
os.environ.update(HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1', HF_HUB_DISABLE_TELEMETRY='1',
                  HF_HOME=str(RUNTIME / 'cache'), PYTORCH_ENABLE_MPS_FALLBACK='1')
# All third party print/log output goes to the job log, never to the JSON pipe.
wire = sys.stdout
sys.stdout = sys.stderr
logging.basicConfig(level=logging.INFO, stream=sys.stderr)


def emit(event, **values):
    wire.write(json.dumps({'event': event, **values}, ensure_ascii=False) + '\n')
    wire.flush()


class Worker:
    def load(self, request):
        self.architecture = request['architecture']
        if self.architecture not in ('ming', 'qwen21'):
            raise ValueError('Architettura non supportata dal motore vision.')
        import comfy.cli_args
        args = comfy.cli_args.args
        args.cpu = request['backend'] == 'cpu'
        if request['backend'] not in ('cpu', 'cuda'):
            raise ValueError('Ming e Qwen Image 2.1 richiedono il motore CPU oppure NVIDIA CUDA.')
        args.highvram = bool(request.get('resident')) and not args.cpu
        args.disable_dynamic_vram = args.cpu or args.highvram
        args.reserve_vram = 1.0
        if not args.disable_dynamic_vram:
            import comfy_aimdo.control
            comfy_aimdo.control.init(simple_vram_headroom=1024**3, nvml_pressure=True)
        import torch
        import comfy.sd
        import comfy.sample
        import comfy.samplers
        import comfy.utils
        import comfy.model_management
        if not args.disable_dynamic_vram:
            import comfy.model_patcher
            import comfy.memory_management
            devices = comfy.model_management.get_all_torch_devices()
            if comfy_aimdo.control.init_devices((d.index,int(args.vram_headroom*1024**3)) for d in devices):
                comfy_aimdo.control.set_log_info()
                comfy.model_patcher.CoreModelPatcher = comfy.model_patcher.ModelPatcherDynamic
                comfy.memory_management.aimdo_enabled = True
        self.torch, self.comfy = torch, comfy
        torch.set_num_threads(request.get('threads', 4))
        comfy.utils.PROGRESS_BAR_ENABLED = False
        files = request['files']
        emit('stage', message='Caricamento diffusore')
        self.base_model = comfy.sd.load_diffusion_model(files['diffusion'])
        if self.base_model is None:
            raise ValueError('Diffusore non riconosciuto.')
        actual = type(self.base_model.model.model_config).__name__
        if (self.architecture == 'ming' and actual != 'MingImage') or (self.architecture == 'qwen21' and actual != 'QwenImage21'):
            raise ValueError(f'Diffusore {actual} incompatibile con il profilo {self.architecture}.')
        emit('stage', message='Caricamento encoder testo e immagini')
        clip_type = comfy.sd.CLIPType.LUMINA2 if self.architecture == 'ming' else comfy.sd.CLIPType.QWEN_IMAGE
        self.base_clip = comfy.sd.load_clip([files['llm']], clip_type=clip_type)
        self.vae = comfy.sd.VAE(sd=comfy.utils.load_torch_file(files['vae'], safe_load=True))
        # Validate the VAE channels, so choosing an old Qwen VAE fails before inference.
        expected = 16 if self.architecture == 'ming' else 64
        if self.vae.latent_channels != expected:
            raise ValueError(f'VAE incompatibile: servono {expected} canali per {self.architecture}.')
        emit('ready')

    def images(self, paths):
        import numpy as np
        from PIL import Image, ImageOps
        result = []
        for path in paths:
            with Image.open(path) as source:
                image = ImageOps.exif_transpose(source)
                if max(image.size) > 8192:
                    raise ValueError('Riferimento troppo grande (massimo 8192 px).')
                image = image.convert('RGBA' if 'A' in image.getbands() else 'RGB')
                result.append(self.torch.from_numpy(np.asarray(image).copy().astype(np.float32) / 255)[None])
        return result

    @staticmethod
    def references(conditioning, latents):
        return [[value, dict(info, reference_latents=list(info.get('reference_latents', []))+latents)] for value, info in conditioning]

    def encode(self, clip, request, images):
        torch, comfy = self.torch, self.comfy
        width, height = request['width'], request['height']
        prompt, negative = request['prompt'], request.get('negative_prompt', '')
        if self.architecture == 'ming':
            # Match the source workflow: reference canvas is resized to the chosen
            # area, preserving its aspect; subsequent references share that size.
            if images:
                ratio = images[0].shape[2] / images[0].shape[1]
                width = max(64, round(math.sqrt(width * height * ratio) / 64) * 64)
                height = max(64, round(width / ratio / 64) * 64)
                images = [comfy.utils.common_upscale(x.movedim(-1, 1), width, height, 'bilinear', 'disabled').movedim(1, -1) for x in images]
            tokens = clip.tokenize(prompt, images=[x[:, :, :, :3] for x in images])
            positive = clip.encode_from_tokens_scheduled(tokens)
            if images:
                positive = self.references(positive, [self.vae.encode(x) for x in images])
            if negative:
                neg = clip.encode_from_tokens_scheduled(clip.tokenize(negative))
                if images:
                    neg = self.references(neg, positive[0][1]['reference_latents'])
            else:
                neg = []
                for value, info in positive:
                    data = info.copy()
                    for key in ('pooled_output', 'conditioning_lyrics', 'conditioning_scale', 'direct_context'):
                        if data.get(key) is not None:
                            data[key] = torch.zeros_like(data[key])
                    neg.append([torch.zeros_like(value), data])
            latent = torch.zeros([1, 16, 1, height // 8, width // 8], device=comfy.model_management.intermediate_device())
        else:
            refs, vision = [], []
            area = width * height
            for image in images:
                ratio = image.shape[2] / image.shape[1]
                w = max(32, round(math.sqrt(area * ratio) / 32) * 32)
                h = max(32, round(math.sqrt(area / ratio) / 32) * 32)
                resized = comfy.utils.common_upscale(image.movedim(-1, 1), w, h, 'lanczos', 'disabled').movedim(1, -1)
                if not vision:
                    width, height = w, h
                rgb = resized[:, :, :, :3]
                if resized.shape[-1] > 3:
                    rgb = rgb * resized[:, :, :, 3:] + 1 - resized[:, :, :, 3:]
                vision.append(rgb)
                refs.append(self.vae.encode(resized))
            def condition(text):
                return clip.encode_from_tokens_scheduled(clip.tokenize(text, images=vision, keep_vision=not refs, prevent_empty_text=True))
            positive = condition(prompt)
            neg = [[torch.zeros_like(value), info.copy()] for value, info in positive] if request.get('cfg')==1 else condition(negative)
            if refs:
                positive, neg = self.references(positive, refs), self.references(neg, refs)
            latent = torch.zeros([1, 64, height // 16, width // 16], device=comfy.model_management.intermediate_device())
        return positive, neg, latent

    def generate(self, request):
        from PIL import Image
        import numpy as np
        torch, comfy = self.torch, self.comfy
        model, clip = self.base_model, self.base_clip
        # Each request starts from the base patchers: a removed LoRA cannot leak
        # into the following image or alter the on-disk model.
        for lora in request.get('loras', []):
            if lora['weight']:
                weights, metadata = comfy.utils.load_torch_file(lora['path'], safe_load=True, return_metadata=True)
                previous = sum(len(v) for v in model.patches.values()) + sum(len(v) for v in clip.patcher.patches.values())
                model, clip = comfy.sd.load_lora_for_models(model, clip, weights, lora['weight'], lora['weight'], metadata)
                applied = sum(len(v) for v in model.patches.values()) + sum(len(v) for v in clip.patcher.patches.values())
                if applied <= previous:raise ValueError('LoRA senza tensori compatibili con il modello: '+Path(lora['path']).name)
        if self.architecture == 'qwen21':
            model = model.clone()
            model.model_options['transformer_options']['qwen_image21_cache'] = {
                'device': request.get('cache_device', 'auto'), 'dtype': request.get('cache_dtype', 'default')}
        sampler = request.get('sampler', 'euler')
        scheduler = request.get('scheduler', 'simple')
        if sampler not in comfy.samplers.KSampler.SAMPLERS or scheduler not in comfy.samplers.KSampler.SCHEDULERS:
            raise ValueError('Sampler o scheduler non supportato da questo modello.')
        images = self.images(request.get('references', []))
        if len(images) > 4:
            raise ValueError('Sono supportati fino a quattro riferimenti.')
        with torch.inference_mode():
            emit('stage', message='Lettura delle istruzioni e dei riferimenti')
            positive, negative, latent = self.encode(clip, request, images)
            noise = comfy.sample.prepare_noise(latent, request['seed'])
            emit('stage', message='Generazione immagine')
            samples = comfy.sample.sample(model, noise, request['steps'], request['cfg'], sampler, scheduler,
                positive, negative, latent, denoise=1.0, disable_pbar=True, seed=request['seed'],
                callback=lambda step, x0, x, total: emit('progress', step=step+1, steps=total))
            emit('stage', message='Decodifica immagine')
            pixels = self.vae.decode(samples)
            if pixels.ndim == 5:
                pixels = pixels.reshape(-1, *pixels.shape[-3:])
            array = (pixels[0].clamp(0, 1).cpu().numpy() * 255).round().astype(np.uint8)
            Image.fromarray(array).save(request['output'], format='PNG')
        emit('done', parameters={'width':int(array.shape[1]), 'height':int(array.shape[0]),
             'steps':request['steps'], 'cfg':request['cfg'], 'sampler':sampler, 'scheduler':scheduler,
             'seed':request['seed'], 'strength':1.0, 'engine':'vision', 'reference_count':len(images)})


def main():
    emit('hello')
    worker = Worker()
    for line in sys.stdin:
        try:
            request = json.loads(line)
            if request['op'] == 'load':
                worker.load(request)
            elif request['op'] == 'generate':
                worker.generate(request)
            else:
                raise ValueError('Operazione non supportata.')
        except Exception as exc:
            traceback.print_exc(file=sys.stderr)
            emit('error', message=str(exc))
            return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

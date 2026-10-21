"""Krea2 uses its own text encoder and Wan image latent, without real model loads."""
import ast
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

from h3chat.vision_runtime import validate_options

ROOT = Path(__file__).resolve().parents[1]


def worker_class():
    tree = ast.parse((ROOT / 'native/vision-worker.py').read_text(encoding='utf-8'))
    cls = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == 'Worker')
    namespace = {'emit': Mock()}
    exec(compile(ast.Module(body=[cls], type_ignores=[]), '<vision-worker>', 'exec'), namespace)
    return namespace['Worker']


class Krea2WorkerTests(unittest.TestCase):
    def loader(self, actual='Krea2', vae_channels=16):
        worker = worker_class()()
        worker.initialize = Mock()
        config = type(actual, (), {})()
        model = SimpleNamespace(model=SimpleNamespace(model_config=config))
        worker.torch = SimpleNamespace(set_num_threads=Mock())
        worker.comfy = SimpleNamespace(
            sd=SimpleNamespace(
                CLIPType=SimpleNamespace(LUMINA2='lumina', QWEN_IMAGE='qwen-image', KREA2='krea2'),
                load_diffusion_model=Mock(return_value=model),
                load_clip=Mock(return_value='krea2-clip'),
                VAE=Mock(return_value=SimpleNamespace(latent_channels=vae_channels))),
            utils=SimpleNamespace(load_torch_file=Mock(return_value='vae-weights')))
        return worker

    def test_loads_krea2_specific_encoder_and_original_files(self):
        worker = self.loader()
        files = {'diffusion':'redcraft.safetensors', 'llm':'qwen3vl_4b.safetensors', 'vae':'qwen_image_vae.safetensors'}
        worker.load({'architecture':'krea2', 'files':files, 'backend':'cpu'})
        worker.comfy.sd.load_diffusion_model.assert_called_once_with(files['diffusion'])
        worker.comfy.sd.load_clip.assert_called_once_with([files['llm']], clip_type='krea2')
        worker.comfy.utils.load_torch_file.assert_called_once_with(files['vae'], safe_load=True)

    def test_rejects_flux1_krea_and_wrong_vae_before_inference(self):
        request = {'architecture':'krea2', 'files':{'diffusion':'diff', 'llm':'text', 'vae':'vae'}, 'backend':'cpu'}
        worker = self.loader(actual='Flux')
        with self.assertRaisesRegex(ValueError, 'Diffusore Flux incompatibile'):
            worker.load(request)
        worker.comfy.sd.load_clip.assert_not_called()
        worker = self.loader(vae_channels=64)
        with self.assertRaisesRegex(ValueError, '16 canali'):
            worker.load(request)

    def encoder(self):
        worker = worker_class()()
        worker.architecture = 'krea2'
        worker.torch = SimpleNamespace(zeros=Mock(return_value='latent'), zeros_like=lambda x:('zero', x))
        worker.comfy = SimpleNamespace(model_management=SimpleNamespace(intermediate_device=lambda:'cpu'))
        clip = SimpleNamespace(tokenize=Mock(side_effect=lambda text, **kw:text),
                               encode_from_tokens_scheduled=Mock(side_effect=lambda text:[[text, {'pooled_output':'pool', 'other':42}]]))
        return worker, clip

    def test_matches_turbo_zero_conditioning_and_single_frame_wan_latent(self):
        worker, clip = self.encoder()
        positive, negative, latent = worker.encode(clip, {'prompt':'city at dawn', 'cfg':1, 'width':1152, 'height':768}, [])
        self.assertEqual(positive[0][0], 'city at dawn')
        self.assertEqual(positive[0][1]['pooled_output'], 'pool')
        self.assertEqual(negative[0], [('zero', 'city at dawn'), {'pooled_output':('zero', 'pool'), 'other':42}])
        self.assertEqual(latent, 'latent')
        worker.torch.zeros.assert_called_once_with([1,16,1,96,144], device='cpu')
        clip.tokenize.assert_called_once_with('city at dawn')

    def test_negative_prompt_is_encoded_when_cfg_is_changed(self):
        worker, clip = self.encoder()
        _, negative, _ = worker.encode(clip, {'prompt':'city', 'negative_prompt':'blur', 'cfg':2, 'width':1024, 'height':1024}, [])
        self.assertEqual(negative[0][0], 'blur')
        self.assertEqual(clip.tokenize.call_count, 2)

    def test_reference_rejection_precedes_any_encoder_or_image_io(self):
        worker, clip = self.encoder()
        with self.assertRaisesRegex(ValueError, 'creare immagini da testo'):
            worker.encode(clip, {'prompt':'edit', 'width':1024, 'height':1024}, ['reference'])
        clip.tokenize.assert_not_called()
        # Worker guards against a handcrafted request even if the API has
        # already checked the profile's max_refs=0.
        worker.base_model, worker.base_clip = Mock(), clip
        worker.images = Mock()
        with self.assertRaisesRegex(ValueError, 'creare immagini da testo'):
            worker.generate({'references':['missing-file.png']})
        worker.images.assert_not_called()

    def test_krea2_accepts_normal_scheduler_but_never_qwen_turbo_sigmas(self):
        model = {'engine':'vision', 'architecture':'krea2'}
        settings = {'sampler':'euler', 'scheduler':'simple', 'strength':.4}
        validate_options(model, settings)
        self.assertEqual(settings['strength'], 1)
        with self.assertRaisesRegex(ValueError, 'solo per Qwen'):
            validate_options(model, settings | {'scheduler':'qwen21_turbo'})


if __name__ == '__main__':
    unittest.main()

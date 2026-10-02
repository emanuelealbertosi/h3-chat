"""Check video component lifetimes without loading CUDA or user model weights."""
import ast
import contextlib
from pathlib import Path
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]


class VideoMemoryOrderTests(unittest.TestCase):
    def exercise(self, offload):
        tree = ast.parse((ROOT/'native/video-worker.py').read_text(encoding='utf-8'))
        definition = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'Worker')
        events = []
        namespace = {'emit': lambda event, **values: events.append((event, values)), 'write_video': Mock(), 'read_safetensors':Mock(return_value=({},{}))}
        exec(compile(ast.Module(body=[definition], type_ignores=[]), '<video-worker>', 'exec'), namespace)
        worker = namespace['Worker']()
        torch = SimpleNamespace(cuda=SimpleNamespace(is_available=lambda: True),
            set_num_threads=Mock(), no_grad=contextlib.nullcontext)
        comfy = ModuleType('comfy')
        comfy.cli_args = ModuleType('comfy.cli_args');comfy.cli_args.args = SimpleNamespace()
        comfy.sd = ModuleType('comfy.sd');comfy.sd.VAE = Mock()
        decoded = [object()] * 24
        comfy.utils = ModuleType('comfy.utils');comfy.utils.load_torch_file = Mock(return_value={})
        comfy.utils._TYPES = {}
        comfy.sample = ModuleType('comfy.sample');comfy.sample.prepare_noise = Mock(return_value=object())
        comfy.model_management = SimpleNamespace(cleanup_models=Mock(), soft_empty_cache=Mock(), load_models_gpu=Mock())
        h3 = SimpleNamespace(MiniMaxH3SigmaShift=SimpleNamespace(execute=lambda model, *args: (model,)))
        extras = ModuleType('comfy_extras');extras.nodes_minimax_h3 = h3
        modules = {'torch': torch, 'comfy': comfy, 'comfy_extras': extras,
            **{'comfy.'+name: getattr(comfy, name) for name in ('cli_args', 'sd', 'utils', 'sample')}}
        lifetime = []

        def load_diffuser():
            if offload:
                self.assertIsNone(worker.clip)
                self.assertIsNone(worker.vae)
                self.assertIsNone(worker.audio_vae)
            worker.model = object();lifetime.append('diffuser')

        def load_conditioners():
            if offload:self.assertIsNone(worker.model)
            worker.clip, worker.vae, worker.audio_vae = object(), object(), object()
            lifetime.append('conditioners')

        def condition(request, images):
            self.assertIsNotNone(worker.clip)
            if offload:self.assertIsNone(worker.model)
            lifetime.append('condition')
            return [], {'samples': object()}, {'waveform': object(), 'sample_rate': 32000}, 39

        def sample(model, *args, **kwargs):
            self.assertIsNotNone(model)
            if offload:self.assertIsNone(worker.clip)
            lifetime.append('sample')
            return SimpleNamespace(unbind=lambda: (object(), object()))

        # The decoder must be sized like the real tensor and still carry ndim.
        class Frames(list):
            ndim = 4
            def __getitem__(self, key):
                return self if isinstance(key,tuple) else super().__getitem__(key)
        def decode(samples):
            if offload:self.assertIsNone(worker.model)
            return Frames(decoded)
        comfy.sd.VAE.return_value.decode.side_effect = decode
        comfy.sample.sample = sample
        worker.load_diffuser, worker.load_conditioners, worker.condition = load_diffuser, load_conditioners, condition
        worker.images = Mock(return_value=[])
        worker.configure_attention = Mock(return_value='pytorch');worker.attention_chunks=1
        opts = {'frames':24, 'shift_video':12, 'shift_audio':3, 'seed':1, 'aspect':'16:9','megapixels':.2,
            'steps':2, 'cfg':1, 'sampler':'res_multistep', 'scheduler':'simple'}
        request = {'options':opts, 'plan':{'audios':[]}, 'output':'unused.mp4','images':[]}
        with patch.dict('sys.modules', modules):
            worker.load({'files':{'vae':'unused.safetensors'}, 'offload':offload})
            if offload:self.assertIsNone(worker.model)
            else:
                # A resident decoder is not released between stages.
                worker.vae = comfy.sd.VAE.return_value
            worker.generate(request)
            if offload:
                self.assertIsNone(worker.model)
                # A reused worker must use the same ordering on the next job.
                worker.generate(request)
        self.assertEqual([event for event, _ in events].count('done'), 2 if offload else 1)
        self.assertEqual(lifetime,
            ['conditioners','condition','diffuser','sample'] * 2 if offload
            else ['diffuser','conditioners','condition','sample'])
        namespace['write_video'].assert_called()
        if offload:
            self.assertEqual(comfy.sd.VAE.call_count, 2)
            self.assertEqual(comfy.model_management.soft_empty_cache.call_count, 4)

    def test_on_demand_weights_do_not_overlap_before_or_after_sampling(self):
        self.exercise(True)

    def test_resident_keeps_components_and_does_not_reload_decoder(self):
        self.exercise(False)


if __name__ == '__main__':unittest.main()

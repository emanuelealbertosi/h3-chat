"""Exercise the worker's real request contract without loading GPU libraries."""
import ast
import contextlib
import json
import tempfile
import time
import types
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from PIL import Image
from h3chat import fibo2
from h3chat.hardware import assess_model
from h3chat.store import DEFAULTS


class WorkerTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.events=[]
        source=Path(__file__).resolve().parents[1]/'native/fibo2-worker.py'
        tree=ast.parse(source.read_text())
        worker=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='Worker')
        scope={'Path':Path,'time':time,'prompt':fibo2.prompt,'negative':fibo2.negative,
               'pipeline_root':lambda _:self.root,'validate_options':fibo2.validate_options,
               'emit':lambda event,**values:self.events.append({'event':event,**values})}
        exec(compile(ast.Module(body=[worker],type_ignores=[]),str(source),'exec'),scope)
        self.worker=scope['Worker']()
        self.torch=Mock(bfloat16='bf16',float32='fp32')
        self.torch.inference_mode=contextlib.nullcontext
        self.torch.cuda.max_memory_allocated.return_value=2*1024**3
        self.pipe=Mock()
        self.worker.torch=self.torch;self.worker.pipe=self.pipe
        self.worker.fonts=['font.otf'];self.worker.backend='cuda'
        self.worker.offload='sequential'

    def request(self,**changes):
        return dict(prompt='A red bicycle',steps=50,cfg=5,seed=42,sampler='auto',scheduler='auto',
                    width=1424,height=800,output=str(self.root/'image.png'),references=[],**changes)

    def test_load_is_offline_and_offloads_leaf_modules_instead_of_the_whole_model(self):
        factory=Mock();factory.from_pretrained.return_value=self.pipe
        with patch.dict('sys.modules',{'torch':self.torch,'diffusers':types.SimpleNamespace(BriaFibo2Pipeline=factory)}):
            self.worker.load({'files':{},'backend':'cuda','threads':4})
        self.assertEqual(factory.from_pretrained.call_args.kwargs,
                         {'torch_dtype':'bf16','local_files_only':True,'low_cpu_mem_usage':True})
        self.pipe.enable_sequential_cpu_offload.assert_called_once()
        self.pipe.enable_model_cpu_offload.assert_not_called()
        self.pipe.vae.enable_tiling.assert_called_once()
        self.assertEqual(self.events[-1]['event'],'ready')

    def test_generation_preserves_controls_output_size_seed_and_callback(self):
        def render(**kwargs):
            self.assertEqual((kwargs['width'],kwargs['height'],kwargs['num_inference_steps'],kwargs['guidance_scale']),
                             (1424,800,50,5))
            values={'latents':'unchanged'}
            self.assertIs(kwargs['callback_on_step_end'](self.pipe,0,1,values),values)
            return types.SimpleNamespace(images=[Image.new('RGB',(1424,800))])
        self.pipe.side_effect=render
        self.worker.generate(self.request())
        self.torch.Generator.assert_called_once_with(device='cpu')
        self.torch.Generator.return_value.manual_seed.assert_called_once_with(42)
        self.assertEqual(Image.open(self.root/'image.png').size,(1424,800))
        self.assertEqual(self.events[-1]['parameters']['sampler'],'euler')
        self.assertEqual(self.events[-1]['parameters']['peak_allocated_gib'],2)
        self.assertEqual(self.events[-1]['parameters']['seed'],42)

    def test_group_offload_keeps_vae_on_gpu_and_uses_no_pinned_prefetch(self):
        factory=Mock();factory.from_pretrained.return_value=self.pipe;group=Mock()
        with patch.dict('sys.modules',{'torch':self.torch,'diffusers':types.SimpleNamespace(BriaFibo2Pipeline=factory),
                'diffusers.hooks':types.SimpleNamespace(apply_group_offloading=group)}):
            self.worker.load({'files':{},'backend':'cuda','fibo_offload':'group'})
        self.pipe.enable_sequential_cpu_offload.assert_not_called()
        self.pipe.transformer.enable_group_offload.assert_called_once()
        self.assertEqual(self.pipe.transformer.enable_group_offload.call_args.kwargs['num_blocks_per_group'],16)
        self.assertFalse(group.call_args.kwargs['use_stream']);self.pipe.vae.to.assert_called_once_with('cuda')
        self.assertEqual(self.worker.offload,'group')

    def test_full_cuda_leaves_fallback_to_driver_without_offload_hooks(self):
        factory=Mock();factory.from_pretrained.return_value=self.pipe
        with patch.dict('sys.modules',{'torch':self.torch,'diffusers':types.SimpleNamespace(BriaFibo2Pipeline=factory)}):
            self.worker.load({'files':{},'backend':'cuda','fibo_offload':'full'})
        self.pipe.to.assert_called_once_with('cuda')
        self.pipe.enable_sequential_cpu_offload.assert_not_called()
        self.pipe.transformer.enable_group_offload.assert_not_called()
        self.assertEqual(self.worker.offload,'full')

    def test_edit_uses_references_and_actual_output_dimensions_without_forcing_square(self):
        ref=self.root/'reference.png';Image.new('RGB',(640,960)).save(ref)
        self.pipe.return_value=types.SimpleNamespace(images=[Image.new('RGB',(832,1248))])
        request=self.request();request.update(references=[str(ref)],preserve_reference_aspect=True)
        self.worker.generate(request)
        arguments=self.pipe.call_args.kwargs
        self.assertEqual(arguments['image'].size,(640,960))
        self.assertNotIn('width',arguments);self.assertNotIn('height',arguments)
        self.assertEqual(json.loads(arguments['negative_prompt']),json.loads(fibo2.NEGATIVE_EDIT))
        self.assertEqual((self.events[-1]['parameters']['width'],self.events[-1]['parameters']['height']),(832,1248))
        request.update(preserve_reference_aspect=False)
        self.worker.generate(request)
        self.assertEqual(self.pipe.call_args.kwargs['width'],1424)

    def test_unsupported_loras_and_fifth_reference_fail_before_inference(self):
        request=self.request();request.update(loras=[{'path':'adapter.safetensors'}])
        with self.assertRaisesRegex(ValueError,'LoRA'):self.worker.generate(request)
        request=self.request();request.update(references=['absent.png']*5)
        with self.assertRaisesRegex(ValueError,'massimo 4'):self.worker.generate(request)
        self.pipe.assert_not_called()

    def test_memory_estimate_counts_host_weights_and_rejects_vulkan(self):
        model={'id':'fibo','name':'FIBO','architecture':'fibo2','engine':'fibo2','capabilities':['create','edit'],
               'files':[{'role':'diffusion','size':24*1024**3}]}
        hw={'ram':{'total_mb':40960,'free_mb':32768},'gpu':[{'name':'GPU','vendor':'NVIDIA','total_mb':16384,'free_mb':14000}]}
        cuda=assess_model(model,DEFAULTS|{'backend':'cuda'},hw)
        cpu=assess_model(model,DEFAULTS|{'profile':'cpu'},hw)
        self.assertLess(cuda['vram_gb'],10);self.assertGreater(cuda['ram_gb'],24)
        self.assertGreater(cpu['ram_gb'],cuda['ram_gb']);self.assertEqual(cpu['status'],'oom')
        full=assess_model(model,DEFAULTS|{'backend':'cuda','image_overrides':{'fibo':{'fibo_offload':'full'}}},hw)
        self.assertGreater(full['vram_gb'],24)
        self.assertEqual(assess_model(model,DEFAULTS|{'backend':'vulkan'},hw)['title'],'Backend incompatibile')


if __name__=='__main__':unittest.main()

"""GPU phase ownership without importing Torch or running real model weights."""
import ast
from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace,ModuleType
import sys
import threading
import time
import unittest
from unittest.mock import Mock,patch
from h3chat.residency import Session

ROOT=Path(__file__).resolve().parents[1]


def worker_class():
    tree=ast.parse((ROOT/'native/vision-worker.py').read_text(encoding='utf-8'))
    worker=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='Worker')
    namespace={'emit':Mock(),'time':time}
    exec(compile(ast.Module(body=[worker],type_ignores=[]),'<vision-worker>', 'exec'),namespace)
    return namespace['Worker']


class Pixels:
    ndim=4
    shape=(1,512,512,3)
    def __getitem__(self,index):return self
    def clamp(self,*args):return self
    def cpu(self):return self
    def numpy(self):return self
    def __mul__(self,value):return self
    def round(self):return self
    def astype(self,dtype):return self


class MemoryPhaseTests(unittest.TestCase):
    def test_cuda_initialization_keeps_gpu_computation_without_highvram_offload(self):
        for backend in ('cuda','cpu'):
            with self.subTest(backend=backend):
                comfy=ModuleType('comfy');comfy.__path__=[]
                modules={'comfy':comfy,'torch':ModuleType('torch')}
                for name in ('cli_args','sd','sample','samplers','utils','model_management'):
                    module=ModuleType('comfy.'+name);setattr(comfy,name,module);modules[module.__name__]=module
                comfy.cli_args.args=SimpleNamespace(highvram=True,gpu_only=True,lowvram=True,novram=True)
                comfy.model_management.load_models_gpu=Mock()
                instance=worker_class()()
                with patch.dict(sys.modules,modules):instance.initialize({'backend':backend})
                args=comfy.cli_args.args
                self.assertFalse(args.highvram);self.assertFalse(args.gpu_only)
                self.assertFalse(args.lowvram);self.assertFalse(args.novram)
                self.assertTrue(args.disable_dynamic_vram)
                self.assertEqual(args.cpu,backend=='cpu');self.assertEqual(instance.backend,backend)
                self.assertEqual(args.reserve_vram,1.0)

    def fixture(self,backend='cuda',failure=None):
        instance=worker_class()();events=[]
        instance.backend=backend;instance.architecture='ming';instance.phase=''
        instance.base_model=SimpleNamespace(name='diffusor')
        instance.base_clip=SimpleNamespace(patcher=SimpleNamespace(name='encoder'))
        def encode(*args):
            events.append('encode')
            if failure=='encode':raise RuntimeError('synthetic encode failure')
            return 'positive','negative','latent'
        def sample(*args,**kwargs):
            events.append('sample')
            if failure=='sample':raise RuntimeError('synthetic sample failure')
            kwargs['callback'](0,None,None,25)
            return 'samples'
        def decode(*args):
            events.append('decode')
            if failure=='decode':raise RuntimeError('synthetic decode failure')
            return Pixels()
        instance.vae=SimpleNamespace(patcher=SimpleNamespace(name='vae'),decode=decode)
        instance.encode=encode;instance.images=lambda paths:[]
        manager=SimpleNamespace(unload_model_and_clones=lambda p:events.append('release '+p.name),
                                soft_empty_cache=lambda **kw:events.append('empty cache'))
        instance.comfy=SimpleNamespace(model_management=manager,
            sample=SimpleNamespace(prepare_noise=lambda *args:'noise',sample=sample),
            samplers=SimpleNamespace(KSampler=SimpleNamespace(SAMPLERS=['euler'],SCHEDULERS=['simple'])))
        instance.torch=SimpleNamespace(inference_mode=nullcontext)
        return instance,events

    def generate(self,instance):
        pil=ModuleType('PIL');pil.Image=SimpleNamespace(fromarray=lambda array:SimpleNamespace(save=lambda *args,**kw:None))
        numpy=ModuleType('numpy');numpy.uint8='uint8'
        with patch.dict(sys.modules,{'PIL':pil,'numpy':numpy}):
            instance.generate({'width':512,'height':512,'seed':42,'steps':25,'cfg':1,'output':'synthetic.png'})

    def test_each_image_releases_encoder_before_sample_and_diffusor_before_decode(self):
        instance,events=self.fixture()
        for _ in range(4):self.generate(instance)
        per_image=['encode','release encoder','empty cache','release vae','empty cache',
                   'sample','release diffusor','empty cache','decode','release vae','empty cache','empty cache']
        self.assertEqual(events,per_image*4)
        # Loaded host weight objects remain available across the whole batch.
        self.assertEqual(instance.base_model.name,'diffusor')
        self.assertEqual(instance.base_clip.patcher.name,'encoder')

    def test_errors_release_the_failed_phase_and_do_not_proceed_to_the_next(self):
        for failure,component,next_phase in (('encode','encoder','sample'),('sample','diffusor','decode'),('decode','vae',None)):
            with self.subTest(failure=failure):
                instance,events=self.fixture(failure=failure)
                with self.assertRaisesRegex(RuntimeError,'synthetic '+failure):self.generate(instance)
                self.assertIn('release '+component,events)
                if next_phase:self.assertNotIn(next_phase,events)

    def test_cpu_mode_does_not_invoke_gpu_offload_or_cuda_allocator(self):
        instance,events=self.fixture(backend='cpu');self.generate(instance)
        self.assertEqual(events,['encode','sample','decode'])

    def test_image_progress_displays_measured_step_time(self):
        session=Session((), 'image', {}, {}, {}, Path('unused.log'))
        session.events.put({'event':'progress','phase':'sample','step':2,'steps':25,'step_seconds':1.42})
        session.events.put({'event':'done'})
        stage=Mock();session.wait('done',threading.Event(),1,stage)
        stage.assert_called_once_with('Generazione immagine · 2/25 passi · ultimo passo 1.4 s')


if __name__=='__main__':unittest.main()

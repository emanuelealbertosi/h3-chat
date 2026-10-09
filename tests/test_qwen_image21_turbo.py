import ast
import contextlib
import json
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

from h3chat.external_models import build_model,validate_config
from h3chat.image_options import options
from h3chat.store import DEFAULTS
from h3chat.qwen_image21 import TURBO_SCHEDULER,TURBO_SIGMAS,validate_schedule
from test_external_models import safetensors

ROOT=Path(__file__).resolve().parents[1]


class TurboTests(unittest.TestCase):
    def test_profile_presets_reuse_original_components_and_leave_base_unchanged(self):
        with tempfile.TemporaryDirectory() as folder:
            files={role:str(safetensors(Path(folder)/f'{role}.safetensors')) for role in ('diffusion','llm','vae')}
            turbo=build_model(validate_config({'profile':'qwen21-turbo','name':'Turbo locale','files':files}))
            base=build_model(validate_config({'profile':'qwen21','files':files}))
            self.assertEqual({f['role']:f['path'] for f in turbo['files']},files)
            self.assertEqual((turbo['engine'],turbo['architecture'],turbo['capabilities']),('vision','qwen21',['create','edit']))
            value=options(turbo,DEFAULTS)
            self.assertEqual((value['steps'],value['cfg'],value['sampler'],value['scheduler']),(8,1,'euler',TURBO_SCHEDULER))
            self.assertEqual(options(turbo,DEFAULTS|{'image_overrides':{turbo['id']:{'scheduler':'auto'}}})['scheduler'],TURBO_SCHEDULER)
            self.assertEqual(options(base,DEFAULTS)['steps'],25)
            experimental=DEFAULTS|{'image_overrides':{turbo['id']:{'steps':12,'cfg':2,'scheduler':'simple'}}}
            self.assertEqual(options(turbo,experimental)['steps'],12)
            self.assertEqual(options(base,experimental)['steps'],25)
            with self.assertRaisesRegex(ValueError,'8 passi'):
                options(turbo,DEFAULTS|{'image_overrides':{turbo['id']:{'steps':25}}})

    def test_fixed_schedule_rejects_wrong_family_or_step_count(self):
        self.assertEqual(len(TURBO_SIGMAS)-1,8)
        self.assertEqual((TURBO_SIGMAS[0],TURBO_SIGMAS[-1]),(1,0))
        self.assertTrue(all(a>b for a,b in zip(TURBO_SIGMAS,TURBO_SIGMAS[1:])))
        for arch,value in [('ming',{'steps':8,'sampler':'euler'}),('qwen21',{'steps':25,'sampler':'euler'}),('qwen21',{'steps':8,'sampler':'heun'})]:
            with self.subTest(arch=arch,value=value),self.assertRaises(ValueError):
                validate_schedule(arch,value|{'scheduler':TURBO_SCHEDULER})

    def test_native_generation_passes_exact_sigmas_without_shifting_named_scheduler(self):
        import numpy as np
        tree=ast.parse((ROOT/'native/vision-worker.py').read_text(encoding='utf-8'))
        cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='Worker')
        cls.body=[n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='generate']
        events=[];namespace={'Path':Path,'time':time,'TURBO_SIGMAS':TURBO_SIGMAS,'TURBO_SCHEDULER':TURBO_SCHEDULER,'validate_schedule':validate_schedule,'emit':lambda event,**kw:events.append((event,kw))}
        exec(compile(ast.Module(body=[cls],type_ignores=[]),'<native worker>', 'exec'),namespace)
        for scheduler,steps in ((TURBO_SCHEDULER,8),('simple',25)):
            with self.subTest(scheduler=scheduler),tempfile.TemporaryDirectory() as folder:
                worker=namespace['Worker']();worker.architecture='qwen21';worker.backend='cpu'
                worker.torch=SimpleNamespace(inference_mode=contextlib.nullcontext,tensor=lambda value,**kwargs:list(value),float32='float32')
                model=Mock();model.model_options={'transformer_options':{}};model.clone.return_value=model
                worker.base_model=model;worker.base_clip=Mock();worker.vae=Mock();pixels=Mock();pixels.ndim=4
                pixels.__getitem__=Mock(return_value=Mock());pixels.__getitem__.return_value.clamp.return_value.cpu.return_value.numpy.return_value=np.zeros((8,8,3))
                worker.vae.decode.return_value=pixels;sample=Mock(return_value='samples')
                worker.comfy=SimpleNamespace(samplers=SimpleNamespace(KSampler=SimpleNamespace(SAMPLERS=['euler'],SCHEDULERS=['simple'])),sample=SimpleNamespace(sample=sample,prepare_noise=Mock(return_value='noise')))
                worker.images=Mock(return_value=[]);worker.encode=Mock(return_value=('positive','negative','latent'));worker.release_gpu=Mock()
                worker.generate({'scheduler':scheduler,'sampler':'euler','steps':steps,'cfg':1,'seed':42,'output':str(Path(folder)/'image.png')})
                self.assertEqual(sample.call_args.args[5],'simple')
                if scheduler==TURBO_SCHEDULER:self.assertEqual(sample.call_args.kwargs['sigmas'],list(TURBO_SIGMAS))
                else:self.assertNotIn('sigmas',sample.call_args.kwargs)
                self.assertTrue((Path(folder)/'image.png').is_file())
                self.assertEqual(events[-1][1]['parameters']['steps'],steps)

    def test_catalog_contains_pinned_verified_components_with_correct_preset(self):
        models=json.loads((ROOT/'catalog.json').read_text(encoding='utf-8'))
        model=next(m for m in models if m['id']=='qwen-image21-turbo-int8')
        self.assertEqual((model['steps'],model['cfg'],model['scheduler']),(8,1,TURBO_SCHEDULER))
        self.assertEqual({f['role'] for f in model['files']},{'diffusion','llm','vae'})
        self.assertEqual(sum(f['size'] for f in model['files']),model['size'])
        for file in model['files']:
            self.assertEqual(file['repo'],'Comfy-Org/Qwen-Image-2.1')
            self.assertRegex(file['sha256'],r'^[a-f0-9]{64}$')
            self.assertRegex(file['revision'],r'^[a-f0-9]{40}$')
            self.assertIn('/resolve/'+file['revision']+'/',file['url'])

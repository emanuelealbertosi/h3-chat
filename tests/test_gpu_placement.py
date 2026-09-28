import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch
from h3chat.engine import Engine
from h3chat.hardware import assess_model
from h3chat.residency import Session
from h3chat.store import DEFAULTS

class PlacementTests(unittest.TestCase):
    def test_image_components_use_selected_device_in_both_lifetime_policies(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'native').mkdir();(root/'native/h3-sd-worker.exe').touch()
            (root/'stable-diffusion.dll').touch()
            engine=Engine(root,root,{})
            try:
                for backend in ('cuda','vulkan','cpu'):
                    for policy in ('on_demand','resident'):
                        session=MagicMock();session.ready=False;session.files={'model':'pikon.safetensors'}
                        settings=DEFAULTS|{'backend':backend,'profile':'low','memory_policy':policy}
                        with patch.object(engine,'_activate',return_value=session),patch('h3chat.engine.runtime_executable',return_value=root/'sd-cli.exe'):
                            engine.start_image({'architecture':'sd'},settings,root/'log',threading.Event())
                        payload=session.send.call_args.args[0]
                        device='cpu' if backend=='cpu' else backend+'0'
                        self.assertEqual((payload['backend'],payload['params_backend'],payload['vae_backend']),(device,device,device))
            finally:engine.stop()

    def test_vae_blocks_are_never_shown_as_extra_sampling_steps(self):
        s=Session((), 'image',{}, {},{},Path('unused.log'))
        for event in ({'event':'progress','phase':'sample','step':0,'steps':13},
                      {'event':'progress','phase':'sample','step':13,'steps':13},
                      {'event':'progress','phase':'decode','backend':'cuda0','step':25,'steps':25},
                      {'event':'done'}):s.events.put(event)
        labels=[];s.wait('done',threading.Event(),1,labels.append)
        self.assertIn('13 passi previsti',labels[0])
        self.assertIn('13/13 passi',labels[1])
        self.assertEqual(labels[2],'Decodifica immagine · GPU · 25/25 blocchi')

    def test_image_gpu_overflow_is_oom_without_silent_cpu_fallback(self):
        model={'id':'sd','name':'SD','architecture':'sd','capabilities':['create'], 'files':[{'role':'model','size':6*1024**3}]}
        hw={'ram':{'free_mb':32000},'gpu':[{'name':'GPU','vendor':'NVIDIA','free_mb':4000,'total_mb':4096}]}
        demand=assess_model(model,DEFAULTS|{'profile':'balanced','backend':'cuda'},hw)
        resident=assess_model(model,DEFAULTS|{'profile':'balanced','backend':'cuda','memory_policy':'resident'},hw)
        self.assertEqual(demand['status'],'oom');self.assertTrue(demand['oom_risk'])
        self.assertEqual(demand['vram_gb'],resident['vram_gb'])
        self.assertTrue(any('VAE ed encoder usano la GPU' in x for x in demand['assumptions']))

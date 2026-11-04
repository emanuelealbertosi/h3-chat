import copy,unittest,tempfile,json
from pathlib import Path
from h3chat.ph3_image import SIGMAS,validate,upsample_input,ready,CORE_REVISION
from h3chat.image_options import options,capture_request,validate_overrides
import test_visual_models as fixture


class PH3Tests(unittest.TestCase):
    setUp=fixture.VisualModelsTests.setUp
    tearDown=fixture.VisualModelsTests.tearDown

    def model(self):return self.app.external_model({'profile':'ph3-image','name':'P-H3 fixture','files':self.qwen['external_config']['files']})

    def test_default_recipe_registration_and_resolution_are_model_specific(self):
        model=self.model();settings=copy.deepcopy(self.app.store.settings());result=options(model,settings,'8 MP 16:9 seed 42')
        self.assertEqual(model['max_refs'],8);self.assertEqual(model['capabilities'],['create','edit'])
        self.assertEqual((result['steps'],result['cfg'],result['sampler'],result['scheduler']),(8,1,'euler','ph3_image'))
        self.assertTrue(result['ph3_upsample']);self.assertEqual(result['seed'],42)
        self.assertGreaterEqual(result['width']*result['height'],8000000)
        self.assertEqual(result['width']%32,0);self.assertEqual(result['height']%32,0)
        self.assertEqual(options(self.qwen,settings)['steps'],25);self.assertEqual(settings,self.app.store.settings())

    def test_recipe_does_not_silently_accept_wrong_schedule_or_step_count(self):
        model=self.model();settings=self.app.store.settings()
        for prompt in ('steps 20','CFG 4','sampler heun','scheduler simple'):
            with self.subTest(prompt=prompt),self.assertRaisesRegex(ValueError,'ricetta ufficiale'):options(model,settings,prompt)
        with self.assertRaises(ValueError):options(self.qwen,settings,'scheduler ph3_image')
        self.assertEqual(len(SIGMAS),9);self.assertEqual(SIGMAS[-1],0)

    def test_upsampler_and_large_canvas_snapshot_stay_request_local(self):
        model=self.model();before=self.app.store.settings()
        saved=capture_request(model,before,{'width':2912,'height':2912,'megapixels':8,'ph3_upsample':False})
        self.assertFalse(options(model,saved)['ph3_upsample']);self.assertEqual(self.app.store.settings(),before)
        with self.assertRaises(ValueError):validate_overrides({self.qwen['id']:{'width':2912}},{self.qwen['id']:self.qwen})
        with self.assertRaises(ValueError):validate_overrides({model['id']:{'ph3_upsample':'yes'}},{model['id']:model})
        self.assertEqual(upsample_input('A glass pear',2048,1024),'Aspect ratio: 2:1\nRequest: A glass pear')

class RuntimeReadinessTests(unittest.TestCase):
    def test_minimax_family_is_allowed_but_other_adapters_are_not(self):
        from h3chat.image_options import compatible
        model={'architecture':'ph3'}
        self.assertTrue(compatible('minimax-h3',model))
        self.assertFalse(compatible('moss',model))
        self.assertFalse(compatible('qwen-image',model))

    def test_lora_reports_actual_patches_and_refuses_zero_matches(self):
        from types import SimpleNamespace
        from unittest.mock import Mock
        from h3chat.ph3_image import apply_loras
        original=SimpleNamespace(patches={})
        patched=SimpleNamespace(patches={'layer':[(1,'patch')]})
        comfy=SimpleNamespace(utils=SimpleNamespace(load_torch_file=Mock(return_value=({'weights':1},{}))),sd=SimpleNamespace(load_lora_for_models=Mock(return_value=(patched,None))))
        adapter={'path':'character.safetensors','weight':.7}
        model,report=apply_loras(original,[adapter],comfy)
        self.assertEqual(original.patches,{})
        self.assertEqual(report,[{'name':'character.safetensors','weight':.7,'applied_patches':1}])
        comfy.sd.load_lora_for_models.return_value=(original,None)
        with self.assertRaisesRegex(ValueError,'senza tensori'):apply_loras(original,[adapter],comfy)

    def test_namespace_aimdo_install_is_ready_and_missing_control_is_not(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);folder=root/'runtime/ph3'
            for name in ('core/comfy_extras/nodes_minimax_h3.py','core/comfy/text_encoders/minimax.py','packages/comfy_kitchen/__init__.py','packages/comfy_aimdo/control.py'):
                path=folder/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text('')
            (folder/'provenance.json').write_text(json.dumps({'revision':CORE_REVISION}))
            self.assertFalse((folder/'packages/comfy_aimdo/__init__.py').exists())
            self.assertTrue(ready(root))
            (folder/'packages/comfy_aimdo/control.py').unlink();self.assertFalse(ready(root))

if __name__=='__main__':unittest.main()

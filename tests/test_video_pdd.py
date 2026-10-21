import json,struct,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from h3chat.video_options import DEFAULTS,options,validate
from h3chat.video_pdd import check_header,apply

class PDDTests(unittest.TestCase):
    def test_standard_mode_never_imports_torch_or_patches_a_model(self):
        model=object()
        self.assertEqual(apply(model,DEFAULTS),(model,None,{}))
        self.assertFalse(validate({})['pdd_enabled'])

    def test_generic_lora_and_diffusion_checkpoint_are_rejected_before_gpu_load(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'ordinary.safetensors'
            header=json.dumps({'diffusion_model.block.weight':{'shape':[1]}}).encode()
            path.write_bytes(struct.pack('<Q',len(header))+header)
            with self.assertRaisesRegex(ValueError,'non è un adattatore'):check_header(path)

    def test_only_the_trained_eight_step_recipe_can_be_queued(self):
        path=str(Path(tempfile.gettempdir())/'MiniMax-H3-Ref2VA-Acc-8Step.safetensors')
        good=DEFAULTS|{'pdd_enabled':True,'pdd_lora':path,'steps':8,'sampler':'euler'}
        with patch('h3chat.external_models.valid_weight',return_value=True),patch('h3chat.video_pdd.check_header'):
            self.assertEqual(validate(good)['steps'],8)
            for changed in ({'steps':20},{'cfg':2},{'shift_audio':12},{'sampler':'res_multistep'}):
                with self.subTest(changed=changed),self.assertRaisesRegex(ValueError,'PDD richiede'):validate(good|changed)
            with self.assertRaisesRegex(ValueError,'PDD richiede'):
                options({'id':'model'},{'video_overrides':{'model':good},'_video_steps':20},False)
        with self.assertRaisesRegex(ValueError,'prima di attivarlo'):validate(good|{'pdd_lora':''})

    def test_off_preserves_ordinary_twenty_step_options(self):
        p=options({'id':'model'},{'video_overrides':{'model':{'steps':20}}},False)
        self.assertEqual((p['steps'],p['sampler'],p['pdd_enabled']),(20,'res_multistep',False))

if __name__=='__main__':unittest.main()

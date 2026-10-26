"""Official FastH3 sampling contract and VSA wiring without loading a model."""
import unittest
from types import SimpleNamespace
from unittest.mock import Mock
from h3chat.fasth3 import PRESET,attach,check_heads
from h3chat.video_options import options

class FastH3Tests(unittest.TestCase):
    def test_distilled_native_head_bank_has_dedicated_load_contract(self):
        check_heads(3072,1024,True);check_heads(96,32,False)
        with self.assertRaises(ValueError):check_heads(3072,1024,False)
        with self.assertRaises(ValueError):check_heads(96,32,True)
    def test_profile_defaults_and_conflicting_recipe_are_explicit(self):
        model={'id':'fast','external_config':{'profile':'fasth3-omni'}}
        result=options(model,{},False)
        for key,value in PRESET.items():self.assertEqual(result[key],value)
        with self.assertRaisesRegex(ValueError,'FastH3'):options(model,{'video_overrides':{'fast':{'steps':12}}},False)
        with self.assertRaisesRegex(ValueError,'VSA'):options({'id':'normal'},{'video_overrides':{'normal':{'attention':'vsa'}}},False)
        normal=options({'id':'normal'},{},False);self.assertEqual(normal['steps'],12);self.assertEqual(normal['sampler'],'res_multistep')
        from h3chat.video_options import capture_request
        captured=capture_request({'video_model':'fast'},{'video':True,'video_parameters':{'duration':10}},lambda *a:model)
        self.assertEqual(options(model,captured,False)['steps'],8)
    def test_actual_native_patcher_called_with_trained_vsa_and_gate_guard(self):
        model=Mock();model.get_model_object.return_value=SimpleNamespace(blocks=[SimpleNamespace(attn=SimpleNamespace(to_gate_compress=object()))]);patch=Mock(return_value='patched')
        self.assertEqual(attach(model,patch),'patched');self.assertTrue(patch.call_args.kwargs['vsa']);self.assertEqual(patch.call_args.kwargs['topk_ratio'],.1);self.assertEqual(patch.call_args.kwargs['start_percent'],0.)
        model.get_model_object.return_value.blocks[0].attn.to_gate_compress=None
        with self.assertRaises(ValueError):attach(model,patch)
        self.assertEqual(patch.call_count,1)

if __name__=='__main__':unittest.main()

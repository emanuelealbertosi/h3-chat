"""Adapter recognition uses paired shapes; no model or GPU is loaded."""
import unittest
import sys
import tempfile
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock, patch
from h3chat.lora_families import targets, tensor_family
from h3chat.image_options import compatible


def header(layers):
    result={}
    for name,(out_size,in_size) in layers.items():
        result[name+'.lora_A.weight']={'shape':[4,in_size]}
        result[name+'.lora_B.weight']={'shape':[out_size,4]}
    return result


class LoraFamilyTests(unittest.TestCase):
    def test_moss_without_metadata_requires_attention_and_both_gated_ffn_shapes(self):
        layers={'diffusion_model.layers.0.proj.q':(3072,3072),
                'diffusion_model.layers.0.proj.ffn_up_gate':(16384,3072),
                'diffusion_model.layers.0.proj.ffn_down':(3072,8192)}
        self.assertEqual(tensor_family(header(layers)),'moss')
        for missing in layers:
            self.assertEqual(tensor_family(header({k:v for k,v in layers.items() if k!=missing})), '')
        wrong=layers|{'diffusion_model.layers.0.proj.ffn_down':(3072,4096)}
        self.assertEqual(tensor_family(header(wrong)),'')
        self.assertTrue(compatible('moss',{'architecture':'moss'}));self.assertFalse(compatible('moss',{'architecture':'flux1'}))

    def test_generic_sd_profile_uses_actual_checkpoint_family(self):
        from h3chat.external_models import build_model,validate_config
        from test_krea2_loras import adapter
        with tempfile.TemporaryDirectory() as folder:
            for width,family in ((768,'sd15'),(1024,'sd2'),(2048,'sdxl'),(1280,'sdxl'),(999,'')):
                path=adapter(Path(folder)/f'checkpoint-{width}.safetensors',
                             {'model.diffusion_model.input_blocks.4.1.transformer_blocks.0.attn2.to_k.weight':[640,width]})
                model=build_model(validate_config({'profile':'sd','files':{'model':str(path)}}))
                self.assertEqual(model['lora_family'],family)
                for candidate in ('sd15','sd2','sdxl'):
                    self.assertEqual(compatible(candidate,model),candidate==family)

    def test_unlabelled_families_and_model_filter(self):
        cases={
            'minimax-h3':{'diffusion_model.blocks.0.attn.qkv_proj':(21504,5376)},
            'anima':{'diffusion_model.blocks.0.cross_attn.k_proj':(2048,1024),
                     'diffusion_model.blocks.0.adaln_modulation_cross_attn.1':(256,2048)},
            'qwen-image':{'diffusion_model.transformer_blocks.0.attn.add_k_proj':(3072,3072)},
            'flux1':{'lora_unet_double_blocks_0_img_attn_proj':(3072,3072)},
            'flux2':{'lora_unet_double_blocks_0_img_attn_proj':(4096,4096)},
            'sdxl':{'lora_unet_input_blocks_4_1_transformer_blocks_0_attn2_to_k':(640,2048)},
            'sd15':{'lora_unet_down_blocks_0_attentions_0_transformer_blocks_0_attn2_to_k':(320,768)},
            'sd2':{'lora_unet_down_blocks_0_attentions_0_transformer_blocks_0_attn2_to_k':(320,1024)},
        }
        for family,layers in cases.items():
            with self.subTest(family=family):
                self.assertEqual(tensor_family(header(layers)),family)
                for other in cases:
                    self.assertEqual(compatible(family,{'architecture':other}),family==other)
        self.assertFalse(compatible('',{'architecture':'krea2'}))

    def test_h3_mlp_only_and_underscore_exports(self):
        self.assertEqual(tensor_family(header({'lora_unet_blocks_0_attn_out_proj':(5376,7168)})),'minimax-h3')
        self.assertEqual(tensor_family(header({'blocks.0.mlp.fc1':(28672,5376),'blocks.0.mlp.fc2':(5376,14336)})),'minimax-h3')
        self.assertEqual(tensor_family(header({'blocks.0.mlp.fc1':(28672,5376)})),'')

    def test_lokr_and_loha_effective_target_dimensions(self):
        lokr={'blocks.0.attn.out_proj.lokr_w1':{'shape':[4,4]},
              'blocks.0.attn.out_proj.lokr_w2':{'shape':[1344,1792]}}
        self.assertEqual(targets(lokr),{'blocks.0.attn.out_proj':(5376,7168,'lokr')})
        self.assertEqual(tensor_family(lokr),'minimax-h3')
        loha={f'layer.hada_w{i}_{part}':{'shape':shape}
              for i in (1,2) for part,shape in (('a',[8,2]),('b',[2,6]))}
        self.assertEqual(targets(loha),{'layer':(8,6,'loha')})
        del loha['layer.hada_w2_b']
        self.assertEqual(targets(loha),{})

    def test_malformed_or_partial_pairs_never_identify_a_family(self):
        for layers in ({'blocks.0.attn.qkv_proj':(21504,5375)}, {'anima_krea2_minimax':(8,8)}):
            self.assertEqual(tensor_family(header(layers)),'')
        bad=header({'blocks.0.attn.qkv_proj':(21504,5376)})
        bad['blocks.0.attn.qkv_proj.lora_B.weight']['shape']=[21504,3]
        self.assertEqual(targets(bad),{})
        for value in (None,{'shape':[True,4]},{'shape':[-1,4]}):
            self.assertEqual(targets({'layer.lora_A.weight':value,'layer.lora_B.weight':{'shape':[8,4]}}),{})

    def test_video_lokr_dimension_check_before_runtime_patch(self):
        from h3chat.video_loras import apply
        key='blocks.0.attn.out_proj';target='diffusion_model.'+key+'.weight'
        state={key+'.lokr_w1':SimpleNamespace(shape=(4,4)),
               key+'.lokr_w2':SimpleNamespace(shape=(1344,1792))}
        comfy=ModuleType('comfy')
        comfy.lora=ModuleType('comfy.lora');comfy.lora_convert=ModuleType('comfy.lora_convert');comfy.utils=ModuleType('comfy.utils')
        comfy.lora.model_lora_keys_unet=Mock(return_value={key:target})
        comfy.lora.load_lora=Mock(return_value={target:object()})
        comfy.lora_convert.convert_lora=lambda value:value
        comfy.utils.load_torch_file=Mock(return_value=state)
        comfy.utils.get_attr=Mock(return_value=SimpleNamespace(shape=(5376,7168)))
        patched=Mock();patched.add_patches.return_value=[target]
        model=Mock();model.clone.return_value=patched
        modules={'comfy':comfy,**{name:getattr(comfy,name.split('.')[-1]) for name in ('comfy.lora','comfy.lora_convert','comfy.utils')}}
        items=[{'path':'adapter.safetensors','weight':.75}]
        with patch.dict(sys.modules,modules),patch('h3chat.video_loras.validate',return_value=items),patch('h3chat.video_pdd.merge_trunk_once',return_value=1):
            result,reports=apply(model,items)
            self.assertIs(result,patched)
            self.assertEqual(reports[0]['prepared_patch_keys'],1)
            patched.add_patches.assert_called_once_with(comfy.lora.load_lora.return_value,.75)
            comfy.lora.load_lora.reset_mock()
            comfy.utils.get_attr.return_value=SimpleNamespace(shape=(5376,5376))
            with self.assertRaisesRegex(ValueError,'incompatibile con questo checkpoint'):apply(model,items)
            comfy.lora.load_lora.assert_not_called()


if __name__=='__main__':unittest.main()

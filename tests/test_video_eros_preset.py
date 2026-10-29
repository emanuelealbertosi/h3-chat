import ast
from pathlib import Path
from types import ModuleType,SimpleNamespace
import unittest
from unittest.mock import Mock,patch
from h3chat.video_options import options,resolve_canvas
from h3chat.video_sparse import attach


class ErosPresetTests(unittest.TestCase):
    def test_both_standard_profiles_resolve_actual_sampling_and_canvas(self):
        preset={'steps':8,'sampler':'er_sde','scheduler':'sgm_uniform','cfg':1,
            'megapixels':.98,'aspect':'16:9','shift_video':12,'shift_audio':3,'attention':'vsa','pdd_enabled':False}
        for ident in ('beta5','beta7'):
            model={'id':ident,'external_config':{'profile':'minimax-h3'}}
            effective=options(model,{'video_overrides':{ident:preset}},False)
            canvas=resolve_canvas(effective,{'images':[]},[])
            self.assertEqual((canvas['width'],canvas['height']),(1344,768))
            self.assertEqual((canvas['output_width'],canvas['output_height']),(1344,756))
            self.assertEqual((effective['sampler'],effective['scheduler'],effective['steps']),('er_sde','sgm_uniform',8))

    def test_standard_vsa_patcher_accepts_no_gates(self):
        model=Mock();model.get_model_object.return_value=SimpleNamespace(blocks=[SimpleNamespace(attn=SimpleNamespace(to_gate_compress=None))])
        patcher=Mock(return_value='sparse');self.assertEqual(attach(model,patcher),'sparse')
        self.assertEqual(patcher.call_args.kwargs['topk_ratio'],.1)
        self.assertEqual(patcher.call_args.kwargs['min_tokens'],12288)

    def test_native_standard_vsa_requires_kitchen_and_switch_removes_patch(self):
        root=Path(__file__).resolve().parents[1]
        definition=next(n for n in ast.parse((root/'native/video-worker.py').read_text(encoding='utf8')).body if isinstance(n,ast.ClassDef) and n.name=='Worker')
        namespace={'emit':Mock(),'logging':Mock(),'chunked_attention':Mock()}
        exec(compile(ast.Module(body=[definition],type_ignores=[]),'<video-worker>','exec'),namespace)
        worker=namespace['Worker']();base=Mock();worker.model=base
        worker.torch=SimpleNamespace(cuda=SimpleNamespace(get_device_properties=lambda _:SimpleNamespace(total_memory=16*1024**3)))
        module=ModuleType('comfy.ldm.modules');module.attention=SimpleNamespace(COMFY_KITCHEN_INT8_ATTENTION_IS_AVAILABLE=False,SAGE_ATTENTION_IS_AVAILABLE=False,attention_pytorch=Mock())
        sparse=ModuleType('comfy_extras.nodes_sparse_attention');sparse.apply_block_sparse_attention=Mock(return_value=Mock())
        with patch.dict('sys.modules',{'comfy.ldm.modules':module,'comfy_extras.nodes_sparse_attention':sparse}):
            with self.assertRaisesRegex(ValueError,'ComfyKitchen'):worker.configure_attention('vsa')
            module.attention.COMFY_KITCHEN_INT8_ATTENTION_IS_AVAILABLE=True;module.attention.attention_comfy_kitchen_int8=Mock()
            self.assertEqual(worker.configure_attention('vsa'),'vsa')
            self.assertIs(worker.vsa_base_model,base);self.assertIsNot(worker.model,base)
            self.assertEqual(worker.configure_attention('pytorch'),'pytorch')
            self.assertIs(worker.model,base);self.assertIsNone(worker.vsa_base_model)


if __name__=='__main__':unittest.main()

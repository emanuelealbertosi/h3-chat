import unittest
from types import SimpleNamespace as NS
from h3chat.video_mlp import supported, rows_per_chunk, install, require_supported_weights


class VideoMLPTests(unittest.TestCase):
    def fixture(self):
        class Weight:
            _layout_cls='TensorWiseINT8Layout'
            _params=NS(transposed=False)
        ops=NS(QuantizedTensor=Weight)
        def projection():return NS(weight=Weight(),weight_function=[],bias_function=[],out_features=57344)
        return NS(fc1=projection(),fc2=projection(),forward=lambda x:'original'),ops

    def test_only_independent_int8_rows_are_supported(self):
        layer,ops=self.fixture();self.assertTrue(supported(layer,ops))
        for key,value in [('pre_quant_scale',object()),('_full_precision_mm',True),('comfy_force_cast_weights',True),('weight_function',[object()]),('bias_function',[object()])]:
            with self.subTest(key=key):
                layer,ops=self.fixture();setattr(layer.fc1,key,value)
                self.assertFalse(supported(layer,ops))
        layer,ops=self.fixture();layer.fc2.weight._layout_cls='TensorCoreNVFP4Layout'
        self.assertFalse(supported(layer,ops))

    def test_workspace_is_bounded_and_kernel_rows_are_aligned(self):
        layer,_=self.fixture();x=NS(element_size=lambda:2)
        rows=rows_per_chunk(layer,x,512*1024**2)
        self.assertEqual(rows%16,0)
        self.assertLessEqual(rows*57344*2,512*1024**2)
        self.assertGreaterEqual(rows,16)

    def test_install_is_idempotent_and_cpu_keeps_original_path(self):
        layer,ops=self.fixture();model=NS(blocks=[NS(mlp=layer)])
        self.assertEqual(install(model,None,ops),1)
        self.assertEqual(install(model,None,ops),0)
        self.assertEqual(layer.forward(NS(requires_grad=False,device=NS(type='cpu'))),'original')

    def test_later_weight_patches_keep_the_original_forward(self):
        layer,ops=self.fixture();install(NS(blocks=[NS(mlp=layer)]),None,ops)
        layer.fc2.weight_function.append(object())
        self.assertEqual(layer.forward(NS(requires_grad=False,device=NS(type='cuda'))),'original')

    def test_removed_w4a8_variant_is_rejected_without_affecting_int8(self):
        layer,ops=self.fixture()
        require_supported_weights(NS(named_parameters=lambda:[('weight',layer.fc1.weight)]))
        layer.fc1.weight._layout_cls=layer.fc2.weight._layout_cls='AsymW4A8Int8Layout'
        self.assertFalse(supported(layer,ops))
        self.assertEqual(install(NS(blocks=[NS(mlp=layer)]),None,ops),0)
        with self.assertRaisesRegex(ValueError,'W4A8 non è supportato'):
            require_supported_weights(NS(named_parameters=lambda:[('weight',layer.fc1.weight)]))

if __name__=='__main__':unittest.main()

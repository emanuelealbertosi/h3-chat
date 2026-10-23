import json,unittest
from runtime_test_support import cpu_package
np=cpu_package('numpy')
from h3chat.moss_image import unpack_qkv
from h3chat.external_models import PROFILES
from h3chat.image_options import options
from h3chat.store import DEFAULTS

def descriptor(value):return np.frombuffer(json.dumps(value).encode(),dtype=np.uint8)

class MossTests(unittest.TestCase):
    @unittest.skipUnless(np is not None,'Install the private documents runtime for NumPy tensor checks')
    def test_non_grid_output_is_cropped_without_pixel_resampling(self):
        from h3chat.image_canvas import crop_canvas
        source=np.arange(1504*1504,dtype=np.uint32).reshape(1504,1504)
        cropped=crop_canvas(source,1500,1500)
        self.assertEqual(cropped.shape,(1500,1500))
        np.testing.assert_array_equal(cropped,source[2:-2,2:-2])
        self.assertTrue(np.shares_memory(cropped,source))
        with self.assertRaises(ValueError):crop_canvas(source,1600,1500)
    def test_official_preset_can_be_overridden_without_touching_other_models(self):
        model={'id':'moss-test',**PROFILES['moss']}
        base=options(model,DEFAULTS)
        self.assertEqual((base['steps'],base['cfg'],base['sampler'],base['scheduler']),(50,3,'euler','sgm_uniform'))
        changed=options(model,DEFAULTS|{'image_overrides':{'moss-test':{'steps':30,'sampler':'heun','scheduler':'karras'}}})
        self.assertEqual((changed['steps'],changed['sampler'],changed['scheduler']),(30,'heun','karras'))
        self.assertEqual(options(model,DEFAULTS)['steps'],50)
        self.assertEqual(options(model,DEFAULTS|{'image_overrides':{'moss-test':{'scheduler':'auto'}}})['scheduler'],'sgm_uniform')
        self.assertEqual(base['strength'],.65)
        self.assertEqual(options(model,DEFAULTS,'landscape, denoise 0.35')['strength'],.35)
        for value in (0,1.1,float('nan'),True):
            with self.assertRaises(ValueError):options(model,DEFAULTS|{'image_overrides':{'moss-test':{'strength':value}}})

    @unittest.skipUnless(np is not None,'Install the private documents runtime for NumPy tensor checks')
    def test_fused_int8_projection_preserves_each_row_and_its_scale(self):
        weight=np.arange(-24,24,dtype=np.int8).reshape(12,4);scale=np.arange(1,13,dtype=np.float32).reshape(12,1)/100
        state={'layers.0.proj.qkv.weight':weight,'layers.0.proj.qkv.weight_scale':scale,
            'layers.0.proj.qkv.comfy_quant':descriptor({'format':'int8_tensorwise','convrot':True,'convrot_groupsize':256}),
            'layers.0.comfy_attention.config':descriptor({'attention':'comfy_kitchen_int8'})}
        actual=unpack_qkv(state);x=np.arange(4,dtype=np.float32)
        expected=(weight*scale)@x
        observed=np.concatenate([(actual['layers.0.proj.'+name+'.weight']*actual['layers.0.proj.'+name+'.weight_scale'])@x for name in ('q','k','v')])
        np.testing.assert_array_equal(observed,expected)
        self.assertNotIn('layers.0.proj.qkv.weight',actual)
        self.assertEqual(len([k for k in actual if k.endswith('.comfy_quant')]),3)
        self.assertIn('layers.0.proj.qkv.weight',state)

    @unittest.skipUnless(np is not None,'Install the private documents runtime for NumPy tensor checks')
    def test_bad_fused_shapes_and_unreviewed_quantization_fail_before_sampling(self):
        with self.assertRaises(ValueError):unpack_qkv({'layers.0.proj.qkv.weight':np.zeros((13,4))})
        with self.assertRaises(ValueError):unpack_qkv({'layers.0.proj.qkv.weight':np.zeros((12,4)),
            'layers.0.proj.qkv.comfy_quant':descriptor({'format':'unknown'}),'layers.0.proj.qkv.weight_scale':np.ones((12,1))})

if __name__=='__main__':unittest.main()

"""Header-only Krea 2 indexing and cross-family routing checks (no models)."""
import json
from pathlib import Path
import struct
import tempfile
import unittest

from h3chat.image_options import compatible, family
from h3chat.loras import inspect, LoraLibrary


def adapter(path, shapes, metadata=None):
    header={'__metadata__':metadata or {}}
    # Indexing reads shapes and verifies bounded offsets, never tensor contents.
    for index,(name,shape) in enumerate(shapes.items()):
        header[name]={'dtype':'F16','shape':shape,'data_offsets':[2*index,2*index+2]}
    raw=json.dumps(header).encode()
    path.write_bytes(struct.pack('<Q',len(raw))+raw+b'\0'*(2*len(shapes)))
    return path


def attention_shapes():
    return {f'diffusion_model.blocks.0.attn.{kind}.{suffix}.weight':shape
            for kind,output in (('gate',6144),('wq',6144),('wk',1536))
            for suffix,shape in (('lora_down',[64,6144]),('lora_up',[output,64]))}


class Krea2LoraTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.root=Path(self.tmp.name)
        self.model={'id':'krea-test','name':'Krea 2','architecture':'krea2','engine':'vision','capabilities':['create'],
                    'external_config':{'profile':'krea2'}}

    def tearDown(self):self.tmp.cleanup()

    def test_declared_family_is_distinct_from_flux_krea_and_anima(self):
        shapes={'layer.lora_A.weight':[1,1],'layer.lora_B.weight':[1,1]}
        paths=[adapter(self.root/(name+'.safetensors'),shapes,{'ss_base_model_version':base})
               for name,base in (('krea','krea2'),('flux','flux.1-krea'),('anima','anima'))]
        self.assertEqual([inspect(path)['family'] for path in paths],['krea2','flux1','anima'])
        self.assertEqual(family(self.model),'krea2')
        self.assertEqual(family(self.model|{'architecture':'generic'}),'krea2')
        self.assertTrue(compatible('krea2',self.model))
        self.assertFalse(compatible('anima',self.model))
        self.assertFalse(compatible('flux1',self.model))
        self.assertFalse(compatible('krea2',{'architecture':'flux1'}))

    def test_unlabelled_turbo_recognized_by_paired_projection_shapes(self):
        path=adapter(self.root/'adapter.safetensors',attention_shapes())
        result=inspect(path)
        self.assertEqual((result['family'],result['family_source'],result['pairs']),('krea2','tensors',3))
        index=LoraLibrary().scan([str(self.root)])['items']
        self.assertEqual(len(index),1)
        self.assertIn('struttura',index[0]['note'])
        selected=LoraLibrary().capture([{'id':index[0]['id'],'model_id':'krea-test','weight':.75}],
                                      [str(self.root)],{'krea-test':self.model})
        self.assertEqual(selected[0]['family'],'krea2')
        self.assertEqual(selected[0]['weight'],.75)

    def test_filename_and_unpaired_projection_do_not_assert_compatibility(self):
        path=adapter(self.root/'Krea2_character.safetensors',{'other.lora_A.weight':[1,1],'other.lora_B.weight':[1,1]})
        self.assertEqual(inspect(path)['family'],'')
        shapes=attention_shapes()
        shapes.pop('diffusion_model.blocks.0.attn.gate.lora_up.weight')
        path=adapter(self.root/'unpaired.safetensors',shapes)
        self.assertEqual(inspect(path)['family'],'')

    def test_lokr_complete_pairs_indexed_without_guessing_unknown_family(self):
        shapes={'diffusion_model.blocks.0.attn.gate.lokr_w1':[4,4],
                'diffusion_model.blocks.0.attn.gate.lokr_w2':[1536,1536]}
        path=adapter(self.root/'known.safetensors',shapes,{'ss_base_model_version':'krea2'})
        self.assertEqual((inspect(path)['family'],inspect(path)['pairs']),('krea2',1))
        for name,meta in (('unknown',{}),('sdxl',{'ss_base_model_version':'sdxl'})):
            self.assertEqual(inspect(adapter(self.root/(name+'.safetensors'),shapes,meta))['family'],'' if name=='unknown' else 'sdxl')
        self.assertIsNone(inspect(adapter(self.root/'partial.safetensors',
                         {'diffusion_model.blocks.0.attn.gate.lokr_w1':[4,4]},
                         {'ss_base_model_version':'krea2'})))
        # A targeted model patch is not a LoRA and must not appear in its picker.
        self.assertIsNone(inspect(adapter(self.root/'filterbypass.safetensors',
                                         {'diffusion_model.txtfusion.projector.diff':[1,12]})))


if __name__=='__main__':unittest.main()

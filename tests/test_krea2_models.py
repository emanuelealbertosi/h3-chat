import struct
import json
import tempfile
import unittest
from pathlib import Path
from h3chat.external_models import validate_config,build_model
from h3chat.image_options import options
from h3chat.store import DEFAULTS
from h3chat.visual_routing import image_brief


class Krea2ModelsTests(unittest.TestCase):
    def test_three_existing_components_are_linked_without_copying_and_have_separate_preset(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);paths={}
            header=json.dumps({'weight':{'dtype':'F16','shape':[1],'data_offsets':[0,2]}}).encode()
            for role in ('diffusion','llm','vae'):
                folder=root/role;folder.mkdir();file=folder/(role+'.safetensors')
                file.write_bytes(struct.pack('<Q',len(header))+header+b'\x00\x00');paths[role]=str(file)
            config=validate_config({'profile':'krea2','name':'RedCraft Krea 2','files':paths})
            model=build_model(config)
            self.assertEqual(model['engine'],'vision');self.assertEqual(model['architecture'],'krea2')
            self.assertEqual(model['capabilities'],['create']);self.assertEqual(model['max_refs'],0)
            self.assertEqual(config['files'],paths)
            original=options(model,DEFAULTS)
            self.assertEqual((original['steps'],original['cfg'],original['sampler'],original['scheduler']),(8,1,'euler','simple'))
            custom=options(model,DEFAULTS|{'image_overrides':{model['id']:{'steps':16,'cfg':2}}})
            self.assertEqual((custom['steps'],custom['cfg']),(16,2));self.assertEqual(options(model,DEFAULTS)['steps'],8)
            self.assertEqual(len(list(root.rglob('*.safetensors'))),3)
            brief,schema=image_brief(model)
            self.assertIn('Krea 2',brief);self.assertIn('prompt',schema['required']);self.assertNotIn('tag-based',brief)
            with self.assertRaises(ValueError):validate_config({'profile':'krea2','files':{'diffusion':paths['diffusion']}})


if __name__=='__main__':unittest.main()

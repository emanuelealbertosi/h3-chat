import copy,json,unittest
from pathlib import Path
from h3chat.infographic_scene import validate

FIXTURE=Path(__file__).parent/'fixtures/motion-scene-v2.json'

class SceneTests(unittest.TestCase):
    def scene(self):return json.loads(FIXTURE.read_text(encoding='utf8'))
    def test_versioned_scene_normalizes_without_mutating_input(self):
        scene=self.scene();before=copy.deepcopy(scene);value=validate(scene)
        self.assertEqual(scene,before);self.assertEqual(value['objects'][0]['transform']['scaleX'],1)
        self.assertEqual(len(value['objects']),3)
    def test_rejects_active_content_unknown_keys_and_nonfinite_values(self):
        for key,value in [('script','alert(1)'),('url','https://example.invalid'),('__proto__',{})]:
            scene=self.scene();scene[key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):validate(scene)
        for value in (float('nan'),float('inf'),True):
            scene=self.scene();scene['objects'][0]['transform']['x']=value
            with self.subTest(value=value),self.assertRaises(ValueError):validate(scene)
        scene=self.scene();scene['objects'][0]['fill']='url(https://example.invalid)'
        with self.assertRaises(ValueError):validate(scene)
    def test_ids_parents_and_keyframes_are_checked(self):
        scene=self.scene();scene['objects'][1]['id']='rack'
        with self.assertRaisesRegex(ValueError,'duplicato'):validate(scene)
        scene=self.scene();scene['objects'][0]['parentId']='missing'
        with self.assertRaisesRegex(ValueError,'padre'):validate(scene)
        scene=self.scene();scene['objects'][0]['tracks'][0]['keyframes'][1]['t']=11
        with self.assertRaisesRegex(ValueError,'intervallo'):validate(scene)
        scene=self.scene();scene['objects'][0]['tracks'][0]['keyframes'][1]['t']=0
        with self.assertRaisesRegex(ValueError,'crescenti'):validate(scene)
    def test_budget_over_legacy_160_is_not_silently_truncated(self):
        scene=self.scene();scene['objects']=[copy.deepcopy(scene['objects'][0]) for _ in range(200)]
        for i,obj in enumerate(scene['objects']):obj['id']='rack_'+str(i)
        self.assertEqual(len(validate(scene)['objects']),200)
        scene['objects']+=copy.deepcopy(scene['objects'][:57])
        with self.assertRaisesRegex(ValueError,'256'):validate(scene)

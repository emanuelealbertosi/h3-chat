import copy,json,unittest
import test_visual_models as fixture
from h3chat.image_presets import MOSS_RECIPES,validate_presets
from h3chat.image_options import options, configured, MOSS_NEGATIVE_PROMPT
from h3chat.store import DEFAULTS,Store

class MossPresetTests(unittest.TestCase):
    setUp=fixture.VisualModelsTests.setUp
    tearDown=fixture.VisualModelsTests.tearDown

    def item(self,name='Ritratto'):
        return {'id':'a'*32,'name':name,'parameters':{'width':1024,'height':1024,'megapixels':2.25,'aspect':'1:1',
            'steps':30,'cfg':4,'sampler':'res_multistep','scheduler':'simple','seed':1234,'negative_prompt':''}}

    def test_save_reload_without_changing_generation_defaults_or_jobs(self):
        before=copy.deepcopy(self.app.store.settings());item=self.item()
        saved=self.app.save_settings({'moss_presets':[item]})
        self.assertEqual(saved, before|{'moss_presets':[item]})
        self.assertEqual(Store(self.app.store.root).settings()['moss_presets'],[item])
        self.assertEqual(self.app.state()['image_options']['moss_presets'],MOSS_RECIPES)
        self.assertIsNone(self.app.store.one('SELECT id FROM jobs'))
        self.app.save_settings({'moss_presets':[]});self.assertEqual(self.app.store.settings(),before)

    def test_invalid_library_is_rejected_without_writing(self):
        before=copy.deepcopy(self.app.store.settings())
        for change in ([self.item('Ufficiale')],[self.item('fIzGiG')],[self.item('')],[self.item('x'*81)],
                       [self.item(),self.item()],self.item(),[self.item()|{'id':'../file'}],
                       [self.item()|{'parameters':{'scheduler':'invented'}}],
                       [self.item()|{'parameters':{'megapixels':float('nan')}}],
                       [self.item()|{'parameters':{'prompt':'not a parameter'}}]):
            with self.subTest(change=change),self.assertRaises(ValueError):self.app.save_settings({'moss_presets':change})
        self.assertEqual(self.app.store.settings(),before)

    def test_included_recipes_and_prompt_priority(self):
        model={'id':'moss','architecture':'moss','engine':'vision','width':1024,'height':1024,'strength':1}
        for recipe,expected in zip(MOSS_RECIPES,[(50,3,'euler','sgm_uniform'),(30,4,'res_multistep','simple')]):
            s=DEFAULTS|{'image_overrides':{'moss':{'megapixels':2.25,'aspect':'16:9','seed':123}|recipe['parameters']}}
            result=options(model,s);self.assertEqual((result['steps'],result['cfg'],result['sampler'],result['scheduler']),expected)
            self.assertEqual((result['width'],result['height'],result['seed']),(2000,1125,123))
            result=options(model,s,'Un faro 1 MP quadrato, 24 passi, CFG 2, seed 42')
            self.assertEqual((result['width'],result['height'],result['steps'],result['cfg'],result['seed']),(1000,1000,24,2,42))

    def test_moss_negative_default_and_explicit_empty_or_custom_override(self):
        model={'id':'moss-test','architecture':'moss','engine':'vision'}
        self.assertEqual(configured(model,DEFAULTS)['negative_prompt'],MOSS_NEGATIVE_PROMPT)
        for negative in ('','my custom negative'):
            settings=DEFAULTS|{'image_overrides':{'moss-test':{'negative_prompt':negative}}}
            self.assertEqual(configured(model,settings)['negative_prompt'],negative)
        self.assertEqual(configured(model,DEFAULTS|{'negative_prompt':'existing global'})['negative_prompt'],'existing global')
        self.assertEqual(configured({'id':'other','architecture':'qwen-edit'},DEFAULTS)['negative_prompt'],DEFAULTS['negative_prompt'])
        for recipe in MOSS_RECIPES:
            self.assertEqual(recipe['parameters']['negative_prompt'],MOSS_NEGATIVE_PROMPT)

if __name__=='__main__':unittest.main()

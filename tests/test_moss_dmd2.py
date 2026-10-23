import copy,json,unittest
from unittest.mock import Mock
from h3chat.image_options import options,validate_overrides,capture_request,OVERRIDE_KEYS
from h3chat.moss_dmd2 import RECIPE
from h3chat.store import DEFAULTS
from h3chat.image_api_server import ImageAPI


class TurboSettingsTests(unittest.TestCase):
    def setUp(self):
        self.model={'id':'m','architecture':'moss','engine':'vision','steps':50,'cfg':3,'sampler':'euler','scheduler':'sgm_uniform'}

    def test_recipe_preserves_canvas_seed_and_prior_preset_and_prompt_priority(self):
        preset={'steps':30,'cfg':4,'sampler':'res_multistep','scheduler':'simple','seed':42,'megapixels':2.25,'aspect':'1:1'}
        settings=copy.deepcopy(DEFAULTS)|{'image_overrides':{'m':preset|{'moss_turbo':True,'moss_turbo_previous':{k:preset[k] for k in RECIPE}}}}
        before=copy.deepcopy(settings);p=options(self.model,settings)
        self.assertEqual({k:p[k] for k in RECIPE},RECIPE)
        self.assertEqual((p['width'],p['height'],p['seed']),(1500,1500,42));self.assertEqual(settings,before)
        tuned=options(self.model,settings,'12 passi CFG 2 sampler heun seed 7')
        self.assertEqual((tuned['steps'],tuned['cfg'],tuned['sampler'],tuned['seed']),(12,2,'heun',7))
        snapshot=capture_request(self.model,settings,{k:v for k,v in p.items() if k in OVERRIDE_KEYS})
        self.assertEqual(snapshot['_image_request_parameters']['moss_turbo_previous'],{k:preset[k] for k in RECIPE})

    def test_reject_wrong_family_and_invalid_hidden_state(self):
        for value in ({'moss_turbo':'yes'},{'moss_turbo_previous':{'steps':20}},{'moss_turbo_previous':dict(RECIPE,steps=-5)}):
            with self.subTest(value=value),self.assertRaises(ValueError):validate_overrides({'m':value},{'m':self.model})
        with self.assertRaises(ValueError):validate_overrides({'q':{'moss_turbo':True}},{'q':{'architecture':'qwen21'}})

    def test_sillytavern_turbo_alias_uses_same_base_and_automatic_recipe(self):
        calls=[]
        def call(path,body=None):
            calls.append((path,body))
            if path.endswith('/models'):return {'data':[{'id':'m','name':'MOSS INT8','capabilities':['create']}]}
            if path.endswith('/generations'):return {'id':'test'}
            return {'status':'done','media':{'mime':'image/png','data':'png','generation':{'seed':42}}}
        client=Mock();client.call.side_effect=call
        api=ImageAPI(client,{'model':'m','moss_dmd2_ready':True,'models':{'m':{'architecture':'moss','engine':'vision','parameters':{'steps':30,'cfg':4,'sampler':'res_multistep','scheduler':'simple'}}}})
        self.assertEqual(len(api.models()),2)
        api.set_options({'sd_model_checkpoint':'MOSS INT8 · Turbo DMD2'})
        api.generate({'prompt':'A cat','steps':20,'cfg_scale':7,'width':768,'height':512,'seed':42})
        ticket=next(b for p,b in calls if p.endswith('/generations'))
        self.assertEqual(ticket['model'],'m');self.assertTrue(ticket['parameters']['moss_turbo'])
        self.assertEqual({k:ticket['parameters'][k] for k in RECIPE},RECIPE)
        self.assertEqual((ticket['parameters']['width'],ticket['parameters']['height']),(768,512))
        calls.clear();api.set_options({'sd_model_checkpoint':'m'});api.generate({'prompt':'A cat'})
        normal=next(b for p,b in calls if p.endswith('/generations'))
        self.assertEqual(normal['parameters']['steps'],30);self.assertFalse(normal['parameters']['moss_turbo'])


if __name__=='__main__':unittest.main()

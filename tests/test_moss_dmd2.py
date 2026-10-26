import copy,json,unittest
from unittest.mock import Mock
from h3chat.image_options import options,validate_overrides,capture_request,OVERRIDE_KEYS
from h3chat.moss_dmd2 import RECIPE
from h3chat.store import DEFAULTS
from h3chat.image_api_server import ImageAPI


class TurboSettingsTests(unittest.TestCase):
    def setUp(self):
        self.model={'id':'m','architecture':'moss','engine':'vision','steps':50,'cfg':3,'sampler':'euler','scheduler':'sgm_uniform'}

    def test_literal_turbo_is_applied_even_when_the_assistant_omits_it(self):
        from h3chat.moss_dmd2 import requested
        for prompt in ('Usa MOSS INT8 turbo: un panorama.', 'Usa il turbo con MOSS.', 'DMD2 attivo'):
            self.assertTrue(requested(prompt))
            result=options(self.model,DEFAULTS,prompt)
            self.assertTrue(result['moss_turbo']);self.assertEqual({k:result[k] for k in RECIPE},RECIPE)
        settings=DEFAULTS|{'image_overrides':{'m':dict(RECIPE,moss_turbo=True,moss_turbo_previous={'steps':40,'cfg':3,'sampler':'heun','scheduler':'simple'})}}
        result=options(self.model,settings,'senza turbo')
        self.assertFalse(result['moss_turbo']);self.assertEqual(result['steps'],40);self.assertEqual(result['sampler'],'heun')
        self.assertIsNone(requested('Usa Qwen 2.1 turbo'))
        with self.assertRaises(ValueError):options({'id':'q','architecture':'qwen21','engine':'vision'},DEFAULTS,'MOSS turbo')

    def test_typed_agent_turbo_survives_a_rewritten_visual_prompt(self):
        from types import SimpleNamespace
        from h3chat.image_batch import validate_plan
        model=self.model|{'name':'MOSS INT8','capabilities':['create'],'max_refs':1}
        app=SimpleNamespace(catalog={'m':model},engine=SimpleNamespace(require_model=lambda ident,cap:model))
        plan={'images':[{'prompt':'A landscape','model_id':'m','references':[],'parameters':{}}]}
        tasks=validate_plan(app,plan,[],DEFAULTS|{'_moss_turbo_requested':True},1,(),'Crea 1 immagine: un panorama.')
        self.assertTrue(tasks[0]['parameters']['moss_turbo']);self.assertEqual(tasks[0]['parameters']['steps'],8)
        wrong=model|{'architecture':'qwen21'};app.catalog['m']=wrong;app.engine.require_model=lambda ident,cap:wrong
        with self.assertRaisesRegex(ValueError,'Nessuna immagine'):validate_plan(app,plan,[],DEFAULTS|{'_moss_turbo_requested':True},1,(),'Un panorama.')

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

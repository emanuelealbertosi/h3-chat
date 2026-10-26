import json
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from h3chat.presentation_preferences import load,update,config
from h3chat.workspaces import guest_allowed

class PresentationPreferencesTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.app=SimpleNamespace(data=Path(self.temp.name))
    def tearDown(self):self.temp.cleanup()
    def test_last_settings_persist_and_do_not_include_prompts_or_generation_mode(self):
        value=config('slides',{'count_mode':'auto','count':32,'duration_minutes':20,'text_tone':'dark','format':'9:16'})
        update(self.app,{'kind':'slides','action':'last','config':value})
        restored=load(SimpleNamespace(data=self.app.data))
        self.assertEqual(restored['slides']['last'],value);self.assertIsNone(restored['backgrounds']['last'])
        self.assertFalse(list(self.app.data.glob('*.tmp')))
        for key in ('prompt','active','job_id','path'):
            with self.assertRaises(ValueError):config('slides',value|{key:'test'})
    def test_named_presets_update_case_insensitive_and_delete_keeps_last(self):
        body={'kind':'slides','action':'save','name':' Lezione ','config':{'count':12}}
        first=update(self.app,body)['slides'];ident=first['presets'][0]['id']
        second=update(self.app,body|{'name':'LEZIONE','config':{'count':20}})['slides']
        self.assertEqual(len(second['presets']),1);self.assertEqual(second['presets'][0]['id'],ident)
        result=update(self.app,{'kind':'slides','action':'delete','id':ident})['slides']
        self.assertEqual(result['presets'],[]);self.assertEqual(result['last']['count'],20)
    def test_backgrounds_and_workspace_are_independent(self):
        value={'name':'Porte logiche','variants':10,'margin':6,'palettes':['pastel'],'seed_mode':'fixed','seed':123}
        result=update(self.app,{'kind':'backgrounds','action':'save','name':'Cornici','config':value})
        self.assertEqual(result['backgrounds']['last']['margin'],6)
        self.assertEqual(result['backgrounds']['presets'][0]['config']['variants'],10)
        self.assertIsNone(result['slides']['last'])
        other=self.app.data/'guest';other.mkdir();self.assertIsNone(load(SimpleNamespace(data=other))['backgrounds']['last'])
        for method in ('GET','POST'):self.assertTrue(guest_allowed('/api/presentation-preferences',method))
        self.assertTrue(guest_allowed('/api/slide-backgrounds','GET'))
    def test_saving_collection_retains_order_and_no_paths_or_model_fallback(self):
        style={'base':'collection','set_id':'a'*32,'asset_ids':['c'*32,'b'*32],'opacity':35,'veil':'dark','decorations':True}
        result=update(self.app,{'kind':'slides','action':'last','config':{'background_style':style,'image_model':'removed-model'}})
        self.assertEqual(result['slides']['last']['background_style'],style)
        self.assertEqual(result['slides']['last']['image_model'],'removed-model')
        with self.assertRaises(ValueError):config('slides',{'background_style':style|{'path':'outputs/foreign.png'}})
        self.assertEqual(config('slides',{'background_style':{'base':'auto','decorations':True}})['background_style']['base'],'auto')
    def test_invalid_data_does_not_replace_saved_preferences(self):
        update(self.app,{'kind':'slides','action':'last','config':{'count':9}})
        before=(self.app.data/'presentation-preferences.json').read_bytes()
        for value in ({'count':101},{'duration_minutes':float('nan')},{'llm_timeout':20},{'generate_images':1},{'engine':'deterministic','composition':'rich'}):
            with self.assertRaises(ValueError):update(self.app,{'kind':'slides','action':'save','name':'bad','config':value})
        with self.assertRaises(ValueError):update(self.app,{'kind':'backgrounds','action':'save','name':'bad\nname','config':{}})
        self.assertEqual(before,(self.app.data/'presentation-preferences.json').read_bytes())
    def test_concurrent_categories_do_not_lose_each_other(self):
        threads=[threading.Thread(target=update,args=(self.app,{'kind':kind,'action':'save','name':'Preset','config':{}})) for kind in ('slides','backgrounds')]
        for t in threads:t.start()
        for t in threads:t.join()
        result=load(self.app)
        self.assertEqual([len(result[k]['presets']) for k in ('slides','backgrounds')],[1,1])
    def test_first_open_recovers_only_options_of_latest_workspace_requests(self):
        requests={'$.settings._slides':{'count':'auto','format':'4:3','theme':'indigo','generate_images':True},'$.settings._slide_backgrounds.options':{'name':'Ultimo set','margin':6,'variants':10}}
        class Queries:
            def one(self,sql,args):
                self.sql=sql
                return {'config':json.dumps(requests[args[0]])}
        app=SimpleNamespace(data=self.app.data,store=Queries());result=load(app)
        self.assertEqual(result['slides']['last']['count_mode'],'auto');self.assertEqual(result['slides']['last']['format'],'4:3')
        self.assertNotIn('theme',result['slides']['last']);self.assertEqual(result['backgrounds']['last']['margin'],6)
        self.assertFalse((app.data/'presentation-preferences.json').exists())

if __name__=='__main__':unittest.main()

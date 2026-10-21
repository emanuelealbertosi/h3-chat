import copy,json,unittest
from pathlib import Path
from unittest.mock import patch
import test_video as fixture
from test_external_models import safetensors
from h3chat.video_options import options,capture_request,resolve_canvas


class VideoRequestTests(unittest.TestCase):
    setUp=fixture.VideoTests.setUp
    tearDown=fixture.VideoTests.tearDown

    def test_model_attention_and_pdd_are_captured_without_changing_preferences(self):
        files=self.files|{'diffusion':str(safetensors(self.folder/'alternate.safetensors'))}
        second=self.app.external_model({'profile':'minimax-h3','name':'Second H3','files':files})
        self.app.save_settings({'video_overrides':{self.model['id']:{'attention':'veda','steps':12,'megapixels':.98},
                                                 second['id']:{'attention':'sage','steps':16,'megapixels':.7}}})
        original=copy.deepcopy(self.app.store.settings());chat=self.app.store.create_chat()['id']
        body={'prompt':'Crea un video','video':True,'assistant':False,'video_model':second['id'],
              'video_parameters':{'attention':'veda','pdd_enabled':False}}
        ident=self.app.send(chat,body)['job_id']
        settings=json.loads(self.app.store.one('SELECT payload FROM jobs WHERE id=?',(ident,))['payload'])['settings']
        result=options(second,settings,False)
        self.assertEqual((settings['video_model'],result['attention'],result['steps'],result['megapixels'],result['pdd_enabled']),
                         (second['id'],'veda',16,.7,False))
        self.assertEqual(self.app.store.settings(),original)
        meta=self.app.store.chat(chat)['messages'][0]['meta']
        self.assertEqual(meta['video_model'],second['id']);self.assertEqual(meta['video_request_parameters'],body['video_parameters'])
        self.app.store.execute("UPDATE jobs SET status='done' WHERE id=?",(ident,))
        retry=self.app.regenerate(chat)['job_id']
        copied=json.loads(self.app.store.one('SELECT payload FROM jobs WHERE id=?',(retry,))['payload'])['settings']
        self.assertEqual(copied['video_model'],second['id']);self.assertEqual(options(second,copied,False)['attention'],'veda')
        self.assertEqual(self.app.store.settings(),original)

    def test_pdd_request_uses_trained_settings_without_persisting_them(self):
        chat=self.app.store.create_chat()['id'];original=copy.deepcopy(self.app.store.settings())
        adapter=str(self.folder/'MiniMax-H3-Ref2VA-Acc-8Step.safetensors')
        body={'prompt':'Video','video':True,'assistant':False,'video_steps':8,
              'video_parameters':{'attention':'veda','pdd_enabled':True,'pdd_lora':adapter}}
        with patch('h3chat.external_models.valid_weight',return_value=True),patch('h3chat.video_pdd.check_header'):
            ident=self.app.send(chat,body)['job_id']
            settings=json.loads(self.app.store.one('SELECT payload FROM jobs WHERE id=?',(ident,))['payload'])['settings']
            result=options(self.model,settings,False)
            self.assertEqual((result['steps'],result['sampler'],result['cfg'],result['shift_video'],result['shift_audio']),
                             (8,'euler',1,12,3))
            self.assertTrue(result['pdd_enabled']);self.assertEqual(result['pdd_lora'],adapter)
            with self.assertRaisesRegex(ValueError,'PDD richiede'):self.app.send(chat,body|{'video_steps':20})
        self.assertEqual(self.app.store.settings(),original)
        self.assertEqual(len(self.app.store.all('SELECT id FROM jobs')),1)

    def test_default_request_keeps_the_existing_preset(self):
        preset={'attention':'veda','steps':12,'megapixels':.98,'duration':15}
        self.app.save_settings({'video_overrides':{self.model['id']:preset}})
        chat=self.app.store.create_chat()['id']
        ident=self.app.send(chat,{'prompt':'Video','video':True,'assistant':False,'video_model':'','video_parameters':{}})['job_id']
        settings=json.loads(self.app.store.one('SELECT payload FROM jobs WHERE id=?',(ident,))['payload'])['settings']
        self.assertEqual(settings['video_overrides'][self.model['id']],preset)
        self.assertNotIn('_video_request',settings)

    def test_seed_is_request_local_randomizes_each_render_and_survives_reload(self):
        from h3chat.request_draft import load
        self.app.save_settings({'video_overrides':{self.model['id']:{'seed':734,'megapixels':.98}}})
        original=copy.deepcopy(self.app.store.settings());chat=self.app.store.create_chat()['id']
        for seed in (-1,0,734,2147483647):
            ident=self.app.send(chat,{'prompt':'Video','video':True,'assistant':False,'video_parameters':{'seed':seed}})['job_id']
            saved=json.loads(self.app.store.one('SELECT payload FROM jobs WHERE id=?',(ident,))['payload'])['settings']
            self.assertEqual(options(self.model,saved,False)['seed'],seed)
            if seed==-1:
                with patch('h3chat.video_options.secrets.randbelow',side_effect=[11,22]):
                    self.assertEqual([options(self.model,saved)['seed'] for _ in range(2)],[11,22])
                self.assertEqual(saved['_video_request']['parameters']['seed'],-1)
            answer=self.app.store.chat(chat)['messages'][-1]
            self.assertEqual(load(self.app,chat,answer['id'])['controls']['video_parameters']['seed'],seed)
            self.assertEqual(self.app.store.settings(),original)
            self.app.store.execute("UPDATE jobs SET status='done' WHERE id=?",(ident,))
        for bad in (True,False,-2,2147483648,1.5,'734'):
            with self.subTest(seed=bad),self.assertRaisesRegex(ValueError,'Seed'):
                capture_request(original,{'video':True,'video_parameters':{'seed':bad}},lambda *_:self.model)

    def test_bad_requests_are_rejected_before_enqueue(self):
        chat=self.app.store.create_chat()['id']
        for value in ({'video_model':True},{'video_model':'missing'},{'video_parameters':None},
                      {'video_parameters':{'attention':'unsupported'}},{'video_parameters':{'pdd_enabled':'yes'}},
                      {'video_parameters':{'pdd_enabled':True}},{'video_parameters':{'veda_predictor':'F:/private.safetensors'}},
                      {'video_parameters':{'attention':'veda'},'video':False}):
            with self.subTest(value=value),self.assertRaises(ValueError):
                self.app.send(chat,{'prompt':'Video','video':True,'assistant':False}|value)
        self.assertEqual(self.app.store.all('SELECT id FROM jobs'),[])

    def test_remote_selection_preserves_server_defaults_and_rejects_local_acceleration(self):
        settings={'video_model':'local','video_overrides':{'local':{'steps':12,'attention':'veda'}}}
        original=copy.deepcopy(settings)
        require=lambda ident,cap:{'id':ident,'remote_media':True}
        selected=capture_request(settings,{'video':True,'video_model':'remote'},require)
        self.assertEqual(selected['video_model'],'remote');self.assertNotIn('remote',selected['video_overrides'])
        for changes in ({'attention':'veda'},{'pdd_enabled':False},{'pdd_enabled':True}):
            with self.subTest(changes=changes),self.assertRaises(ValueError):
                capture_request(settings,{'video':True,'video_model':'remote','video_parameters':changes},require)
        self.assertEqual(settings,original)

    def test_forced_format_wins_over_keyframes_and_conflicting_prompt(self):
        opts=options(self.model,self.app.store.settings(),False)
        plan={'images':[{'index':1,'role':'keyframe','seconds':0}]}
        for aspect in ('16:9','9:16','1:1','4:3','3:4'):
            result=resolve_canvas(opts,plan,[(896,1120)],'formato 9:16',force_aspect=aspect)
            a,b=map(int,aspect.split(':'))
            self.assertEqual(result['output_width']*b,result['output_height']*a)
            self.assertEqual((result['aspect'],result['aspect_source'],result['format_image']),(aspect,'request',None))
        automatic=resolve_canvas(opts,plan,[(896,1120)],'formato 16:9')
        self.assertEqual(automatic['aspect'],'4:5');self.assertEqual(automatic['aspect_source'],'image')

    def test_segment_duration_and_format_are_frozen_in_request_only(self):
        original=copy.deepcopy(self.app.store.settings());chat=self.app.store.create_chat()['id']
        for seconds in (5,10,15):
            ident=self.app.send(chat,{'prompt':'Video','video':True,'assistant':False,'video_segment_seconds':seconds,
                                     'video_parameters':{'aspect':'16:9'}})['job_id']
            captured=json.loads(self.app.store.one('SELECT payload FROM jobs WHERE id=?',(ident,))['payload'])['settings']
            self.assertEqual(captured['_video_segment_seconds'],seconds);self.assertEqual(captured['_video_aspect'],'16:9')
            self.assertEqual(options(self.model,captured,False)['duration'],seconds)
            self.app.store.execute("UPDATE jobs SET status='cancelled' WHERE id=?",(ident,))
        self.assertEqual(self.app.store.settings(),original)
        for bad in (True,0,6,16,'10',10.0):
            with self.subTest(bad=bad),self.assertRaises(ValueError):
                self.app.send(chat,{'prompt':'Video','video':True,'assistant':False,'video_segment_seconds':bad})

    def test_reload_cancelled_request_retains_assets_and_never_enqueues_or_exposes_credentials(self):
        from h3chat.request_draft import load
        settings=self.app.store.settings()|{'_video':True,'_assistant':True,'_video_quality':'high',
            '_video_steps':12,'_video_editing':'storyboard','_video_segment_seconds':10,'_video_aspect':'16:9',
            'video_overrides':{self.model['id']:{'aspect':'16:9','duration':10,'attention':'veda','megapixels':.98}},
            '_private_test_secret':'NEVER_EXPOSE_ME'}
        chat=self.app.store.create_chat()['id'];media=[{'id':'a'*32,'name':'Character.png','mime':'image/png','path':'fixture.png'}]
        ident=self.app.store.enqueue(chat,'Original complete prompt',media,settings)
        self.app.store.execute("UPDATE jobs SET status='cancelled' WHERE id=?",(ident,))
        messages=self.app.store.chat(chat)['messages'];before=self.app.store.all('SELECT * FROM jobs')
        first=load(self.app,chat,messages[0]['id']);second=load(self.app,chat,messages[1]['id'])
        self.assertEqual(first,second);self.assertEqual(first['prompt'],'Original complete prompt');self.assertEqual(first['media'],media)
        self.assertEqual(first['controls']['video_segment_seconds'],10);self.assertEqual(first['controls']['video_parameters']['aspect'],'16:9')
        self.assertEqual(first['controls']['video_parameters']['attention'],'veda');self.assertEqual(first['controls']['video_model'],self.model['id'])
        self.assertNotIn('NEVER_EXPOSE_ME',json.dumps(first));self.assertEqual(self.app.store.all('SELECT * FROM jobs'),before)
        other=self.app.store.create_chat()['id']
        with self.assertRaises(ValueError):load(self.app,other,messages[0]['id'])

if __name__=='__main__':unittest.main()

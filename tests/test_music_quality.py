import copy,json,tempfile,unittest
from pathlib import Path
from h3chat.music_quality import PROFILES,capture,validate
from h3chat.music_options import options
from h3chat.store import Store

CATALOG={'bf16':{'capabilities':['music']},'q8':{'capabilities':['music']},'chat':{'capabilities':['chat']}}
SETTINGS={'music_model':'q8','music_quality':'model','music_quality_profiles':{
    'high':{'model':'bf16','steps':60},'low':{'model':'q8','steps':32}},
    'music_overrides':{'bf16':{'cfg_scale':1.5,'seed':42},'q8':{'num_inference_steps':24}}}

class QualityTests(unittest.TestCase):
    def test_high_low_switch_weights_and_steps_without_mutating_saved_preferences(self):
        original=copy.deepcopy(SETTINGS)
        for quality,model,steps in [('high','bf16',60),('low','q8',32)]:
            request=capture(SETTINGS,quality);self.assertEqual(request['music_model'],model)
            parameters=options({'id':model},request,randomize=False)
            self.assertEqual(parameters['num_inference_steps'],steps)
            if quality=='high':self.assertEqual((parameters['cfg_scale'],parameters['seed']),(1.5,42))
        self.assertEqual(SETTINGS,original)

    def test_legacy_custom_parameters_and_configurable_quality_steps(self):
        request=capture(SETTINGS)
        self.assertEqual(options({'id':'q8'},request)['num_inference_steps'],24)
        custom=copy.deepcopy(SETTINGS);custom['music_quality']='high';custom['music_quality_profiles']['high']['steps']=88
        self.assertEqual(options({'id':'bf16'},capture(custom))['num_inference_steps'],88)

    def test_invalid_and_unconfigured_choices_are_rejected(self):
        for choice in ('wrong',False,0,[],{}):
            with self.subTest(choice=choice),self.assertRaises(ValueError):capture(SETTINGS,choice)
        for change in ({'model':'chat'},{'steps':True},{'steps':129},{'steps':0},{'extra':'file'}):
            settings=copy.deepcopy(SETTINGS);settings['music_quality_profiles']['high'].update(change)
            with self.subTest(change=change),self.assertRaises(ValueError):validate(settings,CATALOG)
        settings=copy.deepcopy(SETTINGS);settings['music_quality_profiles']=copy.deepcopy(PROFILES)
        with self.assertRaisesRegex(ValueError,'Configura'):capture(settings,'high')

    def test_queue_and_regeneration_keep_the_captured_quality(self):
        with tempfile.TemporaryDirectory() as temp:
            store=Store(temp);chat=store.create_chat();settings=capture(SETTINGS,'high')
            job=store.enqueue(chat['id'],'Test musicale',[],settings)
            store.save_settings({'music_quality':'low'})
            saved=json.loads(store.one('SELECT payload FROM jobs WHERE id=?',(job,))['payload'])['settings']
            self.assertEqual(saved['music_model'],'bf16');self.assertEqual(saved['music_overrides']['bf16']['num_inference_steps'],60)
            store.execute("UPDATE jobs SET status='done' WHERE id=?",(job,))
            retry=store.regenerate(chat['id']);saved=json.loads(store.one('SELECT payload FROM jobs WHERE id=?',(retry,))['payload'])['settings']
            self.assertEqual(saved['music_model'],'bf16');self.assertEqual(saved['music_quality'],'high')
            user=store.chat(chat['id'])['messages'][0]
            self.assertEqual(user['meta']['music_quality'],'high')

class QualityServiceTests(unittest.TestCase):
    def test_explicit_and_automatic_requests_capture_profiles_before_routing(self):
        from test_music import MusicTests
        fixture=MusicTests();fixture.setUp()
        try:
            high_path=Path(fixture.config['files']['model']).with_name('bf16-fixture.gguf');high_path.write_bytes(Path(fixture.config['files']['model']).read_bytes())
            high=fixture.app.external_model(fixture.config|{'name':'BF16 fixture','files':fixture.config['files']|{'model':str(high_path)}})
            profiles={'high':{'model':high['id'],'steps':60},'low':{'model':fixture.model['id'],'steps':32}}
            fixture.app.save_settings({'music_quality_profiles':profiles})
            for explicit in (True,False):
                chat=fixture.app.store.create_chat()
                body={'prompt':'genera una canzone','assistant':False,'music':explicit,'music_quality':'high'}
                job=fixture.app.send(chat['id'],body)['job_id']
                saved=json.loads(fixture.app.store.one('SELECT payload FROM jobs WHERE id=?',(job,))['payload'])['settings']
                self.assertEqual(saved['music_model'],high['id']);self.assertEqual(options(high,saved)['num_inference_steps'],60)
                fixture.app.store.execute("UPDATE jobs SET status='done' WHERE id=?",(job,))
        finally:fixture.tearDown()

if __name__=='__main__':unittest.main()

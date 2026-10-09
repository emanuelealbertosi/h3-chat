import base64
import copy
import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from h3chat.media_providers import MediaProviders
from h3chat.store import DEFAULTS, Store
from h3chat.video_engine import VideoEngine
from h3chat.video_options import apply_quality, options, quality, resolve_canvas
import test_video as fixture


class VideoQualityOptionsTests(unittest.TestCase):
    def test_high_preserves_saved_preset_and_medium_caps_only_size_and_steps(self):
        model={'id':'hybrid'}
        settings=DEFAULTS|{'video_overrides':{'hybrid':{'steps':12,'megapixels':.7,'seed':734,'aspect':'9:16','duration':15,'cfg':2,'attention':'sage'}}}
        original=copy.deepcopy(settings)
        high=options(model,settings,False)
        self.assertEqual(high,options(model,settings|{'_video_quality':'high'},False))
        medium=options(model,settings|{'_video_quality':'medium'},False)
        self.assertEqual((medium['steps'],medium['megapixels']),(8,.5))
        for key in ('duration','frames','aspect','cfg','seed','attention','offload','sampler','scheduler','shift_video','shift_audio'):
            self.assertEqual(high[key],medium[key],key)
        self.assertLess(medium['width']*medium['height'],high['width']*high['height'])
        self.assertEqual(settings,original)
        self.assertNotIn('quality',medium)  # Native worker accepts generation options only.

    def test_lower_custom_parameters_are_not_increased(self):
        parameters={'steps':4,'megapixels':.3,'duration':6}
        self.assertEqual(apply_quality(parameters,'medium'),parameters)
        self.assertEqual(apply_quality({},'high'),{})  # Remote server defaults stay untouched.
        self.assertEqual(apply_quality({},'medium'),{'steps':8,'megapixels':.5})

    def test_medium_keeps_keyframe_ratio_and_prompt_reference_format(self):
        opts=options({'id':'hybrid'},DEFAULTS|{'_video_quality':'medium'},False)
        for role,prompt,expected in [('keyframe','formato 16:9','4:3'),('reference','formato 9:16','9:16')]:
            result=resolve_canvas(opts,{'images':[{'index':1,'role':role,'seconds':0}]},[(1200,900)],prompt)
            self.assertEqual(result['aspect'],expected)
            a,b=map(int,expected.split(':'))
            self.assertEqual(result['output_width']*b,result['output_height']*a)
            self.assertLess(result['output_width']*result['output_height'],.53*1024**2)

    def test_invalid_quality_is_rejected(self):
        for value in ('low','Media',None,True,[],{}):
            with self.subTest(value=value),self.assertRaises(ValueError):quality(value)

    def test_local_worker_keeps_lipsync_minimum_and_records_quality(self):
        with tempfile.TemporaryDirectory() as directory:
            engine=VideoEngine();engine.root=engine.data=Path(directory)
            session=Mock();session.uses=0
            def send(request):
                self.assertEqual(request['options']['steps'],8)
                self.assertNotIn('quality',request['options'])
                Path(request['output']).write_bytes(b'\0\0\0\x18ftypmp42'+b'\0'*24)
            session.send.side_effect=send;session.wait.return_value={'parameters':{'steps':8}}
            engine.start_video=Mock(return_value=session)
            settings=DEFAULTS|{'_video_quality':'medium','video_overrides':{'hybrid':{'steps':4}}}
            plan={'prompt':'Test','images':[],'audios':[{'index':1,'role':'lipsync','start':0}]}
            with patch('h3chat.veda.preflight'):
                result=engine.generate_video({'id':'hybrid','name':'Hybrid'},settings,plan,[{'mime':'audio/wav','path':'audio.wav'}],'job',threading.Event(),Mock())
            self.assertEqual((result['generation']['quality'],result['generation']['megapixels'],result['generation']['steps']),('medium',.5,8))


class VideoQualitySnapshotTests(unittest.TestCase):
    setUp=fixture.VideoTests.setUp
    tearDown=fixture.VideoTests.tearDown

    def test_send_and_regenerate_preserve_profile_without_editing_admin_defaults(self):
        chat=self.app.store.create_chat()
        job_id=self.app.send(chat['id'],{'prompt':'Un tramonto','video':True,'assistant':False,'video_quality':'medium'})['job_id']
        job=self.app.store.one('SELECT * FROM jobs WHERE id=?',(job_id,))
        self.assertEqual(json.loads(job['payload'])['settings']['_video_quality'],'medium')
        self.assertEqual(self.app.store.chat(chat['id'])['messages'][0]['meta']['video_quality'],'medium')
        self.assertNotIn('_video_quality',self.app.store.settings())
        self.app.store.execute("UPDATE jobs SET status='done' WHERE id=?",(job_id,))
        regenerated=self.app.regenerate(chat['id'])['job_id']
        retry=self.app.store.one('SELECT payload FROM jobs WHERE id=?',(regenerated,))
        self.assertEqual(json.loads(retry['payload'])['settings']['_video_quality'],'medium')
        self.assertEqual(self.app.engine.session_key('video',self.model,DEFAULTS),self.app.engine.session_key('video',self.model,DEFAULTS|{'_video_quality':'medium'}))

    def test_old_clients_default_to_high_and_invalid_profile_never_enqueues(self):
        chat=self.app.store.create_chat()
        with self.assertRaises(ValueError):self.app.send(chat['id'],{'prompt':'Crea un video','assistant':False,'video_quality':'low'})
        self.assertEqual(self.app.store.all('SELECT id FROM jobs'),[])
        job_id=self.app.send(chat['id'],{'prompt':'Crea un video','assistant':False})['job_id']
        job=self.app.store.one('SELECT payload FROM jobs WHERE id=?',(job_id,))
        self.assertEqual(json.loads(job['payload'])['settings']['_video_quality'],'high')


class VideoQualityRemoteTests(unittest.TestCase):
    def test_remote_caps_preserve_sparse_high_and_do_not_leak_to_images(self):
        with tempfile.TemporaryDirectory() as directory:
            providers=MediaProviders(Store(Path(directory)))
            cfg=providers.save({'name':'Fixture','role':'video','adapter':'h3','base_url':'http://127.0.0.1:8790','model':'hybrid'})
            model=providers.model(cfg)
            video={'data':base64.b64encode(b'\0\0\0\x18ftypmp42'+b'\0'*24).decode(),'mime':'video/mp4','generation':{'steps':8,'megapixels':.5}}
            image={'data':base64.b64encode(b'\x89PNG\r\n\x1a\n'+b'fixture').decode(),'mime':'image/png'}
            cancel=Mock();cancel.wait.return_value=False
            for profile,overrides,plan,expected in [
                ('high',{}, {'prompt':'Test','images':[],'audios':[]},{}),
                ('medium',{}, {'prompt':'Test','images':[],'audios':[]},{'steps':8,'megapixels':.5}),
                ('medium',{'steps':4,'megapixels':.3}, {'prompt':'Test','images':[],'audios':[{'role':'lipsync'}]},{'steps':8,'megapixels':.3}),
                ('medium',{},None,{})]:
                with self.subTest(profile=profile,plan=plan),patch.object(providers.client,'exchange',side_effect=[{'id':'a'*32},{'status':'done','media':video if plan else image}]) as exchange:
                    result=providers.generate(model,DEFAULTS|{'_video_quality':profile,'video_overrides':{model['id']:overrides}},'Test',[],'job',cancel,Mock(),plan=plan)
                    self.assertEqual(exchange.call_args_list[0].kwargs['body']['parameters'],expected)
                    self.assertEqual(result['generation'].get('quality'),profile if plan else None)

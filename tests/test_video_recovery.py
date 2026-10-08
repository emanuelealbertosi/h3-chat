import ast,json,math,sys,tempfile,threading,unittest,wave
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock,patch
from h3chat.video_timeline import timeline,validate_audio_interval,tail_padding_samples
from h3chat.video_resume import checkpoint,save
from h3chat.video_engine import VideoEngine
from h3chat.store import Store,DEFAULTS
ROOT=Path(__file__).resolve().parents[1]

class RecoveryTests(unittest.TestCase):
    def test_only_subframe_final_tail_is_tolerated_at_audio_sample_precision(self):
        self.assertEqual(tail_padding_samples(714176,716000,48000,tail=True),1824)
        self.assertEqual(tail_padding_samples(716000,716000,48000),0)
        with self.assertRaises(ValueError):tail_padding_samples(714176,716000,48000)
        for count in (0,100,713000):
            with self.assertRaises(ValueError):tail_padding_samples(count,716000,48000,tail=True)
        self.assertEqual(tail_padding_samples(959,960,24000,tail=True),1)

    def test_interval_validation_runs_before_models_and_rejects_real_shortfall(self):
        validate_audio_interval(149.87866666666667,135,358/24,tail=True)
        with self.assertRaises(ValueError):validate_audio_interval(149.87866666666667,135,358/24)
        with self.assertRaises(ValueError):validate_audio_interval(149,135,358/24,tail=True)
        engine=VideoEngine();engine.scene_scripts=Mock();engine.generate_video=Mock()
        with tempfile.TemporaryDirectory() as tmp:
            engine.data=Path(tmp);audio={'id':'a','mime':'audio/wav','path':'track.wav'}
            plan={'prompt':'Synthetic','images':[],'audios':[{'index':1,'role':'lipsync','start':0},{'index':2,'role':'lipsync','start':0}]}
            with patch('h3chat.soundtrack.probe',return_value={'duration':1}):
                with self.assertRaisesRegex(ValueError,'troppo corto'):engine.generate_long_video({'id':'m'},{'_video_duration':42,'_video_soundtrack':audio,'_assistant':True},plan,[audio,{'id':'b','mime':'audio/wav','path':'short.wav'}],'job',threading.Event(),lambda _:None,prompt='Synthetic')
        engine.scene_scripts.assert_not_called();engine.generate_video.assert_not_called()

    def fixture(self,data,ident):
        folder=data/'outputs'/ident;folder.mkdir(parents=True)
        p={'width':640,'height':480,'canvas_width':640,'canvas_height':480,'aspect':'4:3','aspect_source':'image','format_image':1}
        plan={'prompt':'Synthetic film','images':[],'audios':[{'index':1,'role':'lipsync','start':0}]}
        outputs=[]
        for i in (1,2):
            path=folder/f'scene-{i:03d}/video.mp4';path.parent.mkdir();path.write_bytes(b'\x00\x00\x00\x18ftypisom');outputs.append(path.relative_to(data).as_posix())
        save(folder,{'timeline':timeline(42),'prompts':['first','second','last'],'plan':plan,'completed':2,'parameters':[p,p],'outputs':outputs,'model':'m'})
        return plan,outputs

    def test_recovers_only_missing_clip_with_visual_memory_and_full_audio(self):
        with tempfile.TemporaryDirectory() as tmp:
            data=Path(tmp).resolve();ident='a'*32;plan,outputs=self.fixture(data,ident)
            engine=VideoEngine();engine.data=data;engine.scene_scripts=Mock(side_effect=AssertionError('No replanning'));calls=[]
            def generate(model,settings,local,refs,job,cancel,stage,**kwargs):
                calls.append(kwargs['scene']);out=data/'outputs'/job/'video.mp4';out.parent.mkdir(parents=True);out.write_bytes(b'fixture')
                return {'path':out.relative_to(data).as_posix(),'generation':checkpoint(data,ident)['parameters'][0]}
            engine.generate_video=generate;audio={'id':'a','mime':'audio/wav','path':'track.wav'}
            settings={'_video_duration':42,'_video_soundtrack':audio,'_video_resume':ident,'_assistant':True}
            with patch('h3chat.soundtrack.compose',return_value={'duration':42}) as mux:
                result=engine.generate_long_video({'id':'m'},settings,plan,[audio],'b'*32,threading.Event(),lambda _:None,prompt='Synthetic')
            self.assertEqual(len(calls),1);self.assertEqual(calls[0]['index'],2);self.assertEqual(calls[0]['canvas']['aspect'],'4:3')
            self.assertEqual(calls[0]['resume_memory']['opening'],str(data/outputs[0]));self.assertEqual(calls[0]['resume_memory']['recent'],[str(data/p) for p in outputs])
            self.assertEqual(len(mux.call_args.args[1]),3);self.assertEqual(result['generation']['recovered_scenes'],2)
            new=json.loads((data/'outputs'/('b'*32)/'scenes.json').read_text());self.assertEqual(new['completed'],3);self.assertEqual(new['outputs'][:2],outputs)

    def test_regenerate_reuses_failed_checkpoint_but_completed_jobs_start_fresh(self):
        with tempfile.TemporaryDirectory() as tmp:
            store=Store(tmp);chat=store.create_chat()['id'];job=store.enqueue(chat,'Synthetic',[],DEFAULTS|{'_video':True})
            self.fixture(Path(tmp),job);store.execute("UPDATE jobs SET status='failed' WHERE id=?",(job,))
            resumed=store.regenerate(chat);payload=json.loads(store.one('SELECT payload FROM jobs WHERE id=?',(resumed,))['payload'])
            self.assertEqual(payload['settings']['_video_resume'],job)
            store.execute("UPDATE jobs SET status='done' WHERE id=?",(resumed,))
            fresh=store.regenerate(chat);payload=json.loads(store.one('SELECT payload FROM jobs WHERE id=?',(fresh,))['payload'])
            self.assertNotIn('_video_resume',payload['settings'])

    def test_resume_rejects_invented_picture_in_remaining_scene_before_gpu(self):
        with tempfile.TemporaryDirectory() as tmp:
            data=Path(tmp).resolve();ident='a'*32;plan,outputs=self.fixture(data,ident);folder=data/'outputs'/ident
            value=json.loads((folder/'scenes.json').read_text());value['prompts'][2]='Animate <Picture 1>.';save(folder,value)
            engine=VideoEngine();engine.data=data;engine.scene_scripts=Mock();engine.generate_video=Mock()
            audio={'id':'a','mime':'audio/wav','path':'track.wav'}
            settings={'_video_duration':42,'_video_soundtrack':audio,'_video_resume':ident,'_assistant':True}
            with self.assertRaisesRegex(ValueError,'scena 3.*Picture.*Nessuna nuova scena'):
                engine.generate_long_video({'id':'m'},settings,plan,[audio],'b'*32,threading.Event(),lambda _:None,prompt='Music video')
            engine.generate_video.assert_not_called();engine.scene_scripts.assert_not_called()
            self.assertEqual(checkpoint(data,ident)['outputs'],outputs)

    def test_legacy_final_scene_recovery_preserves_local_keyframe_time(self):
        with tempfile.TemporaryDirectory() as tmp:
            data=Path(tmp);ident='a'*32;plan,outputs=self.fixture(data,ident);folder=data/'outputs'/ident
            value=json.loads((folder/'scenes.json').read_text());value.pop('plan');value.pop('outputs');save(folder,value)
            failed=folder/'scene-003';failed.mkdir();local=plan|{'images':[{'index':1,'role':'keyframe','seconds':5}]}
            (failed/'video-plan.json').write_text(json.dumps({'plan':local}))
            recovered=checkpoint(data,ident);self.assertEqual(recovered['plan']['images'][0]['seconds'],35)
            with self.assertRaises(ValueError):checkpoint(data,'../private')

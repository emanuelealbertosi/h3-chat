import copy
import json
import threading
import unittest
from unittest.mock import Mock
from h3chat.video_timing import localize,shared_story
from h3chat.video_timeline import timeline,scene_plan
from h3chat.video_engine import VideoEngine
from h3chat.video_storyboard import validate,local_plan

class TimingTests(unittest.TestCase):
    def test_legacy_global_and_already_local_clocks_are_idempotent(self):
        scene=timeline(90)[1]
        original='00:15–00:21: Find keys. 00:21–00:27: Switch singer. 00:27–00:30: Reach stairs. Voice begins at 00:21.'
        expected='00:00–00:06: Find keys. 00:06–00:12: Switch singer. 00:12–00:15: Reach stairs. Voice begins at 00:06.'
        self.assertEqual(localize(original,scene),expected)
        self.assertEqual(localize(expected,scene),expected)
        self.assertEqual(localize(original,scene,basis='local'),expected)

    def test_explicit_basis_disambiguates_short_storyboard_shots(self):
        scene={'start':6,'duration':9}
        self.assertEqual(localize('00:07–00:09: Cut.',scene,basis='video'),'00:01–00:03: Cut.')
        self.assertEqual(localize('00:07–00:09: Cut.',scene,basis='local'),'00:07–00:09: Cut.')

    def test_source_offsets_fractional_times_and_seconds(self):
        scene=timeline(42)[1]
        self.assertEqual(localize('01:15–01:18.500: Dance.',scene,basis='source',audio_start=60),'00:00–00:03.5: Dance.')
        text='From 15 to 21 seconds search; at 21 s switch. A 3 second camera move.'
        self.assertEqual(localize(text,scene,basis='video'),'From 0 to 6 seconds search; at 6 s switch. A 3 second camera move.')
        self.assertEqual(localize('01:00:15,250–01:00:18: Dance.',scene,basis='source',audio_start=3600),'00:00.25–00:03: Dance.')

    def test_dialogue_reference_labels_and_aspect_ratio_are_not_timestamps(self):
        scene=timeline(90)[1]
        text='00:21: <d>[Italian] Alle 07:00 mi alzo</d>. Says "at 32 seconds". Use <Picture 1> and <Audio 1>, 16:9.'
        value=localize(text,scene)
        self.assertEqual(value,'00:06: <d>[Italian] Alle 07:00 mi alzo</d>. Says "at 32 seconds". Use <Picture 1> and <Audio 1>, 16:9.')

    def test_invalid_mixed_or_reversed_timing_is_not_silently_shifted(self):
        for text in ('00:02: Sing. 00:25: Run.','00:18–00:17: Run.','00:90: Run.','00:59: Run.'):
            with self.subTest(text=text),self.assertRaises(ValueError):localize(text,timeline(90)[1])

    def test_shared_timeline_filters_other_clips_and_clips_crossing_actions(self):
        text='subject_definitions: <Subject 1> from <Picture 1>. retention_analysis: <Audio 1> fully_copy. detailed_description: [Shot 1] 00:00–00:06: Wake. 00:06–00:18: Run. [Shot 2] 00:18–00:27: Sing <d>[Italian] parole</d>. 00:27–00:42: Finish. overall_soundscape: Music begins at 00:00.'
        result=shared_story(text,timeline(42)[1])
        self.assertIn('00:00–00:03: Run.',result);self.assertIn('00:03–00:12: Sing',result);self.assertIn('00:12–00:15: Finish.',result)
        self.assertNotIn('Wake.',result);self.assertNotIn('[Shot 1]',result)
        self.assertIn('<Picture 1>',result);self.assertIn('<Audio 1>',result);self.assertIn('<d>[Italian] parole</d>',result)

    def test_scene_plan_changes_narrative_only_and_keeps_audio_and_keyframe_offsets(self):
        plan={'prompt':'A film','images':[{'index':1,'role':'keyframe','seconds':21}],'audios':[{'index':1,'role':'lipsync','start':999}]}
        original=copy.deepcopy(plan)
        result=scene_plan(plan,timeline(90)[1],1,'00:21: Switch singer.',audio_start=60)
        self.assertIn('00:06: Switch singer.',result['prompt'])
        self.assertEqual(result['audios'][0]['start'],75)
        self.assertEqual(result['images'][0]['seconds'],6);self.assertEqual(plan,original)

    def test_structured_assistant_normalizes_video_source_and_local_in_same_batch(self):
        engine=VideoEngine()
        values=[{'prompt':'00:00–00:15: Start.','time_basis':'local'},
                {'prompt':'00:15–00:21: Keys. 00:21–00:30: Singer.','time_basis':'video'},
                {'prompt':'01:30–01:42: Finish.','time_basis':'source'}]
        engine.completion=Mock(return_value=(json.dumps({'scenes':values}),'stop'))
        settings={'context':80000,'video_prompt_max_tokens':3000,'_video_audio_start':60}
        plan={'prompt':'A film','images':[],'audios':[{'index':1,'role':'lipsync','start':0}]}
        result=engine.scene_scripts(plan,timeline(42),settings,threading.Event(),Mock(),prompt='Film times are global.')
        self.assertEqual(result[1],'00:00–00:06: Keys. 00:06–00:15: Singer.')
        self.assertEqual(result[2],'00:00–00:12: Finish.')
        self.assertEqual(engine.completion.call_count,1)

    def test_storyboard_normalizes_prompt_and_keeps_global_shot_end(self):
        refs=[{'mime':'audio/wav'}]
        value={'style':'Cinematic','shots':[
            {'end':6,'prompt':'00:00–00:06: Opening.','time_basis':'local','continuity':'cut','lip_sync':False,'images':[]},
            {'end':15,'prompt':'00:06–00:09: Dance. 00:09–00:15: Sing.','time_basis':'video','continuity':'cut','lip_sync':True,'images':[]}]}
        shots=validate(value,15,refs,'A film')['shots']
        self.assertEqual(shots[1]['end'],15);self.assertEqual(shots[1]['start'],6)
        self.assertEqual(shots[1]['prompt'],'00:00–00:03: Dance. 00:03–00:09: Sing.')
        plan,_=local_plan({'style':'Cinematic'},shots[1],{'audios':[{'index':1,'role':'reuse','start':0}]},refs,1,60)
        self.assertIn('00:00–00:03: Dance.',plan['prompt']);self.assertEqual(plan['audios'][0]['start'],66)

    def test_assistant_repairs_mixed_time_bases_before_accepting_scene(self):
        engine=VideoEngine()
        engine.completion=Mock(side_effect=[
            (json.dumps({'scenes':[{'prompt':'00:00–00:03: Start. 00:21–00:30: Sing.','time_basis':'local'}]}),'stop'),
            (json.dumps({'scenes':[{'prompt':'00:00–00:06: Start. 00:06–00:15: Sing.','time_basis':'local'}]}),'stop')])
        plan={'prompt':'A film','images':[],'audios':[]}
        result=engine.scene_scripts(plan,[timeline(30)[1]],{'context':80000,'video_prompt_max_tokens':3000},threading.Event(),Mock(),prompt='Keep the requested times.')
        self.assertEqual(result,['00:00–00:06: Start. 00:06–00:15: Sing.'])
        self.assertEqual(engine.completion.call_count,2)
        self.assertIn('Tempi fuori dal clip',engine.completion.call_args.args[0][0]['content'])

    def test_assistant_off_sends_only_matching_local_actions_through_orchestration(self):
        import tempfile
        from pathlib import Path
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as tmp:
            engine=VideoEngine();engine.data=Path(tmp);calls=[]
            audio={'id':'a','mime':'audio/wav','path':'song.wav'}
            plan={'prompt':'detailed_description: 00:00–00:15: Wake. 00:15–00:30: Drive.','images':[],'audios':[{'index':1,'role':'reuse','start':0}]}
            def generate(model,settings,local,refs,job,*args,**kwargs):
                calls.append(local)
                path=engine.data/'outputs'/job/'video.mp4';path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(b'fixture')
                return {'path':path.relative_to(engine.data).as_posix(),'generation':{'width':640,'height':480,'canvas_width':640,'canvas_height':480,'aspect':'4:3','aspect_source':'image'}}
            engine.generate_video=generate
            with patch('h3chat.soundtrack.compose',return_value={'duration':30}):
                engine.generate_long_video({}, {'_video_duration':30,'_video_soundtrack':audio,'_assistant':False},plan,[audio],'job',threading.Event(),Mock(),prompt='Original storyboard')
            self.assertEqual(len(calls),2)
            self.assertIn('00:00–00:15: Drive.',calls[1]['prompt']);self.assertNotIn('Wake.',calls[1]['prompt'])
            self.assertEqual([p['audios'][0]['start'] for p in calls],[0,15])

if __name__=='__main__':unittest.main()

import json,tempfile,threading,unittest
from pathlib import Path
from unittest.mock import Mock,patch
from h3chat.infographics import options,plan_regia,validate_motion,build
from h3chat.infographic_video import select,asset,source_time

class InfographicPlanningTests(unittest.TestCase):
    def plan(self):
        return {'title':'Corso','visual_direction':'Neon, Manrope, tre scene','delivery':'spot','music_style':'Ambient','jingle_lyrics':'','scenes':[{'title':'A','purpose':'Aprire','narration':'Impara a intervenire.'}]*3}
    def test_truncated_plan_retries_without_grammar_and_preserves_user_budget(self):
        engine=Mock();engine.completion.side_effect=[('{','length'),(json.dumps(self.plan()),'stop')]
        settings={'max_tokens':40000,'temperature':.2,'llm_timeout':1800,'context':80000}
        result=plan_regia(engine,[],'fonti',{'type':'object'},settings,threading.Event(),lambda _:None,3)
        self.assertEqual(len(result['scenes']),3);self.assertEqual(settings['max_tokens'],40000)
        calls=engine.completion.call_args_list;self.assertLess(calls[0].args[1]['max_tokens'],40000)
        self.assertIsNone(calls[1].kwargs['schema']);self.assertNotIn('fonti',str(calls[1].args[1]))
    def test_whitespace_loop_stops_early_and_malformed_retry_cannot_be_published(self):
        engine=Mock()
        def reply(*args,**kw):kw['on_text'](' '*1600)
        engine.completion.side_effect=reply
        with self.assertRaisesRegex(ValueError,'due tentativi'):plan_regia(engine,[],'',{}, {'max_tokens':40000,'temperature':.2},threading.Event(),lambda _:None,3)
        self.assertEqual(engine.completion.call_count,2)
    def test_invalid_scene_count_retries(self):
        engine=Mock();bad=self.plan();bad['scenes']=[];engine.completion.side_effect=[(json.dumps(bad),'stop'),(json.dumps(self.plan()),'stop')]
        self.assertEqual(len(plan_regia(engine,[],'',{}, {'max_tokens':40000,'temperature':.2},threading.Event(),lambda _:None,3)['scenes']),3)
    def test_repeated_phrase_detected_before_consuming_output_allowance(self):
        engine=Mock();count=[0]
        def reply(*args,**kw):
            count[0]+=1
            if count[0]==1:kw['on_text']('Una narrazione iniziale. '+ 'e vicino e lontano '*120)
            return json.dumps(self.plan()),'stop'
        engine.completion.side_effect=reply
        plan_regia(engine,[],'',{}, {'max_tokens':40000,'temperature':.2},threading.Event(),lambda _:None,3)
        self.assertEqual(count[0],2)

class VideoBackgroundTests(unittest.TestCase):
    def test_saved_pre_video_job_is_normalized_before_selecting_video(self):
        legacy={k:v for k,v in options().items() if not k.startswith('video_')}
        legacy.update(duration=40,scenes=4,images='provided')
        with tempfile.TemporaryDirectory() as tmp:
            app=Mock();app.data=Path(tmp);settings={'_infographic':legacy}
            with patch('h3chat.infographic_video.select',side_effect=RuntimeError('normalized')) as select_video:
                with self.assertRaisesRegex(RuntimeError,'normalized'):
                    build(app,{'id':'job'},{'media':[]},[],settings,{},threading.Event(),lambda _:None,Path(tmp)/'log',{})
                normalized=select_video.call_args.args[0]
                self.assertEqual(normalized['video_background'],'auto');self.assertEqual(normalized['video_fit'],'contain')
                self.assertEqual(normalized['duration'],40);self.assertEqual(normalized['scenes'],4)
                self.assertEqual(normalized['images'],'provided')
            self.assertNotIn('video_background',settings['_infographic'])
        self.assertIsNone(select(legacy,[]))
    def test_defaults_off_multiple_and_selected_attachment(self):
        a={'id':'one','mime':'video/mp4'};b={'id':'two','mime':'video/mp4'}
        self.assertEqual(select(options(),[a]),a);self.assertIsNone(select(options(value={'video_background':'off'}),[a]))
        with self.assertRaises(ValueError):select(options(),[a,b])
        self.assertEqual(select(options(value={'video_id':'two'}),[a,b]),b)
        with self.assertRaises(ValueError):select(options(value={'video_id':'other'}),[a])
    def test_asset_must_be_authorized_and_stay_in_workspace(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'uploads').mkdir();(root/'uploads/a.mp4').write_bytes(b'fixture')
            a={'id':'one','mime':'video/mp4','path':'uploads/a.mp4'}
            self.assertEqual(asset(root,[a],'one','video/mp4'),root/a['path'])
            for media,ident in (([a],'two'),([a|{'path':'../private.mp4'}],'one'),([a|{'path':'uploads/../../private.mp4'}],'one')):
                with self.assertRaises(ValueError):asset(root,media,ident,'video/mp4')
    def test_timeline_continues_and_loop_freeze_are_deterministic(self):
        self.assertAlmostEqual(source_time(17,15,'loop'),2)
        self.assertAlmostEqual(source_time(17,15,'freeze'),15-1e-6)
        with self.assertRaises(ValueError):options(value={'video_fit':'stretch'})
        with self.assertRaises(ValueError):validate_motion({'pages':[{}],'infographic':{'version':1,'durations':[5],'sfx':'none','transition':'cut','video':{'asset_id':'x'}}})

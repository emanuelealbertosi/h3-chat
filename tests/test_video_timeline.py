import unittest
from h3chat.video_timeline import timeline,scene_plan
from h3chat.soundtrack import select

class TimelineTests(unittest.TestCase):
    def test_full_orchestration_retains_audio_offsets_and_canvas(self):
        import json,tempfile,threading
        from pathlib import Path
        from unittest.mock import Mock,patch
        from h3chat.video_engine import VideoEngine
        audio={'id':'sound','name':'sound.wav','mime':'audio/wav','path':'sound.wav'}
        plan={'prompt':'A continuous film','images':[],'audios':[{'index':1,'role':'lipsync','start':0}]}
        with tempfile.TemporaryDirectory() as tmp:
            engine=VideoEngine();engine.data=Path(tmp);calls=[]
            def generate(model,settings,p,refs,job,cancel,stage,**kw):
                calls.append((p,kw['scene']));path=Path(tmp)/job/'video.mp4';path.parent.mkdir(parents=True);path.write_bytes(b'fixture')
                return {'path':path.relative_to(tmp).as_posix(),'generation':{'width':640,'height':480,'canvas_width':640,'canvas_height':480,'aspect':'4:3','aspect_source':'image','format_image':1}}
            engine.generate_video=generate
            with patch('h3chat.soundtrack.compose',return_value={'duration':42}) as mux:
                item=engine.generate_long_video({}, {'_video_duration':42,'_video_soundtrack':audio,'_assistant':False},plan,[audio],'job',threading.Event(),lambda _:None,prompt='Anima con audio')
            self.assertEqual([p['audios'][0]['start'] for p,s in calls],[0,15,30])
            self.assertEqual([s['duration'] for p,s in calls],[15,15,12])
            self.assertEqual(calls[1][1]['canvas']['aspect'],'4:3')
            self.assertEqual(item['generation']['scenes'],3);self.assertTrue(item['generation']['audio_preserved'])
            self.assertEqual(len(mux.call_args.args[1]),3)
            saved=json.loads((Path(tmp)/'outputs/job/scenes.json').read_text());self.assertEqual(saved['completed'],3)

    def test_audio_duration_splits_without_losing_tail(self):
        self.assertEqual([s['duration'] for s in timeline(42)],[15,15,12])
        self.assertEqual([s['start'] for s in timeline(42)],[0,15,30])
        self.assertGreaterEqual(sum(s['duration'] for s in timeline(30.01)),30.01)
        for x in (0,601,float('nan')):
            with self.assertRaises(ValueError):timeline(x)

    def test_explicit_reference_labels_and_global_timing_are_preserved(self):
        plan={'prompt':'Use <Picture 1> and <Audio 1>','images':[{'index':1,'role':'keyframe','seconds':0},{'index':2,'role':'keyframe','seconds':20}], 'audios':[{'index':1,'role':'lipsync','start':2}]}
        result=scene_plan(plan,timeline(42)[1],1)
        self.assertEqual(result['images'],[{'index':1,'role':'reference','seconds':0},{'index':2,'role':'keyframe','seconds':5}])
        self.assertEqual(result['audios'][0]['start'],15);self.assertEqual(result['audios'][0]['role'],'lipsync')
        self.assertEqual(plan['audios'][0]['start'],2)

    def test_soundtrack_selected_without_llm_and_negation(self):
        a={'id':'a','name':'voice.wav','mime':'audio/wav'};b={'id':'b','name':'song.mp3','mime':'audio/mpeg'}
        self.assertEqual(select('anima con audio 2',[a,b]),b)
        self.assertEqual(select('Manim',[a]),a)
        self.assertEqual(select('usa la traccia precedente',[],[{'media':[a]}]),a)
        self.assertIsNone(select('crea senza audio',[a]))
        self.assertIsNone(select('usa audio solo come riferimento',[a]))
        with self.assertRaises(ValueError):select('crea video',[a,b])

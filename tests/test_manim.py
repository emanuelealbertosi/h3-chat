import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch
from h3chat.manim_code import duration,validate_source,source_from_text
from h3chat.service import Service

ROOT=Path(__file__).resolve().parents[1]
CODE='from manim import *\nclass Helper: pass\nclass Demo(ThreeDScene):\n def construct(self):\n  self.add(Sphere()); self.wait(30)\n'

class SourceTests(unittest.TestCase):
    def test_full_python_three_d_and_helper_classes(self):
        self.assertEqual(source_from_text(CODE)['scene_name'],'Demo')
        self.assertEqual(validate_source({'title':'3D','code':CODE,'scene_name':'Demo'})['code'],CODE)
        # Imports and Python are intentionally allowed: OS isolation handles execution.
        self.assertIn('import',source_from_text(CODE)['code'])
    def test_syntax_and_scene_selection_errors(self):
        for code in ('class Broken:', 'print(1)',CODE+'\nclass Second(Scene): pass'):
            with self.assertRaises(ValueError):source_from_text(code)
        with self.assertRaises(ValueError):validate_source({'code':CODE,'scene_name':'Missing'})
    def test_explicit_duration_beats_preferences(self):
        for prompt,seconds in [('animazione di 30s',30),('Manim 30 secondi',30),('animation 1.5 minutes',90),('durata 2,5 secondi',2.5)]:
            self.assertEqual(duration(prompt,10),(seconds,True))
        self.assertEqual(duration('scena 3D',10),(10,False))
        for prompt in ('video 0s','video 601 secondi'):
            with self.assertRaises(ValueError):duration(prompt,8)
    def test_video_duration_never_silently_clamps_thirty_seconds(self):
        from h3chat.video_options import with_prompt_duration,prompt_duration
        settings={'video_model':'hybrid','video_overrides':{'hybrid':{'duration':10,'steps':12}}}
        adjusted=with_prompt_duration(settings,'anima questa immagine per 15s')
        self.assertEqual(adjusted['video_overrides']['hybrid']['duration'],15)
        self.assertEqual(settings['video_overrides']['hybrid']['duration'],10)
        self.assertIsNone(prompt_duration('immagine 2 a 5 secondi'))
        with self.assertRaisesRegex(ValueError,'15 secondi'):prompt_duration('crea una animazione di 30s')
    def test_legacy_storyboard_stays_usable(self):
        scene={'objects':[{'type':'circle'}]}
        self.assertEqual(source_from_text(json.dumps(scene)),scene)

class FlowTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.app=Service(ROOT,self.tmp.name,start_worker=False)
        self.model={'id':'fixture','name':'Fixture','capabilities':['chat'],'files':[],'vision':{'enabled':False}}
    def tearDown(self):self.app.close();self.tmp.cleanup()
    def job(self,body):
        chat=self.app.store.create_chat()
        with patch.object(self.app.engine,'require_model',return_value=self.model):ticket=self.app.send(chat['id'],body)
        return self.app.store.one('SELECT * FROM jobs WHERE id=?',(ticket['job_id'],))
    def render(self,worker,request,*args,**kwargs):
        target=Path(request['output'])/'animation.mp4';target.write_bytes(b'fixture')
        self.options=request['options'];self.worker=worker
        return {'path':str(target),'duration':next(self.durations),'sandbox':'fixture'}
    def execute(self,job,completion=None):
        with patch.object(self.app.engine,'require_model',return_value=self.model),patch.object(self.app.engine,'start_llama'),patch.object(self.app.engine,'completion',side_effect=completion) as llm,patch.object(self.app.engine,'tool_call',side_effect=self.render),patch('h3chat.manim_artifact.status',return_value={'lab':{'ready':True},'latex':{'ready':True}}):
            self.app.execute_job(job,threading.Event())
        return self.app.store.messages(job['chat_id'])[-1],llm
    def test_free_source_no_second_llm_canvas_and_exports(self):
        self.durations=iter([30]);job=self.job({'prompt':'Renderizza Manim 30s','lab':'manim','lab_source':CODE,'canvas':True})
        answer,llm=self.execute(job)
        self.assertEqual(answer['status'],'done');llm.assert_not_called()
        self.assertEqual(self.options['duration'],30);self.assertEqual(self.worker,'manim-worker.py')
        self.assertEqual(answer['media'],[]);artifact=answer['meta']['artifact']
        self.assertIn('manim-python',artifact['content']);self.assertTrue(any(m['name']=='scena.py' for m in artifact['media']))
    def test_generated_duration_difference_preserves_video_without_extra_llm(self):
        self.durations=iter([28]);source={'title':'Demo','scene_name':'Demo','code':CODE}
        job=self.job({'prompt':'crea animazione Manim di 20s','canvas':False,'think_level':'high'})
        answer,llm=self.execute(job,[(json.dumps(source),'stop')])
        self.assertEqual(answer['status'],'done');self.assertEqual(llm.call_count,1)
        self.assertEqual(llm.call_args.args[1]['think_level'],'high')
        self.assertEqual(answer['meta']['manim_duration'],28);self.assertEqual(answer['meta']['manim_repairs'],0)
        self.assertIn('28.0 s',answer['meta']['manim_timing_note']);self.assertTrue(any(m['mime']=='video/mp4' for m in answer['media']))
        self.assertIn('Required total timeline: 20',llm.call_args_list[0].args[0][-1]['content'])
    def test_manual_duration_difference_preserves_source_and_publishes_video(self):
        self.durations=iter([10]);job=self.job({'prompt':'renderizza Manim 30 secondi','lab':'manim','lab_source':CODE,'canvas':True})
        answer,llm=self.execute(job)
        self.assertEqual(answer['status'],'done');self.assertIn('10.0 s',answer['meta']['manim_timing_note'])
        self.assertTrue(any(m['mime']=='video/mp4' for m in answer['meta']['artifact']['media']))
        self.assertIn(CODE,answer['meta']['artifact']['content']);llm.assert_not_called()
    def test_recover_legacy_duration_error_without_rerender_or_overwriting_new_canvas(self):
        from h3chat.manim_artifact import recover
        job=self.job({'prompt':'Manim 20s','lab':'manim','lab_source':CODE,'canvas':True})
        folder=self.app.data/'outputs'/job['id'];folder.mkdir(parents=True)
        (folder/'animation.mp4').write_bytes(b'\0\0\0\x18ftypisom'+b'synthetic'*20)
        artifact={'title':'Scena precedente','content':'```manim-python\n'+CODE+'\n```','media':[]}
        self.app.store.update_answer(job,'','failed',[],{'intent':'manim','canvas':True,'artifact':artifact,'error':'Durata errata: il video dura 28.00 s; richiesti 20 s. Correggi i tempi.'})
        self.app.store.execute("UPDATE jobs SET status='failed' WHERE id=?",(job['id'],))
        self.app.store.canvas_history.save(job['chat_id'],artifact,key='job:'+job['id'],message_id=job['message_id'])
        self.app.store.canvas_history.save(job['chat_id'],{'title':'Documento successivo','content':'Da conservare','media':[]},key='later')
        with patch.object(self.app.engine,'tool_call',side_effect=AssertionError('Must not render')):recover(self.app,job['chat_id'],job['message_id'])
        answer=self.app.store.messages(job['chat_id'])[-1];self.assertEqual(answer['status'],'done')
        self.assertNotIn('error',answer['meta']);self.assertEqual(answer['meta']['manim_duration'],28)
        self.assertTrue(any(x['mime']=='video/mp4' for x in answer['meta']['artifact']['media']))
        self.assertEqual(self.app.store.canvas_history.get(job['chat_id'])['content'],'Da conservare')
        with self.assertRaises(ValueError):recover(self.app,'other-chat',job['message_id'])

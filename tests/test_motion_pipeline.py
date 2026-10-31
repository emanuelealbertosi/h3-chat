import copy,json,threading,unittest
from unittest.mock import patch
import test_visual_models as fixture
from h3chat.slides import PREFIX,validate_content
from h3chat.infographic_storyboard import EXAMPLE
from h3chat.infographics import enqueue_render

class MotionPipelineTests(unittest.TestCase):
    setUp=fixture.VisualModelsTests.setUp
    tearDown=fixture.VisualModelsTests.tearDown
    def test_scene_pipeline_saves_graph_and_reexport_without_new_llm(self):
        chat=self.app.store.create_chat()['id'];before=self.app.store.settings()
        ticket=self.app.send(chat,{'prompt':'Crea infografica con livelli e camera','lab':'infographic','rag':False,'infographic':{'animation_engine':'motion','format':'16:9','duration':20,'scenes':2,'voice':False,'music':'none','images':'auto','output':'static'}})
        job=self.app.store.one('SELECT * FROM jobs WHERE id=?',(ticket['job_id'],));plan={'title':'Dati','visual_direction':'Superfici chiare e accenti ciano','delivery':'serious','music_style':'','jingle_lyrics':'','scenes':[{'title':'Una scena','purpose':'Spiegare','narration':'I servizi usano dati.'} for _ in range(2)]}
        with patch.object(self.app.engine,'prepare'),patch.object(self.app.engine,'prepare_tools',side_effect=lambda h,*a,**k:(h,{},[],[])),patch.object(self.app.engine,'start_llama'),patch.object(self.app.engine,'stop'),patch.object(self.app.engine,'completion',side_effect=[(json.dumps(plan),'stop'),(json.dumps(EXAMPLE),'stop'),(json.dumps(EXAMPLE),'stop')]) as complete,patch.object(self.app.engine,'generate') as generate,patch('h3chat.voice.synthesize') as voice,patch.object(self.app.engine,'tool_call',return_value={'pages':[{'error':None}]}) as cpu_check:
            self.app.execute_job(job,threading.Event())
        status=self.app.store.one('SELECT status,error FROM jobs WHERE id=?',(ticket['job_id'],));self.assertEqual(status['status'],'done',status['error']);self.assertEqual(complete.call_count,3);generate.assert_not_called();voice.assert_not_called()
        artifact=self.app.store.canvas_history.get(chat);deck=json.loads(artifact['content'][len(PREFIX):-4]);self.assertEqual(deck['infographic']['scene_format_version'],2);self.assertEqual(deck['infographic']['durations'],[10,10]);self.assertTrue(all(p['status']=='ready' and p['motion_scene']['camera']['keyframes'] for p in deck['pages']));validate_content(artifact['content'],artifact['media']);self.assertEqual(self.app.store.settings(),before)
        with patch.object(self.app.engine,'completion') as complete,patch('h3chat.voice.synthesize') as voice:
            render=enqueue_render(self.app,chat,{'artifact_id':artifact['id']})
        snapshot=json.loads(self.app.store.one('SELECT payload FROM jobs WHERE id=?',(render['job_id'],))['payload'])['settings']['_infographic_render'];self.assertEqual(snapshot['deck'],deck);complete.assert_not_called();voice.assert_not_called()

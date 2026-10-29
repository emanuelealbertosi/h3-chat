import importlib.util,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from h3chat.agent_online_video import youtube_url
from h3chat.agent_tools import validate,permission
from h3chat.agent_state import DEFAULTS
import test_agent_runtime as fixture
from test_agent_runtime import decision

class OnlineVideoURLs(unittest.TestCase):
    def test_single_video_is_preserved_but_playlist_and_tracking_removed(self):
        canonical='https://www.youtube.com/watch?v=Q3H6yRTCPJE'
        for url in (canonical+'&list=RDQ3H6yRTCPJE&start_radio=1','https://youtu.be/Q3H6yRTCPJE?t=3','https://m.youtube.com/shorts/Q3H6yRTCPJE'):
            self.assertEqual(youtube_url(url),canonical)
        for url in ('file:///secret','https://youtube.com.attacker.test/watch?v=Q3H6yRTCPJE','https://youtube.com/playlist?list=xyz','https://user:pass@youtube.com/watch?v=Q3H6yRTCPJE','https://youtube.com:8788/watch?v=Q3H6yRTCPJE'):
            with self.subTest(url=url),self.assertRaises(ValueError):youtube_url(url)

    def test_video_download_is_not_a_gpu_generation_permission(self):
        permission(DEFAULTS,'download_online_video',{'url':'https://youtu.be/Q3H6yRTCPJE'})
        validate('download_online_video',{'url':'https://youtu.be/Q3H6yRTCPJE','max_height':720})
        with self.assertRaises(ValueError):validate('download_online_video',{'url':'https://youtu.be/Q3H6yRTCPJE','cookies_from_browser':'edge'})

class OperationalCompletion(unittest.TestCase):
    setUp=fixture.AgentTests.setUp
    tearDown=fixture.AgentTests.tearDown
    ticket=fixture.AgentTests.ticket
    run_job=fixture.AgentTests.run_job

    def test_capabilities_only_finish_gets_one_concrete_method_review(self):
        chat,job=self.ticket('agent: Scarica il file richiesto',confirm_writes=False)
        calls=[]
        def completion(messages,*args,**kwargs):
            state=json.loads(messages[-1]['content']);calls.append(state)
            if len(calls)==1:return decision('get_agent_capabilities')
            return decision('finish',message='Il risultato non è stato ancora scaricato.')
        self.run_job(job,completion)
        self.assertEqual(len(calls),3);self.assertIn('completion_feedback',calls[-1])
        from h3chat.agent_state import load
        state=load(self.app,chat,job['id']);self.assertEqual(state['status'],'done');self.assertTrue(state['completion_reviewed'])
        self.assertFalse(any(a['tool']=='computer_run' for a in state['actions']))

"""Human answers resume the same run, never grant permissions or duplicate jobs."""
import json
import unittest
import test_agent_runtime as fixture
from test_agent_runtime import decision
from h3chat import agent_state


class AgentQuestions(unittest.TestCase):
    setUp=fixture.AgentTests.setUp
    tearDown=fixture.AgentTests.tearDown
    ticket=fixture.AgentTests.ticket
    run_job=fixture.AgentTests.run_job

    def test_capabilities_distinguish_scope_and_missing_interactive_tools(self):
        from h3chat.agent_capabilities import snapshot
        from h3chat.agent_state import DEFAULTS
        h3=snapshot(DEFAULTS,{'_web':False})
        self.assertFalse(h3['code_execution']);self.assertNotIn('computer_run',h3['tools'])
        sandbox=snapshot(DEFAULTS|{'scope':'sandbox'}, {'_web':True})
        self.assertTrue(sandbox['code_execution']);self.assertIn('computer_run',sandbox['tools'])
        self.assertTrue(sandbox['web_enabled']);self.assertFalse(sandbox['desktop_mouse_keyboard'])
        self.assertFalse(sandbox['interactive_browser']);self.assertFalse(sandbox['planning_roles']['independent_tool_execution'])

    def waiting(self):
        chat,job=self.ticket('agent: Chiedimi quante slide preparare',confirm_writes=False)
        self.run_job(job,lambda *a,**kw:decision('ask_user',{'question':'Quante slide vuoi?','options':['5','10']}))
        state=agent_state.load(self.app,chat,job['id'])
        self.assertEqual(state['status'],'awaiting_input')
        self.assertEqual(state['actions'][0]['status'],'awaiting_input')
        self.assertEqual(agent_state.public(state)['actions'][0]['question']['options'],['5','10'])
        return chat,job,state['actions'][0]

    def test_answer_continues_same_run_and_is_an_observation(self):
        chat,job,action=self.waiting()
        body={'action_id':action['id'],'decision':'answer','answer':'Cinque, con esempi'}
        result=agent_state.resume(self.app,chat,job['id'],body)
        self.assertEqual(agent_state.resume(self.app,chat,job['id'],body)['job_id'],result['job_id'])
        continued=self.app.store.one('SELECT * FROM jobs WHERE id=?',(result['job_id'],))
        def complete(messages,*args,**kwargs):
            self.assertIn('Cinque, con esempi',json.dumps(messages,ensure_ascii=False))
            return decision('finish',message='Risposta ricevuta.')
        self.run_job(continued,complete)
        state=agent_state.load(self.app,chat,job['id'])
        self.assertEqual(state['status'],'done');self.assertEqual(len(state['actions']),1)
        self.assertEqual(state['actions'][0]['result']['answer'],'Cinque, con esempi')

    def test_missing_stale_and_invalid_answers_do_not_resume(self):
        chat,job,action=self.waiting()
        for body in ({},{'decision':'approve','action_id':action['id']},
                     {'decision':'answer','action_id':'f'*32,'answer':'5'},
                     {'decision':'answer','action_id':action['id'],'answer':' '},
                     {'decision':'answer','action_id':action['id'],'answer':'x'*4001}):
            with self.subTest(body=str(body)[:80]),self.assertRaises(ValueError):agent_state.resume(self.app,chat,job['id'],body)
        self.assertEqual(agent_state.load(self.app,chat,job['id'])['status'],'awaiting_input')

    def test_answer_does_not_broaden_permissions(self):
        chat,job,action=self.waiting()
        with self.assertRaisesRegex(ValueError,'permessi'):
            agent_state.resume(self.app,chat,job['id'],{'decision':'answer','action_id':action['id'],'answer':'5','limits':{'allow_images':True}})
        state=agent_state.load(self.app,chat,job['id'])
        self.assertFalse(state['config']['allow_images']);self.assertEqual(state['status'],'awaiting_input')

    def test_reject_stops_the_run(self):
        chat,job,action=self.waiting()
        agent_state.resume(self.app,chat,job['id'],{'decision':'reject','action_id':action['id']})
        self.assertEqual(agent_state.load(self.app,chat,job['id'])['status'],'rejected')
        with self.assertRaises(ValueError):agent_state.resume(self.app,chat,job['id'],{'decision':'answer','action_id':action['id'],'answer':'5'})

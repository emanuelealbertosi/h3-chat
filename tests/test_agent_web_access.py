import json,unittest
from unittest.mock import patch
import test_agent_runtime as fixture
from test_agent_runtime import decision
from h3chat import agent_state


class WebOnDemand(unittest.TestCase):
    setUp=fixture.AgentTests.setUp
    tearDown=fixture.AgentTests.tearDown
    ticket=fixture.AgentTests.ticket
    run_job=fixture.AgentTests.run_job

    @staticmethod
    def complete(messages,*args,**kwargs):
        state=json.loads(messages[-1]['content'])
        return decision('finish',message='Fonte letta.') if state['observations'] else decision('read_web_page',{'url':'https://example.com/'},'Leggo la fonte richiesta.')

    def test_web_off_asks_once_then_human_approval_resumes_same_action(self):
        chat,job=self.ticket('agent: Leggi la pagina scelta',confirm_writes=True)
        before=self.app.store.settings()
        with patch('h3chat.web_search.fetch',return_value='<html><p>Verified fixture text</p></html>') as fetch:
            self.run_job(job,self.complete);fetch.assert_not_called()
            state=agent_state.load(self.app,chat,job['id']);self.assertEqual(state['status'],'awaiting_approval')
            action=state['actions'][0];self.assertEqual(action['enable_web']['scope'],'this_run_only')
            self.assertTrue(agent_state.public(state)['actions'][0]['enable_web'])
            with self.assertRaises(ValueError):agent_state.resume(self.app,chat,job['id'],{'decision':'approve','action_id':'f'*32})
            result=agent_state.resume(self.app,chat,job['id'],{'decision':'approve','action_id':action['id']})
            next_job=self.app.store.one('SELECT * FROM jobs WHERE id=?',(result['job_id'],));self.assertTrue(json.loads(next_job['payload'])['settings']['_web'])
            self.run_job(next_job,self.complete);self.assertEqual(fetch.call_count,1)
        state=agent_state.load(self.app,chat,job['id']);self.assertEqual(state['status'],'done');self.assertEqual(len(state['actions']),1)
        self.assertEqual(state['web_grants'][0]['source'],'human_approval');self.assertEqual(before,self.app.store.settings())

    def test_autoapprove_enables_for_run_without_changing_global_preferences(self):
        chat,job=self.ticket('agent: Leggi la fonte necessaria',confirm_writes=False)
        before=self.app.store.settings()
        with patch('h3chat.web_search.fetch',return_value='<p>Verified public source</p>') as fetch:self.run_job(job,self.complete)
        state=agent_state.load(self.app,chat,job['id']);self.assertEqual(state['status'],'done');self.assertTrue(state['web_enabled']);fetch.assert_called_once()
        self.assertEqual(state['web_grants'][0]['source'],'autoapprove_policy');self.assertEqual(before,self.app.store.settings())

    def test_human_offline_instruction_and_disabled_policy_are_not_overridden(self):
        for prompt,extra in (('agent: Lavora senza internet',{}),('agent: Leggi una fonte',{'web_on_demand':False})):
            with self.subTest(prompt=prompt):
                chat,job=self.ticket(prompt,confirm_writes=False,**extra)
                with patch('h3chat.web_search.fetch') as fetch:self.run_job(job,self.complete);fetch.assert_not_called()
                state=agent_state.load(self.app,chat,job['id']);self.assertFalse(state.get('web_enabled',False));self.assertEqual(state['actions'][0]['status'],'failed')

    def test_rejection_does_not_activate_web(self):
        chat,job=self.ticket('agent: Leggi la pagina',confirm_writes=True)
        self.run_job(job,self.complete);state=agent_state.load(self.app,chat,job['id'])
        agent_state.resume(self.app,chat,job['id'],{'decision':'reject','action_id':state['actions'][0]['id']})
        state=agent_state.load(self.app,chat,job['id']);self.assertEqual(state['status'],'rejected');self.assertFalse(state.get('web_enabled',False))

"""Human credential boundary, durable prepared IDs and Agent continuation."""
import json
import threading
import unittest
from unittest.mock import patch
import test_agent_runtime as fixture
from test_agent_runtime import decision
from h3chat import agent_state
from h3chat.agent_connection import submit
from h3chat.agent_tools import validate

SECRET='fixture-key-only-in-human-dialog-9151'
CONFIG={'name':'Server di prova','base_url':'http://127.0.0.1:9/v1','model':'example-model','format':'json_object'}

class AgentConnectionTests(unittest.TestCase):
    setUp=fixture.AgentTests.setUp
    tearDown=fixture.AgentTests.tearDown
    ticket=fixture.AgentTests.ticket
    run_job=fixture.AgentTests.run_job

    def waiting(self):
        chat,job=self.ticket('agent: Configura il server di prova')
        self.run_job(job,lambda *a,**kw:decision('configure_api',CONFIG))
        state=agent_state.load(self.app,chat,job['id']);self.assertEqual(state['status'],'awaiting_connection');self.assertEqual(self.app.providers.list(),[])
        return chat,job,state['actions'][0]

    def body(self,action,**extra):return {'action_id':action['id'],'api_key':SECRET,**extra}

    def test_human_key_is_protected_and_never_enters_job_prompt_checkpoint_or_observation(self):
        chat,job,action=self.waiting();original=self.app.store.settings();result=submit(self.app,chat,job['id'],self.body(action))
        self.assertEqual(len(self.app.providers.list()),1);self.assertEqual(self.app.store.settings(),original)
        state=agent_state.load(self.app,chat,job['id']);self.assertEqual(state['actions'][0]['status'],'done');self.assertTrue(state['actions'][0]['result']['has_key'])
        self.assertNotIn(SECRET,json.dumps(state));row=self.app.store.one('SELECT payload FROM jobs WHERE id=?',(result['job_id'],));self.assertNotIn(SECRET,row['payload'])
        stored=self.app.store.one('SELECT secret FROM api_providers WHERE id=?',(result['provider_id'],))['secret'];self.assertNotEqual(stored,SECRET)
        config,key=self.app.providers.credentials(result['provider_id']);self.assertEqual(key,SECRET)
        self.assertNotIn(SECRET,json.dumps(self.app.store.messages(chat)))
        self.run_job(self.app.store.one('SELECT * FROM jobs WHERE id=?',(result['job_id'],)),lambda *a,**kw:decision('finish',message='Connessione salvata.'))
        self.assertEqual(agent_state.load(self.app,chat,job['id'])['status'],'done')
        duplicate=submit(self.app,chat,job['id'],self.body(action));self.assertTrue(duplicate['reused']);self.assertEqual(len(self.app.providers.list()),1)

    def test_agent_cannot_supply_secret_or_bypass_pending_human_input(self):
        with self.assertRaises(ValueError):validate('configure_api',CONFIG|{'api_key':SECRET})
        chat,job,action=self.waiting()
        with self.assertRaisesRegex(ValueError,'finestra'):agent_state.resume(self.app,chat,job['id'],{})
        other=self.app.store.create_chat()['id']
        with self.assertRaises(ValueError):submit(self.app,other,job['id'],self.body(action))
        with self.assertRaises(ValueError):submit(self.app,chat,job['id'],self.body(action,config={'api_key':SECRET}))
        self.assertEqual(self.app.providers.list(),[])
        agent_state.resume(self.app,chat,job['id'],{'decision':'reject','action_id':action['id']})
        with self.assertRaises(ValueError):submit(self.app,chat,job['id'],self.body(action))

    def test_explicit_new_brain_is_scoped_to_run(self):
        chat,job,action=self.waiting();before=self.app.store.settings()['chat_model']
        result=submit(self.app,chat,job['id'],self.body(action,use_for_run=True))
        queued=json.loads(self.app.store.one('SELECT payload FROM jobs WHERE id=?',(result['job_id'],))['payload'])
        self.assertEqual(queued['settings']['chat_model'],result['provider_id']);self.assertEqual(self.app.store.settings()['chat_model'],before)

    def test_connection_test_is_explicit_and_does_not_save_or_complete(self):
        chat,job,action=self.waiting()
        with patch.object(self.app,'provider_request',return_value={'ok':True,'message':'Test simulato'}) as test:
            result=submit(self.app,chat,job['id'],self.body(action,operation='test'))
        self.assertEqual(result['message'],'Test simulato');self.assertEqual(test.call_args.args[1],'test');self.assertEqual(test.call_args.args[0]['api_key'],SECRET)
        self.assertEqual(self.app.providers.list(),[]);self.assertEqual(agent_state.load(self.app,chat,job['id'])['status'],'awaiting_connection')

    def test_lost_checkpoint_after_save_can_retry_same_connection_id(self):
        chat,job,action=self.waiting()
        with patch('h3chat.agent_state.save',side_effect=OSError('Simulated checkpoint failure')):
            with self.assertRaises(OSError):submit(self.app,chat,job['id'],self.body(action))
        self.assertEqual(len(self.app.providers.list()),1)
        result=submit(self.app,chat,job['id'],self.body(action,api_key=''))
        self.assertEqual(result['provider_id'],action['connection']['id']);self.assertEqual(len(self.app.providers.list()),1)
        self.assertEqual(self.app.providers.credentials(result['provider_id'])[1],SECRET)

if __name__=='__main__':unittest.main()

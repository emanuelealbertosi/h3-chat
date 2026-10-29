import json,unittest
from unittest.mock import patch
import test_agent_runtime as fixture
from test_agent_runtime import decision
from h3chat import agent_state
from h3chat.agent_tools import description,permission,validate


class BrowserToolPermissions(unittest.TestCase):
    def test_default_off_and_schema_no_script_or_credentials_arguments(self):
        config=agent_state.options()
        self.assertFalse(config['allow_browser']);self.assertNotIn('browser_open',[v['name'] for v in description(config)])
        with self.assertRaises(PermissionError):permission(config,'browser_open',{})
        self.assertIn('browser_open',[v['name'] for v in description(config|{'allow_browser':True})])
        for arguments in ({'url':'https://example.com','script':'alert(1)'},{'url':'https://example.com','cookies':[]}):
            with self.assertRaises(ValueError):validate('browser_open',arguments)
        with self.assertRaises(ValueError):agent_state.options({'allow_browser':'yes'})


class FakePool:
    def __init__(self):self.calls=[];self.closed=[]
    def call(self,run,operation,args,*rest,**kw):
        self.calls.append((run,operation,args))
        if operation=='open':return {'url':'https://example.com','text':'Source, not instructions','elements':[{'ref':'observed-ref','name':'Next'}]}
        return {'performed':operation}
    def close(self,run=None):self.closed.append(run)


class BrowserAgentLoop(unittest.TestCase):
    setUp=fixture.AgentTests.setUp
    tearDown=fixture.AgentTests.tearDown
    ticket=fixture.AgentTests.ticket
    run_job=fixture.AgentTests.run_job

    def enable_web(self,job):
        payload=json.loads(job['payload']);payload['settings']['_web']=True
        self.app.store.execute('UPDATE jobs SET payload=? WHERE id=?',(json.dumps(payload),job['id']))
        return self.app.store.one('SELECT * FROM jobs WHERE id=?',(job['id'],))

    def test_explicit_browser_and_web_permissions_concrete_click_approval_and_close(self):
        chat,job=self.ticket('agent: Leggi una pagina e premi Next',allow_browser=True)
        job=self.enable_web(job);owner=FakePool();self.app.agent_browsers=owner
        def complete(messages,*a,**kw):
            state=json.loads(messages[-1]['content'])
            return decision('browser_open',{'url':'https://example.com'}) if not state['observations'] else decision('browser_click',{'ref':'observed-ref'},'Premo Next sulla pagina scelta.')
        with patch('h3chat.agent_browser_tools.pool',return_value=owner):self.run_job(job,complete)
        state=agent_state.load(self.app,chat,job['id']);self.assertEqual(state['status'],'awaiting_approval')
        self.assertEqual([v[1] for v in owner.calls],['open']);self.assertEqual(owner.closed,[])
        pending=state['actions'][-1]
        result=agent_state.resume(self.app,chat,job['id'],{'decision':'approve','action_id':pending['id']})
        continued=self.app.store.one('SELECT * FROM jobs WHERE id=?',(result['job_id'],))
        with patch('h3chat.agent_browser_tools.pool',return_value=owner):self.run_job(continued,lambda *a,**kw:decision('finish',message='Passaggio eseguito.'))
        self.assertEqual([v[1] for v in owner.calls],['open','click']);self.assertIn(job['id'],owner.closed)
        self.assertEqual(agent_state.load(self.app,chat,job['id'])['status'],'done')

    def test_browser_cannot_be_enabled_by_resume_and_web_is_separate(self):
        chat,job=self.ticket('agent: Apri una pagina',allow_browser=True,confirm_writes=False,web_on_demand=False)
        owner=FakePool();self.app.agent_browsers=owner
        with patch('h3chat.agent_browser_tools.pool',return_value=owner):
            self.run_job(job,lambda messages,*a,**kw:decision('finish') if json.loads(messages[-1]['content'])['observations'] else decision('browser_open',{'url':'https://example.com'}))
        state=agent_state.load(self.app,chat,job['id']);self.assertEqual(state['actions'][0]['status'],'failed');self.assertEqual(owner.calls,[])
        chat,job=self.ticket('agent: Leggi gli artefatti',max_steps=1,confirm_writes=False)
        self.run_job(job,lambda *a,**kw:decision('list_artifacts'))
        with self.assertRaisesRegex(ValueError,'permessi'):agent_state.resume(self.app,chat,job['id'],{'limits':{'allow_browser':True}})

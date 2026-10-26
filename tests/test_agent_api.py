"""Actual Agent HTTP model transport against a local provider stub only."""
import json
import threading
import unittest
import test_api_providers as api_fixture
from test_agent_runtime import decision
from h3chat.agent_state import load

class AgentStub(api_fixture.Stub):
    def do_POST(self):
        body=json.loads(self.rfile.read(int(self.headers['Content-Length'])));self.server.calls.append((self.path,dict(self.headers),body))
        data=json.loads(body['messages'][-1]['content'])
        text=decision('finish',message='Elenco consultato.')[0] if data['observations'] else decision('list_artifacts')[0]
        if self.server.mode=='bad':text='{}'
        self.send_response(200);self.send_header('Content-Type','text/event-stream');self.end_headers()
        self.wfile.write(('data: '+json.dumps({'choices':[{'delta':{'content':text},'finish_reason':'stop'}]})+'\n\ndata: [DONE]\n\n').encode());self.wfile.flush()

class AgentApiTests(unittest.TestCase):
    setUp=api_fixture.ApiTests.setUp
    tearDown=api_fixture.ApiTests.tearDown
    def run_agent(self):
        self.server.RequestHandlerClass=AgentStub
        model=self.app.provider_request(self.config)
        self.app.save_settings({'chat_model':model['id'],'context':32768,'max_tokens':2200})
        chat=self.app.store.create_chat()['id'];ticket=self.app.send(chat,{'prompt':'agent: Elenca gli artefatti','rag':False})
        job=self.app.store.one('SELECT * FROM jobs WHERE id=?',(ticket['job_id'],))
        self.app.execute_job(job,threading.Event())
        return chat,job
    def test_external_model_executes_tool_and_observes_result(self):
        chat,job=self.run_agent();state=load(self.app,chat,job['id'])
        self.assertEqual(state['status'],'done');self.assertEqual(state['actions'][0]['tool'],'list_artifacts')
        posts=[c for c in self.server.calls if c[2]];self.assertEqual(len(posts),2)
        self.assertIn('observations',json.loads(posts[-1][2]['messages'][-1]['content']))
        message=self.app.store.one('SELECT meta FROM messages WHERE id=?',(job['message_id'],))
        self.assertNotIn('private-key-qa',message['meta']);self.assertNotIn('api_key',json.dumps(state))
    def test_invalid_json_does_not_retry_or_execute_a_tool(self):
        self.server.mode='bad';chat,job=self.run_agent();state=load(self.app,chat,job['id'])
        self.assertEqual(state['status'],'failed');self.assertEqual(state['actions'],[])
        self.assertEqual(len([c for c in self.server.calls if c[2]]),1)

if __name__=='__main__':unittest.main()

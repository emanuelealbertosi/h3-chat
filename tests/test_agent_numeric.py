"""Invalid numeric decisions never reach a tool; one budgeted repair only."""
import json
import unittest
from h3chat import agent_state as ledger
from h3chat.remote_llm import check_schema,SchemaNumericError
from test_agent_runtime import AgentTests,decision


class AgentNumericTests(unittest.TestCase):
    setUp=AgentTests.setUp
    tearDown=AgentTests.tearDown
    ticket=AgentTests.ticket
    run_job=AgentTests.run_job

    def test_numeric_error_names_nested_field_and_bounds_without_string_content(self):
        schema={'type':'object','properties':{'private_text':{'type':'string'},'items':{'type':'array',
            'items':{'type':'object','properties':{'duration':{'type':'number','minimum':1,'maximum':600}}}}}}
        with self.assertRaises(SchemaNumericError) as caught:
            check_schema({'private_text':'do not reveal me','items':[{'duration':900}]},schema)
        message=str(caught.exception)
        self.assertIn('$.items[0].duration',message)
        self.assertIn('900',message);self.assertIn('1–600',message)
        self.assertNotIn('do not reveal me',message)

    def test_invalid_video_number_gets_one_counted_correction_before_approval(self):
        chat,job=self.ticket('agent: Crea un video di una teiera.',allow_video=True)
        calls=[]
        def complete(messages,*args,**kwargs):
            data=json.loads(messages[-1]['content']);calls.append(data)
            if len(calls)==1:return decision('create_video',{'prompt':'A blue teapot','parameters':{'megapixels':0}})
            self.assertIn('$.parameters.megapixels',data['decision_validation']['error'])
            return decision('create_video',{'prompt':'A blue teapot','parameters':{'megapixels':.7}})
        answer,worker,image=self.run_job(job,complete)
        state=ledger.load(self.app,chat,job['id'])
        self.assertEqual(state['status'],'awaiting_approval',answer['meta'])
        self.assertEqual(state['usage']['llm_calls'],2)
        self.assertEqual(len(state['actions']),1)
        self.assertEqual(state['actions'][0]['arguments']['parameters']['megapixels'],.7)
        self.assertEqual(len(self.app.store.all('SELECT id FROM jobs')),1)
        worker.assert_not_called();image.assert_not_called()

    def test_two_invalid_decisions_fail_with_field_and_never_execute(self):
        chat,job=self.ticket('agent: Crea un video di una teiera.',allow_video=True)
        calls=[]
        def complete(*args,**kwargs):
            calls.append(1)
            return decision('create_video',{'prompt':'A blue teapot','parameters':{'duration':0}})
        answer,worker,image=self.run_job(job,complete)
        state=ledger.load(self.app,chat,job['id'])
        self.assertEqual(state['status'],'failed')
        self.assertIn('$.parameters.duration',state['message'])
        self.assertEqual(len(calls),2);self.assertEqual(state['actions'],[])
        worker.assert_not_called();image.assert_not_called()

    def test_numeric_correction_cannot_exceed_human_call_budget(self):
        chat,job=self.ticket('agent: Crea un video di una teiera.',allow_video=True,max_calls=1)
        answer,worker,image=self.run_job(job,lambda *a,**k:decision('create_video',{
            'prompt':'A blue teapot','parameters':{'duration':0}}))
        state=ledger.load(self.app,chat,job['id'])
        self.assertEqual(state['status'],'paused')
        self.assertEqual(state['usage']['llm_calls'],1);self.assertEqual(state['actions'],[])
        worker.assert_not_called();image.assert_not_called()


if __name__=='__main__':unittest.main()

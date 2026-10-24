import json,threading,unittest
from unittest.mock import Mock,patch
from h3chat.remote_llm import Client,StructuredCompletionError,structured_text
from h3chat.downloads import Cancelled

SCHEMA={'type':'object','properties':{'content':{'type':'string'},'sources':{'type':'array','items':{'type':'string','enum':['R1']}}},'required':['content','sources'],'additionalProperties':False}
GOOD={'content':'Esempio "concreto"\nSpiegazione.','sources':['R1']}
CONFIG={'model':'fixture','base_url':'http://fixture','thinking':'none','format':'json_object'}
SETTINGS={'max_tokens':3500,'temperature':.2,'think_level':'off'}
def reply(text,finish='stop'):return {'choices':[{'message':{'content':text},'finish_reason':finish}]}

class StructuredTests(unittest.TestCase):
    def test_configured_timeout_also_reaches_transport_socket(self):
        response=Mock();response.read.return_value=b'{}'
        opener=Mock();opener.open.return_value=response
        with patch('h3chat.remote_llm.urllib.request.build_opener',return_value=opener):
            result=Client().exchange(CONFIG,'',threading.Event(),timeout=6000)
        self.assertEqual(result,{})
        self.assertEqual(opener.open.call_args.kwargs['timeout'],6000)

    def test_only_complete_fence_is_unwrapped_and_schema_stays_strict(self):
        self.assertEqual(json.loads(structured_text('```json\n'+json.dumps(GOOD)+'\n```',SCHEMA)),GOOD)
        for value in ['Explanation\n'+json.dumps(GOOD),json.dumps(GOOD)+'\nExplanation','```json\n{}\n```',json.dumps(GOOD|{'extra':1}),json.dumps(GOOD|{'sources':['R2']})]:
            with self.subTest(value=value),self.assertRaises(ValueError):structured_text(value,SCHEMA)

    def test_malformed_stream_gets_one_targeted_repair_same_provider_and_budget(self):
        c=Client();calls=[];bad='{"content":"literal\nline", "sources":["R1"]}'
        def exchange(config,key,cancel,**kw):
            calls.append(kw['body']);text=bad if len(calls)==1 else json.dumps(GOOD)
            kw['on_event']({'choices':[{'delta':{'content':text},'finish_reason':'stop'}]})
        c.exchange=exchange
        chunks=[];text,finish=c.completion(CONFIG,'secret',[{'role':'user','content':'Original task'}],SETTINGS,threading.Event(),chunks.append,SCHEMA)
        self.assertEqual(json.loads(text),GOOD);self.assertEqual(finish,'stop');self.assertEqual(len(calls),2)
        self.assertEqual(calls[0]['max_tokens'],calls[1]['max_tokens']);self.assertEqual(calls[1]['model'],'fixture')
        self.assertIn('Original task',str(calls[1]['messages']));self.assertIn('COMPLETE corrected JSON',calls[1]['messages'][-1]['content'])

    def test_second_invalid_is_bounded_and_preserves_safe_candidate(self):
        c=Client();c.exchange=Mock(return_value=reply('secret malformed'))
        with self.assertRaises(StructuredCompletionError) as e:c.completion(CONFIG,'secret',[],SETTINGS,threading.Event(),schema=SCHEMA)
        self.assertEqual(c.exchange.call_count,2);self.assertNotIn('secret',str(e.exception));self.assertNotIn('secret',e.exception.content)

    def test_length_http_and_cancellation_are_not_retried(self):
        c=Client();c.exchange=Mock(return_value=reply('{"unfinished','length'))
        self.assertEqual(c.completion(CONFIG,'',[],SETTINGS,threading.Event(),schema=SCHEMA),'{"unfinished');self.assertEqual(c.exchange.call_count,1)
        for error in [RuntimeError('Provider API 401'),Cancelled()]:
            c.exchange=Mock(side_effect=error)
            with self.assertRaises(type(error)):c.completion(CONFIG,'',[],SETTINGS,threading.Event(),schema=SCHEMA)
            self.assertEqual(c.exchange.call_count,1)

    def test_valid_fenced_stream_needs_no_new_request(self):
        c=Client()
        def exchange(*a,**kw):kw['on_event']({'choices':[{'delta':{'content':'```json\n'+json.dumps(GOOD)+'\n```'},'finish_reason':'stop'}]})
        c.exchange=Mock(side_effect=exchange)
        text,finish=c.completion(CONFIG,'',[],SETTINGS,threading.Event(),on_text=lambda x:None,schema=SCHEMA)
        self.assertEqual(json.loads(text),GOOD);self.assertEqual(c.exchange.call_count,1)

if __name__=='__main__':unittest.main()

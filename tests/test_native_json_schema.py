import copy,json,unittest
from h3chat.native_json_schema import grammar_schema,validate_response

class NativeSchemaTests(unittest.TestCase):
    def test_native_engine_sends_compact_schema_and_checks_original_limits(self):
        import io,threading
        from types import SimpleNamespace
        from unittest.mock import patch
        from h3chat.engine import Engine
        from h3chat.store import DEFAULTS
        schema={'type':'object','properties':{'copy':{'type':'string','maxLength':6000}},'required':['copy']};sent=[]
        fake=SimpleNamespace(active_model={},active=None,port=12345,key='fixture')
        def open_request(request,**kwargs):
            sent.append(json.loads(request.data));return io.BytesIO(json.dumps({'choices':[{'message':{'content':'{"copy":"valid"}'}}]}).encode())
        with patch('urllib.request.urlopen',side_effect=open_request):value=Engine.completion(fake,[],DEFAULTS,threading.Event(),schema=schema)
        self.assertEqual(json.loads(value),{'copy':'valid'});self.assertNotIn('maxLength',sent[0]['response_format']['json_schema']['schema']['properties']['copy']);self.assertEqual(schema['properties']['copy']['maxLength'],6000)

    def test_only_expensive_string_repetitions_are_removed(self):
        schema={'type':'object','properties':{'copy':{'type':'string','minLength':1,'maxLength':6000},'title':{'type':'string','maxLength':150},'id':{'type':'string','maxLength':32},'rows':{'type':'array','minItems':1,'maxItems':6,'items':{'type':'string','maxLength':2000}}},'required':['copy'],'additionalProperties':False}
        before=copy.deepcopy(schema);native=grammar_schema(schema);self.assertEqual(schema,before);self.assertNotIn('maxLength',native['properties']['copy']);self.assertEqual(native['properties']['copy']['minLength'],1);self.assertEqual(native['properties']['id']['maxLength'],32);self.assertEqual(native['properties']['rows']['maxItems'],6);self.assertFalse(native['additionalProperties'])
    def test_original_lengths_are_still_enforced_after_generation(self):
        schema={'type':'object','properties':{'copy':{'type':'string','minLength':1,'maxLength':6000},'rows':{'type':'array','items':{'type':'string','maxLength':150}}}}
        validate_response(json.dumps({'copy':'test','rows':['valid']}),schema)
        for value in ({'copy':''},{'copy':'x'*6001},{'copy':'ok','rows':['x'*151]}):
            with self.assertRaisesRegex(ValueError,'lunghezza'):validate_response(json.dumps(value),schema)

if __name__=='__main__':unittest.main()

import io,json,threading,unittest
from unittest.mock import patch
from types import SimpleNamespace
from h3chat.engine import Engine
from h3chat.message_content import append_text
from h3chat.store import DEFAULTS

class ContentTests(unittest.TestCase):
    def test_native_request_has_typed_parts_after_appending_instructions(self):
        message={'role':'user','content':[{'type':'image_url','image_url':{'url':'data:image/png;base64,fixture'}},{'type':'text','text':'Fonte [R1]'}]}
        append_text(message,'\nMeasured narration: 20 seconds.')
        append_text(message,'\nPrevious scene: fixture Python.')
        engine=object.__new__(Engine);engine.active=SimpleNamespace(port=1234,api_key='fixture');engine.active_model={}
        def request(req,**kw):
            body=json.loads(req.data);parts=body['messages'][0]['content']
            self.assertTrue(all(isinstance(p,dict) and p['type'] in ('text','image_url') for p in parts));self.assertEqual(len(parts),4)
            self.assertIn('20 seconds',parts[2]['text']);self.assertIn('Previous scene',parts[3]['text'])
            return io.BytesIO(json.dumps({'choices':[{'message':{'content':'OK'}}]}).encode())
        with patch('h3chat.engine.urllib.request.urlopen',side_effect=request):
            self.assertEqual(engine.completion([message],DEFAULTS,threading.Event()),'OK')

    def test_text_remains_text_and_invalid_container_is_reported(self):
        message={'content':'Prompt'};append_text(message,'\nInstruction');self.assertEqual(message['content'],'Prompt\nInstruction')
        with self.assertRaises(ValueError):append_text({'content':None},'Instruction')

if __name__=='__main__':unittest.main()

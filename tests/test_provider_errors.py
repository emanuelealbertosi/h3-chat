import json,unittest
from h3chat.provider_errors import bad_request

class ProviderErrorsTests(unittest.TestCase):
    def test_safe_classifications_never_echo_secrets_or_prompt(self):
        cases=[('max_tokens must be less than 64000','token in uscita'),('reasoning effort none is not supported','Thinking'),('response_format json_schema is unsupported','formato JSON'),('image inputs are not supported','immagine'),('context length maximum exceeded','contesto')]
        for message,expected in cases:
            result=bad_request(json.dumps({'error':{'message':message+' APIKEY-SECRET and private prompt'}}));self.assertIn(expected,result);self.assertNotIn('SECRET',result);self.assertNotIn('private',result)
    def test_unknown_error_stays_generic(self):
        for raw in ('not-json',json.dumps({'error':'secret'}),json.dumps({'error':{'message':'Secret request contents'}})):
            self.assertIn('non supportati',bad_request(raw));self.assertNotIn('Secret',bad_request(raw))

if __name__=='__main__':unittest.main()

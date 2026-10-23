import base64,json,threading,unittest,urllib.request,urllib.error
from http.server import ThreadingHTTPServer
from unittest.mock import Mock
from h3chat.image_api_server import ImageAPI,Handler,APIError,H3Client

KEY='test-key-image-api-with-more-than-24-chars'
PNG='iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aOKsAAAAASUVORK5CYII='


class ImageAPITests(unittest.TestCase):
    def setUp(self):
        self.calls=[]
        def call(path,body=None):
            self.calls.append((path,body))
            if path.endswith('/models'):return {'data':[{'id':'q','name':'Qwen 2.1','capabilities':['create','edit']},{'id':'v','name':'Video','capabilities':['video']}]}
            if path.endswith('/generations'):return {'id':'only-remote-job','status':'queued'}
            return {'status':'done','media':{'mime':'image/png','data':PNG,'generation':{'seed':42,'width':1024,'height':576}}}
        self.client=Mock();self.client.call.side_effect=call
        self.api=ImageAPI(self.client,{'model':'q','models':{'q':{'parameters':{'steps':24,'cfg':4,'seed':-1,'width':1024,'height':1024,'megapixels':1.2,'aspect':'1:1'}}}})

    def test_dimensions_model_seed_and_png_roundtrip_without_mutating_presets(self):
        original=json.dumps(self.api.config)
        result=self.api.generate({'prompt':'una pera','width':1024,'height':576,'seed':42,'sampler_name':'Euler','scheduler':'Simple','override_settings':{'sd_model_checkpoint':'Qwen 2.1'}})
        body=next(b for p,b in self.calls if p.endswith('/generations'))
        self.assertEqual(body['model'],'q');self.assertEqual(body['parameters']['seed'],42)
        self.assertEqual((body['parameters']['width'],body['parameters']['height']),(1024,576))
        self.assertNotIn('megapixels',body['parameters']);self.assertEqual(body['parameters']['aspect'],'auto')
        self.assertEqual((body['parameters']['steps'],body['parameters']['cfg']),(24,4))
        self.assertEqual(result['images'],[PNG]);self.assertEqual(json.loads(result['info'])['seed'],42)
        self.assertEqual(json.dumps(self.api.config),original)

    def test_preserves_parameters_when_not_overridden_and_rejects_fake_features(self):
        for patch in [{'enable_hr':True},{'batch_size':2},{'alwayson_scripts':{'ControlNet':{}}},{'override_settings':{'sd_model_checkpoint':'v'}}]:
            with self.assertRaises(APIError):self.api.generate({'prompt':'x',**patch})
        self.assertFalse(any(p.endswith('/generations') for p,b in self.calls))

    def test_interrupt_cannot_cancel_unrelated_app_work(self):
        self.api.interrupt();self.assertEqual(self.calls,[])
        self.api.active='only-remote-job';self.api.interrupt()
        self.assertEqual(self.calls,[('/v1/h3/jobs/only-remote-job/cancel',{})])

    def test_anima_and_moss_keep_their_own_presets_and_sampler_dialects(self):
        for engine,steps,cfg,sampler in [('native',30,4,'euler_a'),('vision',50,3,'euler_ancestral')]:
            with self.subTest(engine=engine):
                self.api.config['models']['q']={'engine':engine,'parameters':{'steps':steps,'cfg':cfg,'seed':-1,'scheduler':'sgm_uniform'}}
                self.api.generate({'prompt':'test','sampler_name':'Euler a'})
                body=[b for p,b in self.calls if p.endswith('/generations')][-1]
                self.assertEqual(body['parameters']['sampler'],sampler)
                self.assertEqual((body['parameters']['steps'],body['parameters']['cfg']),(steps,cfg))

    def test_no_nonlocal_upstream(self):
        for url in ['http://example.com','http://127.0.0.1@otherhost','https://127.0.0.1']:
            with self.assertRaises(ValueError):H3Client(url,KEY)

    def test_http_basic_auth_discovery_generation_and_no_admin(self):
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler);server.secret=KEY;server.api=self.api
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        self.addCleanup(server.server_close);self.addCleanup(server.shutdown)
        url='http://127.0.0.1:'+str(server.server_port)
        def request(path,body=None,headers=None):
            req=urllib.request.Request(url+path,data=None if body is None else json.dumps(body).encode(),headers=headers or {})
            with urllib.request.urlopen(req) as r:return json.load(r)
        with self.assertRaises(urllib.error.HTTPError) as denied:request('/sdapi/v1/options')
        self.assertEqual(denied.exception.code,403)
        auth={'Authorization':'Basic '+base64.b64encode(('h3:'+KEY).encode()).decode()}
        self.assertEqual(request('/sdapi/v1/options',headers=auth)['sd_model_checkpoint'],'Qwen 2.1')
        self.assertEqual(len(request('/sdapi/v1/sd-models',headers=auth)),1)
        with self.assertRaises(urllib.error.HTTPError) as missing:request('/api/state',headers=auth)
        self.assertEqual(missing.exception.code,404)
        with self.assertRaises(urllib.error.HTTPError):request('/sdapi/v1/options',headers=auth|{'Origin':'http://other.local'})
        self.assertEqual(request('/sdapi/v1/txt2img',{'prompt':'una pera'},auth)['images'],[PNG])


if __name__=='__main__':unittest.main()

import base64,io,json,tempfile,threading,time,unittest,urllib.request,urllib.error,wave
from pathlib import Path
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from unittest.mock import patch
from h3chat.service import Service
from h3chat.media_providers import MediaProviders
from h3chat.store import Store,DEFAULTS
from h3chat.image_options import options as image_options
from h3chat.downloads import Cancelled
from h3chat.providers import endpoint

ROOT=Path(__file__).resolve().parents[1]
PNG=base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aOKsAAAAASUVORK5CYII=')
class Fixture(BaseHTTPRequestHandler):
    def log_message(self,*a):pass
    def do_GET(self):self.send_response(200);self.end_headers();self.wfile.write(b'{"data":[{"id":"test"}]}')
    def do_POST(self):
        raw=self.rfile.read(int(self.headers['Content-Length']));self.server.calls.append((self.path,dict(self.headers),raw));self.send_response(200);self.end_headers();value={'images':[base64.b64encode(PNG).decode()]} if self.path.startswith('/sdapi') else {'data':[{'b64_json':base64.b64encode(PNG).decode()}]};self.wfile.write(json.dumps(value).encode())

class MediaTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.data=Path(self.tmp.name);self.providers=MediaProviders(Store(self.data));self.http=ThreadingHTTPServer(('127.0.0.1',0),Fixture);self.http.calls=[];self.thread=threading.Thread(target=self.http.serve_forever,daemon=True);self.thread.start();self.url=f'http://127.0.0.1:{self.http.server_port}'
    def tearDown(self):self.providers.client.abort();self.http.shutdown();self.http.server_close();self.tmp.cleanup()
    def config(self,adapter='openai-images',**values):return self.providers.save({'name':'Test','base_url':self.url,'model':'test','role':'image','adapter':adapter,**values})
    def test_images_create_edit_multipart_and_forge_parameters(self):
        cfg=self.config();model=self.providers.model(cfg);settings=DEFAULTS|{'_image_options':image_options(model,DEFAULTS)};output=self.providers.generate(model,settings,'Crea un cerchio',[],'a',threading.Event(),lambda _:None);self.assertEqual((self.data/output['path']).read_bytes(),PNG);body=json.loads(self.http.calls[-1][2]);self.assertEqual(body['model'],'test');self.assertEqual(body['response_format'],'b64_json')
        source=self.data/'uploads/reference.png';source.parent.mkdir();source.write_bytes(PNG);refs=[{'name':'reference.png','path':'uploads/reference.png','mime':'image/png'}];self.providers.generate(model,settings,'Rendi blu',refs,'b',threading.Event(),lambda _:None);path,headers,raw=self.http.calls[-1];self.assertEqual(path,'/images/edits');self.assertIn('multipart/form-data',headers['Content-Type']);self.assertIn(b'name="image"',raw);self.assertIn(PNG,raw)
        cfg=self.config('forge');model=self.providers.model(cfg);self.providers.generate(model,settings,'tag1, tag2',refs,'c',threading.Event(),lambda _:None);body=json.loads(self.http.calls[-1][2]);self.assertEqual(body['steps'],20);self.assertEqual(body['override_settings']['sd_model_checkpoint'],'test');self.assertEqual(body['init_images'],[base64.b64encode(PNG).decode()])
    def test_keys_never_leave_private_provider_table(self):
        cfg=self.config(api_key='media-secret');self.assertTrue(cfg['has_key']);self.assertNotIn('media-secret',json.dumps(self.providers.list()));self.assertNotIn('media-secret',json.dumps(self.providers.model(cfg)));self.assertEqual(self.providers.credentials(cfg['id'])[1],'media-secret')
        with self.assertRaises(ValueError):self.providers.save({**cfg,'base_url':self.url+'/changed','api_key':''})
    def test_lan_endpoint_and_video_gpu_only(self):
        self.assertEqual(endpoint('http://192.168.1.10:8790'),'http://192.168.1.10:8790')
        with self.assertRaises(ValueError):endpoint('http://public.example.com')
        with self.assertRaises(ValueError):self.config('h3',role='video',device='cpu')

class H3ServerTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.path=Path(self.tmp.name);self.app=Service(ROOT,self.path/'server');self.client=MediaProviders(Store(self.path/'client'));self.cfg=self.app.media_server.start({'port':self.free_port()});self.url=f"http://127.0.0.1:{self.cfg['port']}";self.key=self.cfg['api_key']
        self.models={role:{'id':role,'name':role,'architecture':'sd' if role=='image' else 'yue2' if role=='music' else 'minimax-h3','capabilities':['create','edit'] if role=='image' else [role],'files':[],'external':True} for role in ('image','music','video')}
        for model in self.models.values():model['ready']=True
        self.app.catalog.update(self.models);self.refresh=patch.object(self.app,'refresh_models',return_value=list(self.models.values()));self.refresh.start()
    def free_port(self):
        import socket
        with socket.socket() as s:s.bind(('127.0.0.1',0));return s.getsockname()[1]
    def tearDown(self):self.client.client.abort();self.app.close();self.refresh.stop();self.tmp.cleanup()
    def output(self,job_id,mime,raw):
        ext={'image/png':'png','audio/wav':'wav','video/mp4':'mp4'}[mime];relative='outputs/'+job_id+'/generated.'+ext;p=self.app.data/relative;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(raw);return {'id':'output','name':'generated.'+ext,'path':relative,'mime':mime,'generation':{'steps':12}}
    def test_auth_and_filesystem_endpoints_are_not_exposed(self):
        with self.assertRaises(urllib.error.HTTPError):urllib.request.urlopen(self.url+'/v1/h3/models')
        request=urllib.request.Request(self.url+'/api/model-files/browse',headers={'Authorization':'Bearer '+self.key})
        with self.assertRaises(urllib.error.HTTPError) as e:urllib.request.urlopen(request)
        self.assertEqual(e.exception.code,404)
    def test_h3_media_roundtrip_for_all_modalities(self):
        audio=io.BytesIO()
        with wave.open(audio,'wb') as f:f.setnchannels(1);f.setsampwidth(2);f.setframerate(8000);f.writeframes(b'\0\0'*100)
        def image(model,settings,prompt,refs,job_id,cancel,stage):self.assertEqual(settings['image_device'],'cpu');return self.output(job_id,'image/png',PNG)
        def music(model,settings,composition,job_id,cancel,stage):return self.output(job_id,'audio/wav',audio.getvalue())
        def video(model,settings,plan,refs,job_id,cancel,stage):self.assertEqual(plan['prompt'],'English instructions');return self.output(job_id,'video/mp4',b'\x00\x00\x00\x18ftypmp42'+b'\0'*24)
        with patch.object(self.app.engine,'generate',side_effect=image),patch.object(self.app.engine,'generate_music',side_effect=music),patch.object(self.app.engine,'generate_video',side_effect=video):
            for role in ('image','music','video'):
                cfg=self.client.save({'name':'Remote '+role,'role':role,'adapter':'h3','base_url':self.url,'model':role,'api_key':self.key,'device':'cpu' if role=='image' else 'gpu'});model=self.client.model(cfg);self.assertTrue(self.client.probe(cfg['id'])['ok']);settings=DEFAULTS|{'_image_options':image_options(model,DEFAULTS)}
                kwargs={'composition':{'title':'Test','style':'piano','lyrics':'','abc':'','instrumental':True}} if role=='music' else {'plan':{'prompt':'English instructions','images':[],'audios':[]}} if role=='video' else {}
                result=self.client.generate(model,settings,'Create an image',[],role,threading.Event(),lambda _:None,**kwargs);self.assertTrue((self.client.store.root/result['path']).exists());self.assertTrue(result['generation']['remote'])
    def test_h3_llm_stream_uses_same_serial_worker(self):
        model={'id':'chat','name':'Chat','files':[],'capabilities':['chat'],'vision':{'enabled':False}}
        self.app.catalog['chat']=model
        def complete(messages,settings,cancel,on_text=None,**kw):
            if on_text:on_text('Risposta dal server.')
            return ('Risposta dal server.','stop')
        with patch.object(self.app.engine,'require_model',return_value=model),patch.object(self.app.engine,'start_llama'),patch.object(self.app.engine,'completion',side_effect=complete):
            req=urllib.request.Request(self.url+'/v1/chat/completions',data=json.dumps({'model':'chat','messages':[{'role':'user','content':'Test'}],'stream':True}).encode(),headers={'Authorization':'Bearer '+self.key,'Content-Type':'application/json'})
            with urllib.request.urlopen(req,timeout=15) as response:raw=response.read().decode()
        self.assertIn('Risposta dal server.',raw);self.assertIn('[DONE]',raw)
    def test_cancelling_remote_generation_also_cancels_owned_server_job(self):
        local_cancel=threading.Event();errors=[]
        def generate(model,settings,prompt,refs,job_id,cancel,stage):
            if cancel.wait(10):raise Cancelled()
            raise AssertionError('Cancellation was not forwarded')
        cfg=self.client.save({'name':'Cancel','role':'image','adapter':'h3','base_url':self.url,'model':'image','api_key':self.key});model=self.client.model(cfg)
        def run():
            try:self.client.generate(model,DEFAULTS,'Create',[],'cancel',local_cancel,lambda _:None)
            except Exception as e:errors.append(e)
        with patch.object(self.app.engine,'generate',side_effect=generate):
            worker=threading.Thread(target=run);worker.start();job=None
            for _ in range(100):
                job=self.app.store.one("SELECT id,status FROM jobs WHERE status='running'")
                if job:break
                time.sleep(.02)
            self.assertIsNotNone(job);local_cancel.set();worker.join(8);self.assertFalse(worker.is_alive());self.assertTrue(errors and isinstance(errors[0],Cancelled))
            for _ in range(100):
                state=self.app.store.one('SELECT status FROM jobs WHERE id=?',(job['id'],))['status']
                if state=='cancelled':break
                time.sleep(.02)
            self.assertEqual(state,'cancelled')

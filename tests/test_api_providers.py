import base64
import json
import tempfile
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch
from h3chat.providers import endpoint,protect,validate
from h3chat.remote_llm import Client,request_body
from h3chat.service import Service
from h3chat.store import DEFAULTS
from h3chat.hardware import assess_model,assess_selection
from h3chat.downloads import Cancelled

ROOT=Path(__file__).resolve().parents[1]

def sample(schema):
    if 'enum' in schema:return 'chat' if 'chat' in schema['enum'] else schema['enum'][0]
    kind=schema.get('type')
    if kind=='object':return {k:sample(v) for k,v in schema.get('properties',{}).items() if k in schema.get('required',[])}
    if kind=='array':return []
    if kind=='boolean':return False
    if kind in ('number','integer'):return schema.get('minimum',1)
    return 'API risposta'

class Stub(BaseHTTPRequestHandler):
    def log_message(self,*args):pass
    def do_GET(self):
        self.server.calls.append((self.path,dict(self.headers),None));self.send_response(200);self.end_headers();self.wfile.write(b'{"data":[{"id":"test-model"},{"id":"vision-test"}]}')
    def do_POST(self):
        body=json.loads(self.rfile.read(int(self.headers['Content-Length'])));self.server.calls.append((self.path,dict(self.headers),body))
        mode=self.server.mode
        if mode=='401':
            self.send_response(401);self.end_headers();self.wfile.write(b'private-key-qa echoed request');return
        if mode=='redirect':
            self.send_response(302);self.send_header('Location',self.server.url+'/stolen');self.end_headers();return
        self.send_response(200);self.send_header('Content-Type','text/event-stream' if body.get('stream') else 'application/json');self.end_headers()
        if mode=='stall':
            self.wfile.write(b': ping\n\n');self.wfile.flush();self.server.stalled.set();self.server.resume.wait(4);return
        text='Risposta via API.'
        if body['messages'][0]['content'].startswith('Return only a JSON object'):
            schema=json.loads(body['messages'][0]['content'].split('\n',1)[1]);value=sample(schema)
            if 'tags' in value:value['tags']=['red hair','1girl']
            text=json.dumps(value)
        if mode=='bad':text='```json\n{}\n```'
        if body.get('stream'):
            events=[{'choices':[{'delta':{'reasoning_content':'private reasoning'},'finish_reason':None}]},{'choices':[{'delta':{'content':text},'finish_reason':None if mode=='truncated' else 'stop'}]}]
            if mode=='streamerror':events=[{'error':{'message':'private-key-qa'}}]
            for event in events:self.wfile.write(('data: '+json.dumps(event)+'\n\n').encode())
            self.wfile.write(b'data: [DONE]\n\n');self.wfile.flush()
        else:self.wfile.write(json.dumps({'choices':[{'message':{'content':text},'finish_reason':'stop'}]}).encode())

class ApiTests(unittest.TestCase):
    def setUp(self):
        self.server=ThreadingHTTPServer(('127.0.0.1',0),Stub);self.server.daemon_threads=True;self.server.url=f'http://127.0.0.1:{self.server.server_port}';self.server.mode='ok';self.server.calls=[];self.server.stalled=threading.Event();self.server.resume=threading.Event()
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        self.tmp=tempfile.TemporaryDirectory();self.app=Service(ROOT,self.tmp.name,start_worker=False)
        self.config={'name':'QA API','base_url':self.server.url+'/v1','model':'test-model','vision':False,'max_refs':4,'thinking':'none','format':'json_object','api_key':'private-key-qa'}
    def tearDown(self):
        self.app.close();self.server.resume.set();self.server.shutdown();self.server.server_close();self.tmp.cleanup()
    def save(self,**overrides):return self.app.provider_request(self.config|overrides)
    def test_dpapi_private_metadata_and_reload(self):
        saved=self.save();self.assertTrue(saved['has_key']);state=self.app.state();self.assertNotIn('private-key-qa',json.dumps(state))
        encrypted=self.app.store.one('SELECT secret FROM api_providers')['secret'];self.assertNotIn('private-key-qa',encrypted);self.assertEqual(protect(encrypted,True),'private-key-qa')
        self.app.close();self.app=Service(ROOT,self.tmp.name,start_worker=False);self.app.refresh_models();self.assertEqual(self.app.providers.credentials(saved['id'])[1],'private-key-qa')
        self.assertTrue(self.app.engine.require_model(saved['id'],'chat')['ready'])
    def test_update_preserves_key_clear_and_remove_selected(self):
        p=self.save();edited=self.save(id=p['id'],name='Renamed',api_key='');self.assertTrue(edited['has_key'])
        self.app.save_settings({'chat_model':p['id']});self.assertFalse(self.save(id=p['id'],api_key='',clear_key=True)['has_key'])
        self.app.remove_provider(p['id']);self.assertEqual(self.app.store.settings()['chat_model'],'');self.assertNotIn(p['id'],self.app.catalog)
    def test_endpoint_change_cannot_reuse_old_key(self):
        p=self.save()
        with self.assertRaisesRegex(ValueError,'Indirizzo cambiato'):self.save(id=p['id'],base_url='https://other.example/v1',api_key='')
    def test_url_and_config_validation(self):
        self.assertEqual(endpoint('https://api.deepseek.com/v1/chat/completions/'),'https://api.deepseek.com/v1')
        for url in ('http://outside.example/v1','https://user:pass@api.example','https://api.example?key=secret','file:///models','https://api.example/\n'):
            with self.assertRaises(ValueError):endpoint(url)
        for invalid in ({'name':3},{'max_refs':10},{'thinking':'invented'},{'api_key':'x\nInjected'},{'model':None}):
            with self.assertRaises(ValueError):validate(self.config|invalid)
    def test_model_list_and_test_request_only_probe(self):
        r=self.app.provider_request(self.config,'models');self.assertEqual(r['models'],['test-model','vision-test'])
        self.assertEqual(self.server.calls[-1][0],'/v1/models');self.assertEqual(self.server.calls[-1][1]['Authorization'],'Bearer private-key-qa')
        self.assertTrue(self.app.provider_request(self.config,'test')['ok']);self.assertEqual(self.server.calls[-1][2]['messages'],[{'role':'user','content':'Reply with OK.'}])
    def test_busy_changes_blocked(self):
        self.app.current_id='running'
        for op in ('save','models','test'):
            with self.assertRaises(ValueError):self.app.provider_request(self.config,op)
    def test_remote_chat_router_stream_no_local_process_and_no_key_in_history(self):
        p=self.save();self.app.save_settings({'chat_model':p['id'],'music_model':''})
        chat=self.app.store.create_chat();sent=self.app.send(chat['id'],{'prompt':'Ciao, spiegami una cosa','media':[]});job=self.app.store.one('SELECT * FROM jobs WHERE id=?',(sent['job_id'],))
        with patch('h3chat.residency.subprocess.Popen') as start:self.app.execute_job(job,threading.Event());start.assert_not_called()
        messages=self.app.store.messages(chat['id']);answer=messages[-1];self.assertEqual(answer['status'],'done',answer);self.assertEqual(answer['content'],'Risposta via API.');self.assertTrue(answer['meta']['api']);self.assertIsNone(answer['meta']['think_budget'])
        self.assertNotIn('private-key-qa',json.dumps(messages));self.assertNotIn('private-key-qa',self.app.store.one('SELECT payload FROM jobs')['payload']);self.assertEqual(self.app.engine.sessions,{})
        bodies=[c[2] for c in self.server.calls];self.assertEqual(len(bodies),2);self.assertFalse(bodies[0]['stream']);self.assertTrue(bodies[1]['stream'])
        for body in bodies:self.assertFalse(set(body)&{'chat_template_kwargs','reasoning_budget_tokens','reasoning_format'})
    def test_canvas_json_validated_and_body_only_standard_reply(self):
        p=self.save();self.app.save_settings({'chat_model':p['id']});chat=self.app.store.create_chat();sent=self.app.send(chat['id'],{'prompt':'Spiega nel canvas','media':[],'canvas':True});job=self.app.store.one('SELECT * FROM jobs WHERE id=?',(sent['job_id'],));self.app.execute_job(job,threading.Event())
        answer=self.app.store.messages(chat['id'])[-1];self.assertEqual(answer['status'],'done',answer);self.assertEqual(answer['content'],'Ho scritto l’artefatto nel canvas.');self.assertEqual(answer['meta']['artifact']['content'],'API risposta')
    def test_vision_attachments_sent_only_with_capability_and_toggle(self):
        p=self.save(vision=True);model=self.app.engine.require_model(p['id'],'chat');raw=base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Y9ZlS8AAAAASUVORK5CYII=');item=self.app.upload({'name':'ref.png','data':base64.b64encode(raw).decode()});history=[{'role':'user','content':'Leggi','media':[item],'seq':1,'status':'done'}]
        self.assertEqual(self.app.engine.chat_messages(history,model,DEFAULTS)[-1]['content'][0]['image_url']['url'],'data:image/png;base64,'+base64.b64encode(raw).decode())
        with self.assertRaises(ValueError):self.app.engine.chat_messages(history,model,DEFAULTS|{'vision_enabled':False})
        plain=self.app.engine.require_model(self.save()['id'],'chat')
        with self.assertRaises(ValueError):self.app.engine.chat_messages(history,plain,DEFAULTS)
    def test_image_assistant_english_tags_over_api(self):
        p=self.save();tuning=DEFAULTS|{'chat_model':p['id']}
        image={'name':'SDXL','architecture':'sdxl'}
        prompt,meta=self.app.engine.refine_image_prompt([], 'Una ragazza coi capelli rossi',[],tuning,threading.Event(),Path(self.tmp.name)/'image.log',lambda _:None,image_model=image)
        self.assertEqual(prompt,'red hair, 1girl');self.assertEqual(meta['prompt_format'],'tags');self.assertEqual(self.app.engine.sessions,{})
    def test_music_assistant_over_api(self):
        p=self.save();result,meta=self.app.engine.refine_music([], 'Crea un brano',{},DEFAULTS|{'chat_model':p['id']},threading.Event(),Path(self.tmp.name)/'music.log',lambda _:None)
        self.assertEqual(result['style'],'API risposta');self.assertEqual(result['lyrics'],'API risposta');self.assertIn('API',meta['model'])
    def test_video_assistant_over_api(self):
        p=self.save();result,meta=self.app.engine.refine_video([], 'Crea un video',[],{'id':'video-fixture'},DEFAULTS|{'chat_model':p['id']},threading.Event(),Path(self.tmp.name)/'video.log',lambda _:None)
        self.assertEqual(result,{'prompt':'API risposta','images':[],'audios':[]});self.assertIn('API',meta['model'])
    def test_resident_api_does_not_preload_or_call_endpoint(self):
        p=self.save();settings=DEFAULTS|{'chat_model':p['id'],'music_model':'','memory_policy':'resident'}
        with patch('h3chat.residency.subprocess.Popen') as start:self.app.engine.prepare(settings,threading.Event(),lambda _:None);start.assert_not_called()
        self.assertEqual(self.server.calls,[])
    def test_service_abort_stalled_api_leaves_no_local_workers(self):
        p=self.save();self.server.mode='stall';self.app.save_settings({'chat_model':p['id']});chat=self.app.store.create_chat();sent=self.app.send(chat['id'],{'prompt':'Scrivi codice Python semplice','media':[]});job=self.app.store.one('SELECT * FROM jobs WHERE id=?',(sent['job_id'],));cancel=threading.Event()
        t=threading.Thread(target=self.app.execute_job,args=(job,cancel));t.start();self.assertTrue(self.server.stalled.wait(2));cancel.set();self.app.engine.abort_active();t.join(2)
        self.assertFalse(t.is_alive());self.assertEqual(self.app.store.messages(chat['id'])[-1]['status'],'cancelled');self.assertEqual(self.app.engine.sessions,{})
    def test_deepseek_thinking_levels_and_json_mapping(self):
        config=self.config|{'thinking':'deepseek'}
        for level,effort in {'off':'none','low':'low','med':'high','high':'high','xhigh':'max'}.items():
            body=request_body(config,[],DEFAULTS|{'think_level':level},True,None);self.assertEqual(body['reasoning_effort'],effort);self.assertEqual(body['thinking']['type'],'disabled' if level=='off' else 'enabled')
        schema={'type':'object'};body=request_body(config,[],DEFAULTS|{'think_level':'high'},False,schema);self.assertEqual(body['reasoning_effort'],'none');self.assertEqual(body['response_format'],{'type':'json_object'});self.assertIn('JSON schema',body['messages'][0]['content'])
    def test_formats_and_openrouter_effort(self):
        schema={'type':'object'}
        for mode in ('json_schema','json_object','prompt'):
            body=request_body(self.config|{'thinking':'openrouter','format':mode},[],DEFAULTS|{'think_level':'med'},True,schema);self.assertEqual(body['reasoning']['effort'],'medium')
            self.assertEqual(body.get('response_format',{}).get('type'),None if mode=='prompt' else mode)
    def test_http_errors_no_secret_echo_or_retry(self):
        self.server.mode='401'
        with self.assertRaisesRegex(RuntimeError,'401') as caught:self.app.provider_request(self.config,'test')
        self.assertNotIn('private-key-qa',str(caught.exception));self.assertEqual(len(self.server.calls),1)
    def test_redirect_rejected_before_credentials_forwarded(self):
        self.server.mode='redirect'
        with self.assertRaisesRegex(RuntimeError,'reindirizza'):self.app.provider_request(self.config,'test')
        self.assertEqual(len(self.server.calls),1)
    def test_invalid_structured_stream_rejected(self):
        self.server.mode='bad';schema={'type':'object','properties':{'intent':{'type':'string'}},'required':['intent']}
        with self.assertRaisesRegex(ValueError,'JSON richiesto'):Client().completion(self.config,'private-key-qa',[],DEFAULTS,threading.Event(),on_text=lambda _:None,schema=schema)
    def test_incomplete_or_error_stream_rejected(self):
        for mode in ('truncated','streamerror'):
            self.server.mode=mode
            with self.assertRaises(RuntimeError) as caught:Client().completion(self.config,'private-key-qa',[{'role':'user','content':'Hi'}],DEFAULTS,threading.Event(),on_text=lambda _:None)
            self.assertNotIn('private-key-qa',str(caught.exception))
    def test_cancel_live_stalled_stream_promptly_and_no_late_callbacks(self):
        self.server.mode='stall';client=Client();cancel=threading.Event();errors=[];chunks=[]
        def run():
            try:client.completion(self.config,'private-key-qa',[{'role':'user','content':'Hi'}],DEFAULTS,cancel,on_text=chunks.append)
            except Exception as exc:errors.append(exc)
        t=threading.Thread(target=run);t.start();self.assertTrue(self.server.stalled.wait(2));start=time.monotonic();cancel.set();t.join(1);self.assertFalse(t.is_alive());self.assertLess(time.monotonic()-start,1);self.assertIsInstance(errors[0],Cancelled);self.assertEqual(chunks,[])
    def test_pre_cancel_no_request(self):
        cancel=threading.Event();cancel.set()
        with self.assertRaises(Cancelled):Client().completion(self.config,'private-key-qa',[],DEFAULTS,cancel)
        self.assertEqual(self.server.calls,[])
    def test_api_memory_estimate_uses_zero_local_weights(self):
        model=self.app.engine.require_model(self.save()['id'],'chat');hardware={'ram':{'free_mb':None},'gpu':[]}
        result=assess_model(model,DEFAULTS,hardware);self.assertEqual(result['ram_gb'],0);self.assertEqual(result['vram_gb'],0)
        combined=assess_selection([model],DEFAULTS,hardware);self.assertEqual(combined['status'],'ok');self.assertEqual(combined['vram_gb'],0)

if __name__=='__main__':unittest.main()

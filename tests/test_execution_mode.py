import json,tempfile,threading,unittest
from pathlib import Path
from unittest.mock import patch
from http.server import ThreadingHTTPServer
from h3chat.service import Service
from h3chat.execution_mode import effective,guard_job,require_model
from h3chat.store import DEFAULTS
from test_api_providers import Stub
ROOT=Path(__file__).resolve().parents[1]

class ExecutionTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.app=Service(ROOT,self.temp.name,start_worker=False);self.addCleanup(self.app.close)
        self.local=next(m['id'] for m in self.app.catalog.values() if 'chat' in m['capabilities'] and not m.get('api'))
        self.app.save_settings({'chat_model':self.local,'memory_policy':'resident','ram_cache_gb':2,'rag_device':'gpu','vision_device':'gpu','manim_device':'gpu'})
    def provider(self,url='http://127.0.0.1:9999/v1'):
        ident=self.app.provider_request({'name':'CPU test API','base_url':url,'model':'test-model','vision':False,'max_refs':4,'thinking':'none','format':'json_object','api_key':''})['id']
        self.app.save_settings({'cpu_chat_model':ident});return ident
    def test_switch_preserves_gpu_choices_and_forces_all_devices_without_mutation(self):
        api=self.provider();before=self.app.store.settings()
        with patch.object(self.app.engine,'stop') as stop:self.app.save_settings({'execution_mode':'cpu'});stop.assert_called_once()
        live=self.app.effective_settings();self.assertEqual(live['chat_model'],api)
        for key in ('backend','rag_device','vision_device','manim_device','asr_device','voice_device','llm_device'):self.assertEqual(live[key],'cpu')
        self.assertFalse(live['mtp_enabled']);self.assertEqual(live['ram_cache_gb'],0)
        self.assertEqual(self.app.store.settings(),before|{'execution_mode':'cpu'})
        self.app.save_settings({'execution_mode':'gpu'});self.assertEqual(self.app.store.settings(),before)
    def test_no_api_and_all_explicit_media_requests_are_rejected_before_queue(self):
        self.app.save_settings({'execution_mode':'cpu'});chat=self.app.store.create_chat()['id']
        with patch.object(self.app,'effective_settings',return_value=effective(DEFAULTS|{'execution_mode':'cpu'},{})),self.assertRaisesRegex(ValueError,'LLM locale'):self.app.send(chat,{'prompt':'Ciao'})
        self.provider()
        for field in ('image_model','music','video','voice','transcribe'):
            with self.subTest(field=field),self.assertRaisesRegex(ValueError,'Modalità CPU'):self.app.send(chat,{'prompt':'Crea una prova',field:'anything' if field=='image_model' else True})
        self.assertEqual(self.app.store.all('SELECT id FROM jobs'),[])
    def test_real_api_chat_uses_no_local_process_and_keeps_gpu_model_selected(self):
        server=ThreadingHTTPServer(('127.0.0.1',0),Stub);server.daemon_threads=True;server.url=f'http://127.0.0.1:{server.server_port}';server.mode='ok';server.calls=[];server.stalled=threading.Event();server.resume=threading.Event()
        threading.Thread(target=server.serve_forever,daemon=True).start();self.addCleanup(server.server_close);self.addCleanup(server.shutdown)
        api=self.provider(server.url+'/v1');self.app.save_settings({'execution_mode':'cpu'})
        chat=self.app.store.create_chat()['id'];sent=self.app.send(chat,{'prompt':'Ciao, rispondi brevemente'})
        job=self.app.store.one('SELECT * FROM jobs WHERE id=?',(sent['job_id'],))
        with patch('h3chat.residency.Session.start',side_effect=AssertionError('No local model worker allowed')):
            self.app.execute_job(job,threading.Event())
        answer=self.app.store.messages(chat)[-1];self.assertEqual(answer['status'],'done',answer['meta']);self.assertIn('Risposta via API',answer['content']);self.assertTrue(server.calls)
        self.assertEqual(answer['meta']['settings']['chat_model'],api);self.assertEqual(self.app.store.settings()['chat_model'],self.local)
    def test_no_switch_during_queue_or_rag_and_old_payload_cannot_bypass_policy(self):
        chat=self.app.store.create_chat()['id'];ident=self.app.store.enqueue(chat,'test',[],self.app.store.settings())
        with patch.object(self.app.engine,'stop') as stop,self.assertRaisesRegex(ValueError,'fine di tutti i lavori'):self.app.save_settings({'execution_mode':'cpu'})
        stop.assert_not_called();self.app.cancel(ident)
        self.app.knowledge.tasks['test']={'status':'running'}
        with self.assertRaisesRegex(ValueError,'indicizzazioni'):self.app.save_settings({'execution_mode':'cpu'})
        self.app.knowledge.tasks.clear();self.app.save_settings({'execution_mode':'cpu'})
        with self.assertRaisesRegex(ValueError,'Modalità CPU'):guard_job(self.app.effective_settings(DEFAULTS|{'_video_edit':{'source':'old'}}))
        with self.assertRaisesRegex(ValueError,'LLM locale'):self.app.engine.require_model('','chat')
        with self.assertRaisesRegex(ValueError,'Modalità CPU'):self.app.engine.require_model('unconfigured','create')
    def test_rag_index_forces_cpu_even_with_saved_gpu_setting(self):
        self.provider();self.app.save_settings({'execution_mode':'cpu'})
        project=self.app.knowledge.save({'name':'CPU project'})['id'];seen=[]
        settings=self.app.store.settings()|{'rag_embedding_model':'synthetic'}
        with patch.object(self.app.knowledge.embeddings,'key',side_effect=lambda s:seen.append(s['rag_device']) or 'synthetic'):
            self.app.knowledge.index(project,settings,threading.Event(),lambda s:None)
        self.assertTrue(seen);self.assertEqual(set(seen),{'cpu'});self.assertEqual(settings['rag_device'],'gpu')
    def test_policy_blocks_nested_media_but_not_existing_cpu_exports(self):
        cpu=effective(DEFAULTS|{'execution_mode':'cpu'})
        for options in ({'_slides':{'generate_images':True}},{'_infographic':{'voice':True}},{'_infographic':{'music':'generate'}},{'_image_batch':True}):
            with self.assertRaisesRegex(ValueError,'Modalità CPU'):guard_job(cpu|options)
        guard_job(cpu|{'_video_assemble':{'source':'saved'},'_infographic_render':True})
        with self.assertRaisesRegex(ValueError,'Modalità CPU'):require_model(cpu,{'remote_media':True},'create')
    def test_global_owner_policy_covers_guests_and_waits_their_jobs(self):
        from h3chat.workspaces import Workspaces
        api=self.provider();spaces=Workspaces(self.app,start_workers=False);self.addCleanup(spaces.close)
        guest=spaces.get({'id':'guest-test','role':'guest'})
        ident=guest.store.enqueue(guest.store.create_chat()['id'],'guest work',[],guest.store.settings())
        with self.assertRaisesRegex(ValueError,'fine di tutti i lavori'):self.app.save_settings({'execution_mode':'cpu'})
        guest.cancel(ident);self.app.save_settings({'execution_mode':'cpu'})
        self.assertEqual(guest.effective_settings()['execution_mode'],'cpu');self.assertEqual(guest.effective_settings()['chat_model'],api)
        with self.assertRaisesRegex(ValueError,'Modalità CPU'):guest.engine.require_model('local','video')

    def test_automatic_image_route_is_blocked_before_native_generation(self):
        self.provider();self.app.save_settings({'execution_mode':'cpu'})
        chat=self.app.store.create_chat()['id'];sent=self.app.send(chat,{'prompt':'Crea una immagine di un albero','assistant':False})
        job=self.app.store.one('SELECT * FROM jobs WHERE id=?',(sent['job_id'],))
        with patch.object(self.app.engine,'generate',side_effect=AssertionError('Generation must not run')) as generate,patch('h3chat.residency.Session.start',side_effect=AssertionError('Native worker must not run')):
            self.app.execute_job(job,threading.Event())
        generate.assert_not_called();answer=self.app.store.messages(chat)[-1]
        self.assertEqual(answer['status'],'failed');self.assertIn('Modalità CPU',str(answer['meta']))

    def gemma(self):
        import struct
        path=Path(self.temp.name)/'Gemma-4-E2B.gguf'
        def string(value):
            raw=value.encode();return struct.pack('<Q',len(raw))+raw
        values={'general.architecture':'gemma4','general.name':'Gemma 4 E2B test'}
        path.write_bytes(b'GGUF'+struct.pack('<IQQ',3,0,len(values))+b''.join(string(k)+struct.pack('<I',8)+string(v) for k,v in values.items()))
        return self.app.external_model({'profile':'chat','name':'Gemma 4 CPU fixture','files':{'model':str(path)},'projector_mode':'off'})

    def test_gemma_cpu_choice_is_visible_and_survives_api_removal_and_reload(self):
        api=self.provider();model=self.gemma();before=self.app.store.settings()['chat_model']
        self.app.save_settings({'execution_mode':'cpu','cpu_chat_model':model['id']})
        self.assertEqual(self.app.effective_settings()['chat_model'],model['id']);self.assertEqual(self.app.store.settings()['chat_model'],before)
        self.assertEqual(self.app.engine.require_model(model['id'],'chat')['id'],model['id'])
        self.app.remove_provider(api);self.app.close();self.app=Service(ROOT,self.temp.name,start_worker=False);self.addCleanup(self.app.close)
        self.assertEqual(self.app.state()['execution']['chat_model'],model['id']);self.assertTrue(self.app.state()['execution']['chat_ready'])

    def test_preferences_choice_replaces_stale_cpu_api_and_legacy_deleted_id(self):
        api=self.provider();model=self.gemma();self.app.save_settings({'execution_mode':'cpu','cpu_chat_model':api})
        self.app.save_settings({'chat_model':model['id']})
        self.assertEqual(self.app.effective_settings()['chat_model'],model['id'])
        self.app.store.save_settings({'cpu_chat_model':'deleted-api-from-01856'})
        self.app.save_settings(self.app.store.settings())
        self.assertEqual(self.app.store.settings()['cpu_chat_model'],'');self.assertEqual(self.app.effective_settings()['chat_model'],model['id'])

    def test_local_cpu_start_uses_cpu_binary_zero_gpu_layers_and_standard_engine(self):
        from unittest.mock import Mock
        model=self.gemma();self.app.save_settings({'execution_mode':'cpu','cpu_chat_model':model['id']})
        session=Mock(ready=False,uses=0,process=Mock());session.process.poll.return_value=None
        self.app.engine.active=session
        response=Mock(status=200);response.__enter__=Mock(return_value=response);response.__exit__=Mock(return_value=False)
        with patch.object(self.app.engine,'_activate',return_value=session),patch('h3chat.llm_acceleration.plan',return_value=None),patch('h3chat.engine.runtime_executable',return_value=Path('runtime/cpu/llama/llama-server.exe')) as runtime,patch('urllib.request.urlopen',return_value=response):
            self.app.engine.start_llama(model,self.app.effective_settings(),Path(self.temp.name)/'test.log',threading.Event())
        self.assertEqual(runtime.call_args.args[1:3],('cpu','llama'))
        args=session.start.call_args.args[0];self.assertEqual(args[args.index('--n-gpu-layers')+1],0)
        self.assertEqual(args[args.index('--spec-type')+1],'none')

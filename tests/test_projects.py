import json,sqlite3,tempfile,threading,time,unittest
from pathlib import Path
from unittest.mock import patch
from h3chat.store import Store,DEFAULTS
from h3chat.rag import Knowledge,grounded,quote_warnings
from h3chat.service import Service
from h3chat.calculator import Calculator
from h3chat.lab import validate_scene,validate_chart,route
from h3chat.devices import options,label

ROOT=Path(__file__).resolve().parents[1]
class ProjectTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.path=Path(self.tmp.name);self.store=Store(self.path/'data');self.k=Knowledge(ROOT,self.store);self.cancel=threading.Event()
    def tearDown(self):self.k.close();self.tmp.cleanup()
    def project(self,name='Test'):return self.k.save({'name':name,'instructions':'Usa euro.','sources_only':True})
    def source(self,p,name,text):
        file=self.path/name;file.write_text(text,encoding='utf-8');self.store.execute('INSERT INTO project_sources(id,project_id,path,name) VALUES (?,?,?,?)',(name,p['id'],str(file),name));return file
    def retrieve(self,p,query,**cfg):return self.k.retrieve(p['id'],query,DEFAULTS|cfg,self.cancel,lambda _:None)
    def test_project_isolation_refresh_and_removed_file_never_returns_old_text(self):
        a=self.project('A');b=self.project('B');file=self.source(a,'a.md','Profitto 900 euro.');self.source(b,'b.md','Profitto 123 euro privato.');rows,mode=self.retrieve(a,'profitto');self.assertEqual(len(rows),1);self.assertIn('900',rows[0]['text']);self.assertEqual(mode,'lessicale')
        file.write_text('Profitto aggiornato 750 euro.',encoding='utf-8');rows,_=self.retrieve(a,'profitto');self.assertIn('750',rows[0]['text']);self.assertNotIn('900',rows[0]['text']);file.unlink();rows,_=self.retrieve(a,'profitto');self.assertEqual(rows,[])
    def test_selection_cannot_cross_projects_and_no_match_is_empty(self):
        a=self.project('A');b=self.project('B');self.source(a,'a.md','Ricavi 1200');self.source(b,'b.md','Ricavi 900');self.retrieve(a,'ricavi')
        self.assertEqual(self.k.retrieve(a['id'],'ricavi',DEFAULTS,self.cancel,lambda _:None,[])[0],[])
        with self.assertRaises(ValueError):self.k.retrieve(a['id'],'ricavi',DEFAULTS,self.cancel,lambda _:None,['b.md'])
        self.assertEqual(self.retrieve(a,'elefante')[0],[])
    def test_project_delete_preserves_chat_and_original_documents(self):
        p=self.project();file=self.source(p,'a.md','Ricavi 1200');chat=self.store.create_chat(project_id=p['id']);self.retrieve(p,'ricavi');self.k.delete(p['id']);self.assertIsNone(self.store.chat(chat['id'])['project_id']);self.assertTrue(file.exists());self.assertEqual(self.store.all('SELECT * FROM rag_chunks'),[])
    def test_folders_detect_new_files_and_do_not_restore_excluded_documents(self):
        p=self.project();folder=self.path/'folder';folder.mkdir();(folder/'first.md').write_text('profitto 100');self.k.add(p['id'],{'paths':[str(folder)]})
        for _ in range(100):
            if not self.k.project(p['id'])['indexing']:break
            time.sleep(.01)
        (folder/'new.md').write_text('profitto 200');rows,_=self.retrieve(p,'profitto');self.assertEqual(len(rows),2);source=next(s for s in self.k.project(p['id'])['sources'] if s['name']=='new.md');self.k.remove(p['id'],source['id']);self.assertEqual(len(self.retrieve(p,'profitto')[0]),1)
    def test_citations_and_literal_quotes_do_not_claim_unretrieved_sources(self):
        sources=[{'citation':'R1','text':'Il profitto è 900 euro.'}]
        result,unknown=grounded('Profitto [R1](https://fake.invalid). [R77].\n```python\nprint("[R77]")\n```',sources)
        self.assertIn('[R1](#rag-R1)',result);self.assertNotIn('fake.invalid',result);self.assertEqual(unknown,['R77']);self.assertIn('print("[R77]")',result)
        self.assertEqual(quote_warnings('“Il profitto è 900 euro.” [R1]',sources),[]);self.assertTrue(quote_warnings('“Il profitto è 999 euro.” [R1]',sources));self.assertTrue(quote_warnings('> Il profitto è 999 euro. [R1]',sources))
    def test_existing_database_migration_preserves_messages_and_collections(self):
        old=self.path/'old';old.mkdir();db=sqlite3.connect(old/'chat.sqlite');db.executescript("CREATE TABLE collections(id TEXT PRIMARY KEY,name TEXT); CREATE TABLE chats(id TEXT PRIMARY KEY,title TEXT,collection_id TEXT,pinned INTEGER,archived INTEGER,created REAL,updated REAL); INSERT INTO collections VALUES ('c','Raccolta'); INSERT INTO chats VALUES ('x','Chat','c',1,0,1,1);");db.close();store=Store(old);chat=store.chat('x');self.assertIsNone(chat['project_id']);self.assertEqual(chat['collection_id'],'c');self.assertEqual(chat['pinned'],1)
    def test_hybrid_retrieval_can_find_semantic_match_without_keyword_overlap(self):
        p=self.project();file=self.source(p,'cat.md','Un felino domestico dorme sul divano.');gguf=self.path/'embedding.gguf';gguf.touch();settings=DEFAULTS|{'rag_embedding_model':str(gguf)}
        with patch.object(self.k.embeddings,'encode',return_value=[[1.,0.,0.,0.,0.,0.,0.,0.]]) as encode:
            rows,mode=self.k.retrieve(p['id'],'gatto',settings,self.cancel,lambda _:None)
        self.assertEqual(len(rows),1);self.assertEqual(mode,'ibrida · CPU');self.assertEqual(encode.call_count,2)
    def test_chat_rag_citations_canvas_and_off(self):
        app=Service(ROOT,self.path/'service',start_worker=False);self.addCleanup(app.close);p=app.knowledge.save({'name':'Bilancio','instructions':'Usa euro.'});file=self.path/'bilancio.md';file.write_text('Profitto 900 euro.');app.store.execute('INSERT INTO project_sources(id,project_id,path,name) VALUES (?,?,?,?)',('src',p['id'],str(file),'Bilancio'));chat=app.store.create_chat(project_id=p['id']);model={'id':'fixture','name':'Fixture','vision':{'enabled':False},'capabilities':['chat'],'files':[]}
        for canvas,rag in ((True,True),(False,False)):
            with patch.object(app.engine,'require_model',return_value=model):ticket=app.send(chat['id'],{'prompt':'Quanto è il profitto?','canvas':canvas,'rag':rag})
            raw=json.dumps({'title':'Bilancio','content':'Profitto 900 euro [R1].'}) if canvas else 'Profitto 900 euro.'
            job=app.store.one('SELECT * FROM jobs WHERE id=?',(ticket['job_id'],))
            with patch.object(app.engine,'prepare'),patch.object(app.engine,'start_llama'),patch.object(app.engine,'require_model',return_value=model),patch.object(app.engine,'completion',return_value=(raw,'stop')) as completion:app.execute_job(job,self.cancel)
            self.assertEqual(app.store.one('SELECT status FROM jobs WHERE id=?',(job['id'],))['status'],'done');m=app.store.messages(chat['id'])[-1]
            self.assertIn('Usa euro.',completion.call_args.args[0][0]['content'])
            if rag:self.assertIn('[R1](#rag-R1)',m['meta']['artifact']['content']);self.assertNotIn('900',m['content']);self.assertEqual(m['meta']['rag_sources'][0]['text'],'Profitto 900 euro.')
            else:self.assertNotIn('rag_sources',m['meta'])

class CalculatorTests(unittest.TestCase):
    def test_exact_data_and_math(self):
        r=Calculator().run('import math\nxs = [x/2 for x in range(-6,7)]\nys = [x**2 for x in xs]\nprint(sum(ys))\narea = pi * 2**2')
        self.assertEqual(r['output'],'45.5');self.assertAlmostEqual(r['values']['area'],12.566370614359172)
    def test_no_io_attributes_imports_or_unbounded_work(self):
        for code in ('import os','open("data/chat.sqlite")','x = (1).__class__','while True: pass','x = [0]*10000000','x = 2**100000000','x = "%999999999s" % "a"','x = [i for i in range(1000000)]','x = [[0]*100]*1000'):
            with self.subTest(code=code),self.assertRaises((ValueError,SyntaxError)):Calculator().run(code)
    def test_scene_validations_reject_executable_inputs_and_bad_coordinates(self):
        self.assertEqual(route('Ricava dal PDF una animazione Manim'),'manim');validate_scene({'objects':[{'type':'plot','expression':'x**2'}]})
        for scene in ({'objects':[{'type':'plot','expression':'__import__("os").system("echo")'}]},{'objects':[{'type':'text','text':'X','x':100}]},{'objects':[{'type':'image','path':'secret'}]},{'scenes':[{'scenes':[{'objects':[{'type':'text','text':'Nested'}]}]}]}):
            with self.assertRaises(ValueError):validate_scene(scene)
        with self.assertRaises(ValueError):validate_chart({'type':'line','labels':['a'],'datasets':[{'data':[1,2]}]})
    def test_per_function_devices_are_independent(self):
        s=DEFAULTS|{'backend':'cuda','llm_device':'gpu','image_device':'cpu','music_backend':'cuda'};self.assertEqual(options(s,'image')['backend'],'cpu');self.assertEqual(options(s,'llm')['backend'],'cuda');self.assertEqual(label(s,'music'),'GPU · CUDA');self.assertEqual(label(s,'video'),'GPU · CUDA')
    def test_remote_only_selection_does_not_report_local_oom_or_require_gpu(self):
        from h3chat.hardware import assess_selection
        hardware={'gpu':[],'ram':{'free_mb':None}};models=[{'id':'remote-video','remote_media':True,'capabilities':['video'],'files':[]}]
        result=assess_selection(models,DEFAULTS,hardware);self.assertEqual(result['status'],'ok');self.assertEqual(result['vram_gb'],0);self.assertEqual(result['ram_gb'],0)

class ArtifactFlowTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.app=Service(ROOT,self.tmp.name,start_worker=False);self.cancel=threading.Event();self.model={'id':'fixture','name':'Fixture','files':[],'capabilities':['chat'],'vision':{'enabled':False}}
    def tearDown(self):self.app.close();self.tmp.cleanup()
    def job(self,body,project_id=None):
        chat=self.app.store.create_chat(project_id=project_id)
        with patch.object(self.app.engine,'require_model',return_value=self.model):ticket=self.app.send(chat['id'],body)
        return self.app.store.one('SELECT * FROM jobs WHERE id=?',(ticket['job_id'],))
    def test_calculation_executes_without_llm_and_canvas_contains_exact_chart_values(self):
        code='print(1200 - 300)\nchart = {"type":"bar","labels":["Profitto"],"datasets":[{"data":[1200-300]}]}'
        job=self.job({'prompt':'Calcolo','lab':'calculate','lab_source':code,'canvas':True})
        with patch.object(self.app.engine,'completion',side_effect=AssertionError('No LLM needed')):self.app.execute_job(job,self.cancel)
        answer=self.app.store.messages(job['chat_id'])[-1];self.assertEqual(answer['status'],'done');self.assertNotIn('900',answer['content']);self.assertIn('900',answer['meta']['artifact']['content']);self.assertEqual(answer['meta']['calculation']['values']['chart']['datasets'][0]['data'],[900])
    def test_pdf_to_manim_router_typed_instructions_and_canvas_destination(self):
        import base64
        from tests.test_tools import pdf_file
        item=self.app.upload({'name':'bilancio.pdf','data':base64.b64encode(pdf_file()).decode()});scene={'title':'Bilancio','scene_name':'Bilancio','code':'from manim import *\nclass Bilancio(Scene):\n def construct(self):\n  self.add(Text("Profitto 900 euro"));self.wait(8)'}
        original=self.app.engine.tool_call
        def render(worker,request,*args,**kw):
            if worker!='manim-worker.py':return original(worker,request,*args,**kw)
            self.assertEqual(request['source'],scene);target=Path(request['output'])/'animation.mp4';target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(b'fixture video transport');return {'path':str(target)}
        for canvas in (False,True):
            job=self.job({'prompt':'Ricava una animazione Manim dal PDF','media':[item],'canvas':canvas})
            with patch.object(self.app.engine,'require_model',return_value=self.model),patch.object(self.app.engine,'start_llama'),patch.object(self.app.engine,'completion',return_value=(json.dumps(scene),'stop')) as completion,patch.object(self.app.engine,'tool_call',side_effect=render),patch('h3chat.service.tools_status',return_value={'lab':{'ready':True},'latex':{'ready':True}}):self.app.execute_job(job,self.cancel)
            answer=self.app.store.messages(job['chat_id'])[-1];self.assertEqual(answer['status'],'done');self.assertEqual(answer['meta']['intent'],'manim');self.assertEqual(answer['meta']['documents'][0]['pages'],2);self.assertIn('profit 900 euros',completion.call_args.args[0][-1]['content']);self.assertIn('code',completion.call_args.kwargs['schema']['properties'])
            artifact=answer['meta']['artifact'];self.assertTrue(any(m['mime']=='video/mp4' for m in artifact['media']));self.assertEqual(bool(answer['media']),not canvas)
            if canvas:self.assertNotIn('Profitto 900',answer['content'])
    def test_web_pages_can_be_saved_to_project_and_retrieved_without_new_search(self):
        p=self.app.knowledge.save({'name':'Web'});source={'title':'Bilancio web','url':'https://example.com/bilancio','read':True,'snippet':'Estratto breve','text':'Il profitto web è 900 euro.'};job=self.job({'prompt':'Cerca sul web profitto','web':True},p['id'])
        with patch('h3chat.tools_engine.search',return_value=[source]),patch.object(self.app.engine,'require_model',return_value=self.model),patch.object(self.app.engine,'start_llama'),patch.object(self.app.engine,'completion',return_value=('Profitto web 900 [1].','stop')):self.app.execute_job(job,self.cancel)
        answer=self.app.store.messages(job['chat_id'])[-1];self.app.save_web_sources(p['id'],{'message_id':answer['id']})
        for _ in range(100):
            if not self.app.knowledge.project(p['id'])['indexing']:break
            time.sleep(.01)
        rows,_=self.app.knowledge.retrieve(p['id'],'profitto',DEFAULTS,self.cancel,lambda _:None);self.assertEqual(len(rows),1);self.assertIn(source['text'],rows[0]['text']);self.assertEqual(rows[0]['source_url'],source['url'])

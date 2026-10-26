"""Source files, H3 PDF and web-to-lot/RAG contracts without real inference."""
import importlib.util
import json
import os
from pathlib import Path
import sys
import threading
import unittest
from unittest.mock import patch,Mock
import test_agent_inputs as inputs
from test_agent_runtime import decision
from h3chat.agent_state import load
from h3chat.agent_files import filename

class AgentFilesWebTests(unittest.TestCase):
    setUp=inputs.AgentInputTests.setUp
    def tearDown(self):
        import time
        self.app.close()
        for attempt in range(25):
            try:self.tmp.cleanup();return
            except PermissionError:
                if attempt==24:raise
                time.sleep(.15)
    ticket=inputs.AgentInputTests.ticket
    drive=inputs.AgentInputTests.drive

    def web_job(self,**options):
        chat,job=self.ticket('agent: Cerca sul Web e importa i risultati',confirm_writes=False,**options)
        payload=json.loads(job['payload']);payload['settings']['_web']=True;job['payload']=json.dumps(payload)
        self.app.store.execute('UPDATE jobs SET payload=? WHERE id=?',(job['payload'],job['id']));return chat,job

    def test_source_project_zip_exists_without_executing_program(self):
        import zipfile
        chat,job=self.ticket('agent: Crea un programma Python',confirm_writes=False)
        source="raise RuntimeError('Program must not execute during creation')\n"
        state=self.drive(job,'create_files',{'title':'Programma','files':[{'name':'src/main.py','content':source},{'name':'README.md','content':'Istruzioni'},{'name':'src/__init__.py','content':''}]})
        artifact=self.app.store.canvas_history.get(chat,state['artifacts'][0]['id']);self.assertFalse(state['actions'][0]['result']['executed'])
        self.assertEqual((self.app.data/artifact['media'][0]['path']).read_text(encoding='utf8'),source)
        with zipfile.ZipFile(self.app.data/artifact['media'][-1]['path']) as archive:self.assertEqual(archive.read('src/main.py').decode(),source)

    def test_invalid_names_and_binary_extensions_are_rejected(self):
        for path in ('../private.py','C:/private.py','/tmp/a.py','a//b.py','CON.py','src/NUL.txt','app.exe','a.pdf','x:secret.txt','a\\b.py'):
            with self.subTest(path=path),self.assertRaises(ValueError):filename(path)

    def test_explicit_user_web_request_enables_web_without_changing_default(self):
        self.app.save_settings({'context':32768,'max_tokens':3000});chat=self.app.store.create_chat()['id']
        ticket=self.app.send(chat,{'prompt':'agent: Scaricami immagini sulle porte logiche da Internet e mettile in un lotto','rag':False,'web':False})
        settings=json.loads(self.app.store.one('SELECT payload FROM jobs WHERE id=?',(ticket['job_id'],))['payload'])['settings']
        self.assertTrue(settings['_web']);self.assertEqual(self.app.store.settings()['web_auto'],True)

    def test_public_pages_are_copied_with_source_url_then_indexed(self):
        chat,job=self.web_job(allow_projects=True);steps=[0];project=self.app.knowledge.save({'name':'Web'})
        rows=[{'title':'Logica','url':'https://example.org/logica','snippet':'Estratto','text':'La porta logica XOR confronta due ingressi.','read':True}]
        def choose(*a,**kw):
            steps[0]+=1
            if steps[0]==1:return decision('web_search',{'query':'porte logiche XOR'})
            if steps[0]==2:return decision('import_web_sources',{'project_id':project['id'],'numbers':[1,1]})
            if steps[0]==3:return decision('index_project',{'project_id':project['id'],'embedding_id':'lexical'})
            return decision('finish')
        with patch.object(self.app.engine,'prepare'),patch.object(self.app.engine,'start_llama'),patch.object(self.app.engine,'completion',side_effect=choose),patch('h3chat.web_search.search',return_value=rows):self.app.execute_job(job,threading.Event())
        state=load(self.app,chat,job['id']);self.assertEqual(state['status'],'done');self.assertTrue(all(a['status']=='done' for a in state['actions']),state)
        sources=self.app.knowledge.project(project['id'])['sources'];self.assertEqual(len(sources),1);self.assertEqual(sources[0]['source_url'],rows[0]['url']);self.assertEqual(sources[0]['status'],'ready')
        self.assertIn(rows[0]['url'],Path(sources[0]['path']).read_text(encoding='utf8'));self.assertTrue(state['actions'][1]['result']['sources'][1]['duplicate'])

    def test_search_image_candidates_download_to_real_lot_with_provenance(self):
        from test_image_batch import PNG
        from h3chat.image_collections import get
        chat,job=self.web_job();steps=[0]
        def choose(messages,*a,**kw):
            steps[0]+=1;data=json.loads(messages[-1]['content'])
            if steps[0]==1:return decision('search_web_images',{'query':'porte logiche','count':1})
            if steps[0]==2:
                source=json.loads(data['observations'][-1]['data'])['images'][0]['id'];return decision('import_web_images',{'image_ids':[source],'lot_name':'Porte logiche'})
            return decision('finish')
        def download(worker,request,*a,**kw):
            self.assertEqual(worker,'agent-web-image-worker.py');path=self.app.data/request['folder']/(request['id']+'.png');path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(PNG)
            return {'id':request['id'],'name':'immagine.png','mime':'image/png','path':path.relative_to(self.app.data).as_posix()}
        with patch.object(self.app.engine,'prepare'),patch.object(self.app.engine,'start_llama'),patch.object(self.app.engine,'completion',side_effect=choose),patch.object(self.app.engine,'tool_call',side_effect=download),patch('h3chat.web_search.search',return_value=[{'title':'Porte logiche','url':'https://example.org/article','text':'Testo letto','snippet':'','read':True}]),patch('h3chat.web_search.fetch',return_value='<img src="/xor.png" alt="Schema XOR">'),patch('h3chat.web_search.public_url',side_effect=lambda url:url):self.app.execute_job(job,threading.Event())
        state=load(self.app,chat,job['id']);self.assertEqual(state['status'],'done');self.assertTrue(all(a['status']=='done' for a in state['actions']),state)
        result=state['actions'][1]['result'];self.assertEqual(result['downloaded'],1);lot=get(self.app,result['lot_id'])
        self.assertEqual(lot['name'],'Porte logiche');self.assertEqual(lot['images'][0]['web_source']['page'],'https://example.org/article');self.assertEqual(lot['images'][0]['caption'],'')
        self.assertTrue((self.app.data/lot['images'][0]['media']['path']).is_file())

    def worker(self):
        path=self.app.root/'native/agent-web-image-worker.py';spec=importlib.util.spec_from_file_location('image_download_test',path);module=importlib.util.module_from_spec(spec);old=sys.stdout
        try:spec.loader.exec_module(module)
        finally:sys.stdout=old
        return module

    def test_downloader_denies_private_and_pins_connection_to_public_address(self):
        module=self.worker()
        for address in ('127.0.0.1','10.0.0.1','169.254.169.254','::1'):
            with self.subTest(address=address),patch.object(module.socket,'getaddrinfo',return_value=[(None,None,None,None,(address,80))]),patch.object(module.socket,'create_connection') as connect:
                with self.assertRaises(ValueError):module.download('http://example.org/image.png')
                connect.assert_not_called()
        response=Mock(status=200);response.getheader.return_value='identity';response.read.side_effect=[b'imagebytes',b''];connection=Mock();connection.getresponse.return_value=response
        with patch.object(module.socket,'getaddrinfo',return_value=[(None,None,None,None,('93.184.216.34',80))]),patch.object(module.socket,'create_connection') as connect,patch.object(module.http.client,'HTTPConnection',return_value=connection):
            self.assertEqual(module.download('http://example.org/image.png'),b'imagebytes');self.assertEqual(connect.call_args.args[0],('93.184.216.34',80));connection.close.assert_called_once()

    def test_image_worker_checks_real_format_and_preserves_download_bytes(self):
        import io
        from PIL import Image
        buffer=io.BytesIO();Image.new('RGB',(3,2),'blue').save(buffer,format='PNG');PNG=buffer.getvalue()
        module=self.worker();request={'data':str(self.app.data),'folder':'outputs/'+'d'*32,'id':'e'*32,'url':'https://example.org/file'}
        with patch.object(module,'download',return_value=PNG):result=module.run(request)
        self.assertEqual(result['mime'],'image/png');self.assertEqual((self.app.data/result['path']).read_bytes(),PNG)
        with patch.object(module,'download',return_value=b'<html>not an image</html>'):
            with self.assertRaises(Exception):module.run(request|{'id':'f'*32})

    @unittest.skipUnless(os.environ.get('H3_AGENT_LAYOUT_TEST')=='1','Real CPU PDF is opt-in.')
    def test_real_h3_pdf_worker_produces_pdf(self):
        result=self.app.engine.tool_call('agent-pdf-worker.py',{'data':str(self.app.data),'body':{'title':'Documento di prova','html':'<h1>Documento H3</h1><p>Creato su CPU.</p><script>throw Error()</script>'}},threading.Event(),lambda s:None,self.base/'pdf.log',timeout=120)
        raw=(self.app.data/result['url'].lstrip('/')).read_bytes();self.assertTrue(raw.startswith(b'%PDF-'));self.assertIn(b'%%EOF',raw[-100:])

if __name__=='__main__':unittest.main()

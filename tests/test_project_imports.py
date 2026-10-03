import base64
import io
import json
from pathlib import Path
import tempfile
import threading
import unittest
import urllib.error
import urllib.request

from app import Handler,ThreadingHTTPServer
from h3chat.service import Service
from h3chat.store import DEFAULTS

ROOT=Path(__file__).resolve().parents[1]

class ImportTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.app=Service(ROOT,self.temp.name,start_worker=False)
        self.addCleanup(self.temp.cleanup);self.addCleanup(self.app.close)
        self.project=self.app.knowledge.save({'name':'Import fixture'})

    def upload(self,**overrides):
        return self.app.knowledge.import_file(self.project['id'],{'name':'Ricavi.md','data':base64.b64encode(b'Ricavi verificati 1200 euro.').decode(),'defer':True}|overrides)

    def test_import_deduplication_persistence_and_retrieval(self):
        first=self.upload();source=self.app.knowledge.project(self.project['id'])['sources'][0]
        target=Path(source['path']);self.assertTrue(source['imported']);self.assertTrue(target.is_relative_to(Path(self.temp.name).resolve()/'project-imports'))
        modified=target.stat().st_mtime_ns;second=self.upload();self.assertEqual(first['id'],second['id']);self.assertTrue(second['duplicate']);self.assertEqual(target.stat().st_mtime_ns,modified)
        rows,_=self.app.knowledge.retrieve(self.project['id'],'ricavi',DEFAULTS,threading.Event(),lambda _:None);self.assertIn('1200',rows[0]['text'])
        other=self.app.knowledge.save({'name':'Other fixture'});self.assertEqual(self.app.knowledge.retrieve(other['id'],'ricavi',DEFAULTS,threading.Event(),lambda _:None)[0],[])

    def test_relative_folder_labels_and_no_path_injection(self):
        self.upload(relative_path='Lezioni/Capitolo1/Ricavi.md')
        self.assertEqual(self.app.knowledge.project(self.project['id'])['sources'][0]['name'],'Lezioni/Capitolo1/Ricavi.md')
        for name in ('../private.md','F:\\private.md','/private.md','file.exe'):
            with self.assertRaises(ValueError):self.upload(name=name)
        for relative in ('../Ricavi.md','C:/Ricavi.md','/Ricavi.md','Folder/./Ricavi.md'):
            with self.assertRaises(ValueError):self.upload(relative_path=relative)

    def test_invalid_empty_oversized_and_fake_documents_are_rejected(self):
        for change in ({'data':'bad!'}, {'data':''}, {'name':'fake.pdf'}, {'name':'fake.docx'}, {'data':'a'*(35*1024**2+1)}):
            with self.subTest(change=list(change)),self.assertRaises(ValueError):self.upload(**change)
        self.assertEqual(self.app.knowledge.project(self.project['id'])['sources'],[])

    def test_import_while_project_busy_is_rejected(self):
        chat=self.app.store.create_chat(project_id=self.project['id']);self.app.store.enqueue(chat['id'],'Fixture',[],DEFAULTS)
        with self.assertRaisesRegex(ValueError,'lavori'):self.upload()

    def test_real_word_import_and_text_extraction(self):
        import sys
        sys.path.insert(0,str(ROOT/'runtime/tools/documents'))
        from docx import Document
        doc=Document();doc.add_paragraph('Risultato verificato 4567.');stream=io.BytesIO();doc.save(stream)
        self.upload(name='Report.docx',data=base64.b64encode(stream.getvalue()).decode())
        rows,_=self.app.knowledge.retrieve(self.project['id'],'risultato',DEFAULTS,threading.Event(),lambda _:None)
        self.assertIn('4567',rows[0]['text'])

    def test_http_import_requires_token_and_keeps_contents_private(self):
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler);server.app=self.app;server.token='synthetic-token'
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        self.addCleanup(server.server_close);self.addCleanup(server.shutdown)
        url=f'http://127.0.0.1:{server.server_port}';body=json.dumps({'name':'file.html','data':base64.b64encode(b'<p>Source text</p>').decode(),'defer':True}).encode()
        def request(token):return urllib.request.Request(url+'/api/projects/'+self.project['id']+'/import',data=body,headers={'Content-Type':'application/json','X-H3-Token':token})
        with self.assertRaises(urllib.error.HTTPError) as denied:urllib.request.urlopen(request('wrong'))
        self.assertEqual(denied.exception.code,403)
        result=json.load(urllib.request.urlopen(request(self.app.token)));self.assertTrue(result['id'])
        path=Path(self.app.knowledge.project(self.project['id'])['sources'][0]['path']).relative_to(Path(self.temp.name).resolve()).as_posix()
        with self.assertRaises(urllib.error.HTTPError):urllib.request.urlopen(url+'/media/'+path)

if __name__=='__main__':unittest.main()

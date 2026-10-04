import hashlib,json,tempfile,threading,unittest,urllib.request,urllib.error
from pathlib import Path
from unittest.mock import patch
from app import Handler,ThreadingHTTPServer
from h3chat.service import Service
from h3chat.store import DEFAULTS
from h3chat.document_limits import RAG_FILE_BYTES,IMPORT_CHUNK_BYTES

ROOT=Path(__file__).resolve().parents[1]

class RagBookTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.app=Service(ROOT,self.tmp.name,start_worker=False)
        self.addCleanup(self.tmp.cleanup);self.addCleanup(self.app.close)
        self.project=self.app.knowledge.save({'name':'Synthetic books'})

    def start(self,**changes):
        return self.app.knowledge.uploads.start(self.project['id'],{'name':'book.pdf','size':26*1024**2,'defer':True}|changes)

    def test_large_binary_upload_is_bounded_deduplicated_and_private(self):
        count=26*1024**2;chunk=b'%PDF-'+b'x'*(IMPORT_CHUNK_BYTES-5)
        first=None
        for repeat in range(2):
            transfer=self.start();received=0
            while received<count:
                raw=chunk if received==0 else b'x'*min(IMPORT_CHUNK_BYTES,count-received)
                response=self.app.knowledge.uploads.append(self.project['id'],transfer['id'],received,raw);received=response['received']
            result=self.app.knowledge.uploads.finish(self.project['id'],transfer['id'])
            if first:self.assertEqual(result['id'],first['id']);self.assertTrue(result['duplicate'])
            else:first=result;self.assertFalse(result['duplicate'])
        source=self.app.knowledge.project(self.project['id'])['sources'][0]
        self.assertEqual(Path(source['path']).stat().st_size,count)
        self.assertEqual(list(self.app.knowledge.uploads.folder.glob('*.partial')),[])
        self.assertTrue(Path(source['path']).is_relative_to(Path(self.tmp.name).resolve()/'project-imports'))

    def test_partial_wrong_project_offsets_and_size_limits(self):
        for size in (0,True,RAG_FILE_BYTES+1):
            with self.assertRaises(ValueError):self.start(size=size)
        transfer=self.start(size=10);ident=transfer['id']
        other=self.app.knowledge.save({'name':'Other'})
        for project,offset,raw in ((other['id'],0,b'%PDF-'),(self.project['id'],1,b'%PDF-'),(self.project['id'],0,b'x'*(IMPORT_CHUNK_BYTES+1))):
            with self.assertRaises(ValueError):self.app.knowledge.uploads.append(project,ident,offset,raw)
        self.app.knowledge.uploads.append(self.project['id'],ident,0,b'%PDF-')
        with self.assertRaisesRegex(ValueError,'incompleto'):self.app.knowledge.uploads.finish(self.project['id'],ident)
        self.assertEqual(self.app.knowledge.project(self.project['id'])['sources'],[])
        self.app.knowledge.uploads.cancel(self.project['id'],ident)
        self.assertFalse((self.app.knowledge.uploads.folder/(ident+'.partial')).exists())
        deleted=self.app.knowledge.uploads.start(other['id'],{'name':'other.txt','size':10})
        self.app.knowledge.delete(other['id'])
        self.assertNotIn(deleted['id'],self.app.knowledge.uploads.pending)
        self.start(size=1);self.app.knowledge.close();self.assertEqual(list(self.app.knowledge.uploads.folder.glob('*.partial')),[])

    def test_native_book_over_25mb_and_300_pages_indexes_its_last_page(self):
        import sys
        sys.path.insert(0,str(ROOT/'runtime/tools/documents'))
        from pypdf import PdfWriter
        from pypdf.generic import DictionaryObject,NameObject,DecodedStreamObject
        path=Path(self.tmp.name)/'book.pdf';writer=PdfWriter()
        for _ in range(901):writer.add_blank_page(width=300,height=400)
        writer.add_metadata({'/Padding':'x'*(26*1024**2)})
        font=DictionaryObject({NameObject('/Type'):NameObject('/Font'),NameObject('/Subtype'):NameObject('/Type1'),NameObject('/BaseFont'):NameObject('/Helvetica')})
        writer.pages[-1][NameObject('/Resources')]=DictionaryObject({NameObject('/Font'):DictionaryObject({NameObject('/F1'):writer._add_object(font)})})
        content=DecodedStreamObject();content.set_data(b'BT /F1 12 Tf 20 200 Td (Ultimo capitolo: magnetismo verificato 778899.) Tj ET')
        writer.pages[-1][NameObject('/Contents')]=writer._add_object(content)
        with path.open('wb') as out:writer.write(out)
        self.assertGreater(path.stat().st_size,25*1024**2)
        transfer=self.start(size=path.stat().st_size);offset=0
        with path.open('rb') as inp:
            for raw in iter(lambda:inp.read(IMPORT_CHUNK_BYTES),b''):
                offset=self.app.knowledge.uploads.append(self.project['id'],transfer['id'],offset,raw)['received']
        self.app.knowledge.uploads.finish(self.project['id'],transfer['id'])
        self.assertTrue(path.exists())
        rows,_=self.app.knowledge.retrieve(self.project['id'],'magnetismo pagina 901',DEFAULTS,threading.Event(),lambda _:None)
        self.assertEqual(rows[0]['page'],901);self.assertIn('778899',rows[0]['text'])
        self.assertEqual(self.app.knowledge.project(self.project['id'])['sources'][0]['status'],'ready')
        # The ordinary chat reader keeps its separate attachment limits.
        with self.assertRaisesRegex(RuntimeError,'300 pagine'):
            self.app.engine.tool_call('document-worker.py',{'op':'read','path':str(path),'output':str(Path(self.tmp.name)/'chat.json')},threading.Event(),lambda _:None,Path(self.tmp.name)/'chat.log',timeout=90)

    def test_embeddings_stage_small_batches_and_failed_rebuild_is_atomic(self):
        path=Path(self.tmp.name)/'source.txt';path.write_text('Original')
        with patch.object(self.app.knowledge,'refresh'):self.app.knowledge.add(self.project['id'],{'paths':[str(path)]})
        blocks=[{'location':f'pagina {i+1}','page':i+1,'text':f'Chapter {i} magnetismo'} for i in range(513)]
        batches=[]
        def encode(texts,*args,**kw):batches.append(len(texts));return [[.5]*8 for _ in texts]
        settings=DEFAULTS|{'rag_embedding_model':'synthetic'}
        with patch.object(self.app.knowledge,'read',return_value=(blocks,[])),patch.object(self.app.knowledge.embeddings,'key',return_value='fixture'),patch.object(self.app.knowledge.embeddings,'encode',side_effect=encode):
            self.app.knowledge.index(self.project['id'],settings,threading.Event(),lambda _:None)
        self.assertEqual(sum(batches),513);self.assertLessEqual(max(batches),32)
        source=self.app.knowledge.project(self.project['id'])['sources'][0];old=self.app.store.all('SELECT text FROM rag_chunks WHERE source_id=?',(source['id'],))
        path.write_text('Modified source');calls=[0]
        def fail(texts,*args,**kw):
            calls[0]+=1
            if calls[0]==2:raise RuntimeError('Synthetic embedding failure')
            return [[.5]*8 for _ in texts]
        with patch.object(self.app.knowledge,'read',return_value=(blocks+blocks,[])),patch.object(self.app.knowledge.embeddings,'key',return_value='fixture'),patch.object(self.app.knowledge.embeddings,'encode',side_effect=fail):
            self.app.knowledge.index(self.project['id'],settings,threading.Event(),lambda _:None)
        self.assertEqual(self.app.store.all('SELECT text FROM rag_chunks WHERE source_id=?',(source['id'],)),old)
        self.assertEqual(self.app.knowledge.project(self.project['id'])['sources'][0]['status'],'error')
        self.assertEqual(list((Path(self.tmp.name)/'project-cache').glob('*.index.sqlite')),[])

    def test_binary_http_auth_and_finish(self):
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler);server.app=self.app
        threading.Thread(target=server.serve_forever,daemon=True).start();self.addCleanup(server.server_close);self.addCleanup(server.shutdown)
        base=f'http://127.0.0.1:{server.server_port}/api/projects/{self.project["id"]}/import'
        def request(url,body,method='POST',binary=False,token=None,offset=0):
            headers={'X-H3-Token':self.app.token if token is None else token,'Content-Type':'application/octet-stream' if binary else 'application/json','X-H3-Offset':str(offset)}
            return urllib.request.urlopen(urllib.request.Request(url,data=body if binary else json.dumps(body).encode(),headers=headers,method=method))
        with request(base+'/start',{'name':'book.pdf','size':10,'defer':True}) as r:transfer=json.load(r)
        with self.assertRaises(urllib.error.HTTPError) as error:request(base+'/'+transfer['id'],b'%PDF-12345','PATCH',True,'wrong')
        self.assertEqual(error.exception.code,403)
        with request(base+'/'+transfer['id'],b'%PDF-12345','PATCH',True) as r:self.assertEqual(json.load(r)['received'],10)
        with request(base+'/'+transfer['id']+'/finish',{}) as r:self.assertTrue(json.load(r)['id'])
        self.assertEqual(len(self.app.knowledge.project(self.project['id'])['sources']),1)

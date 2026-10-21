import base64
import hashlib
import json
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from types import SimpleNamespace
from app import Handler, ThreadingHTTPServer
from h3chat.service import Service
from h3chat.file_uploads import FileUploads, CHUNK_BYTES
from h3chat.store import Store
from h3chat.workspaces import guest_allowed

ROOT=Path(__file__).resolve().parents[1]

class FileUploadTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.app=SimpleNamespace(data=Path(self.tmp.name),closed=threading.Event(),store=Store(self.tmp.name))
        self.uploads=FileUploads(self.app);self.addCleanup(self.uploads.close)

    def send(self,name,raw,origin='uploaded'):
        transfer=self.uploads.start({'name':name,'size':len(raw),'origin':origin})
        if raw:self.uploads.append(transfer['id'],{'offset':0,'data':base64.b64encode(raw).decode()})
        return self.uploads.finish(transfer['id'])

    def test_unknown_formats_empty_and_json_preserve_original_bytes(self):
        for name,raw in [('sample.custom',b'\0\xffprivate'),('config.json',b'{"v":17}'),('no-extension',b'plain'),('empty.dat',b'')]:
            with self.subTest(name=name):
                media=self.send(name,raw);self.assertEqual((self.app.data/media['path']).read_bytes(),raw)
                metadata=json.loads((self.app.data/'uploads'/(media['id']+'.json')).read_text())
                self.assertEqual(metadata['path'],media['path']);self.assertEqual(media['size'],len(raw))
                self.assertEqual(self.app.store.gallery.get(media['id'])['path'],media['path'])

    def test_transfer_beyond_old_video_limit_is_bounded_and_exact(self):
        size=66*1024**2+23;transfer=self.uploads.start({'name':'large.mkv','size':size});ident=transfer['id']
        piece=b'x'*CHUNK_BYTES;hasher=hashlib.sha256()
        for offset in range(0,size,CHUNK_BYTES):
            raw=piece[:min(CHUNK_BYTES,size-offset)];hasher.update(raw)
            result=self.uploads.append(ident,{'offset':offset,'data':base64.b64encode(raw).decode()})
            self.assertEqual(result['received'],offset+len(raw))
        media=self.uploads.finish(ident);self.assertEqual(media['mime'],'video/x-matroska')
        with (self.app.data/media['path']).open('rb') as stream:self.assertEqual(hashlib.file_digest(stream,'sha256').hexdigest(),hasher.hexdigest())
        self.assertEqual(media['size'],size)
        huge=self.uploads.start({'name':'large.archive','size':10*1024**3})
        self.uploads.cancel(huge['id']);self.assertEqual(self.uploads.pending,{})

    def test_partial_order_and_workspace_isolation(self):
        ident=self.uploads.start({'name':'file.bin','size':2})['id']
        with self.assertRaisesRegex(ValueError,'incompleto'):self.uploads.finish(ident)
        with self.assertRaisesRegex(ValueError,'Ordine'):self.uploads.append(ident,{'offset':1,'data':'YQ=='})
        with tempfile.TemporaryDirectory() as folder:
            other=FileUploads(SimpleNamespace(data=Path(folder),closed=threading.Event()))
            with self.assertRaisesRegex(ValueError,'tua area'):other.append(ident,{'offset':0,'data':'YQ=='})
        self.uploads.append(ident,{'offset':0,'data':'YQ=='})
        with self.assertRaisesRegex(ValueError,'Dimensione'):self.uploads.append(ident,{'offset':1,'data':'YWE='})
        self.uploads.cancel(ident);self.assertFalse(list(self.uploads.folder.glob('*.partial')))

    def test_generated_exports_keep_deduplication(self):
        one=self.send('export.html',b'<p>test</p>','generated');two=self.send('export.html',b'<p>test</p>','generated')
        self.assertEqual(one['id'],two['id']);self.assertFalse(self.uploads.pending)

    def test_guest_routes_use_private_workspace(self):
        for route,method in [('/api/uploads/start','POST'),('/api/uploads/'+('a'*32)+'/chunk','POST'),('/api/uploads/'+('a'*32)+'/finish','POST'),('/api/uploads/'+('a'*32),'DELETE')]:self.assertTrue(guest_allowed(route,method))


class UploadHttpTests(unittest.TestCase):
    def test_http_chunks_token_streaming_range_and_metadata_privacy(self):
        with tempfile.TemporaryDirectory() as folder:
            app=Service(ROOT,folder,start_worker=False)
            server=ThreadingHTTPServer(('127.0.0.1',0),Handler);server.app=app;server.token=app.token
            threading.Thread(target=server.serve_forever,daemon=True).start()
            base=f'http://127.0.0.1:{server.server_port}'
            def call(path,body,token=app.token):
                request=urllib.request.Request(base+'/api'+path,data=json.dumps(body).encode(),headers={'Content-Type':'application/json','X-H3-Token':token})
                return json.load(urllib.request.urlopen(request))
            try:
                with self.assertRaises(urllib.error.HTTPError) as denied:call('/uploads/start',{'name':'file.bin','size':6},'wrong')
                self.assertEqual(denied.exception.code,403)
                ident=call('/uploads/start',{'name':'file.custom','size':6})['id']
                call('/uploads/'+ident+'/chunk',{'offset':0,'data':base64.b64encode(b'abcdef').decode()})
                media=call('/uploads/'+ident+'/finish',{})
                request=urllib.request.Request(base+'/media/'+media['path'],headers={'Range':'bytes=2-4'})
                with urllib.request.urlopen(request) as response:
                    self.assertEqual(response.status,206);self.assertEqual(response.read(),b'cde')
                    self.assertEqual(response.headers['Content-Type'],'application/octet-stream')
                    self.assertEqual(response.headers['Content-Disposition'],'attachment')
                for path in ('/media/uploads/'+ident+'.json','/media/upload-cache/'+ident+'.partial'):
                    with self.assertRaises(urllib.error.HTTPError):urllib.request.urlopen(base+path)
            finally:server.shutdown();server.server_close();app.close()

if __name__=='__main__':unittest.main()

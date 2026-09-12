import io
import json
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
import zipfile
from pathlib import Path
from unittest.mock import patch

from h3chat.downloads import download,extract_zip,safe_join,Cancelled
from h3chat.service import Service,partial_string
from h3chat.engine import explicit_route
from h3chat.pdf_export import Sanitizer
from h3chat.store import Store,DEFAULTS
from app import Handler,ThreadingHTTPServer

ROOT=Path(__file__).resolve().parents[1]


class CoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.data=Path(self.tmp.name)
        self.app=Service(ROOT,self.data,start_worker=False)
    def tearDown(self):
        self.app.close();self.tmp.cleanup()

    def test_chat_lifecycle_and_collection_cascade(self):
        s=self.app.store
        s.execute('INSERT INTO collections VALUES (?,?)',('work','Lavoro'))
        c=s.create_chat('Prova','work')
        s.execute('UPDATE chats SET pinned=1,archived=1 WHERE id=?',(c['id'],))
        self.assertTrue(s.chat(c['id'])['pinned'])
        s.execute('DELETE FROM collections WHERE id=?',('work',))
        self.assertIsNone(s.chat(c['id'])['collection_id'])
        with self.assertRaisesRegex(ValueError,'archivio'):
            s.enqueue(c['id'],'ciao',[],DEFAULTS)
        self.app.delete_chat(c['id'])
        with self.assertRaises(ValueError):s.chat(c['id'])

    def test_enqueue_snapshot_duplicate_and_cancel(self):
        c=self.app.store.create_chat()
        job=self.app.store.enqueue(c['id'],'ciao',[],DEFAULTS,True)
        with self.assertRaisesRegex(ValueError,'Attendi'):
            self.app.store.enqueue(c['id'],'again',[],DEFAULTS)
        with self.assertRaises(ValueError):self.app.delete_chat(c['id'])
        self.app.store.save_settings({'temperature':1.5})
        payload=json.loads(self.app.store.one('SELECT * FROM jobs WHERE id=?',(job,))['payload'])
        self.assertEqual(payload['settings']['temperature'],0.7)
        self.assertTrue(payload['canvas'])
        self.app.cancel(job)
        self.assertEqual(self.app.store.chat(c['id'])['messages'][-1]['status'],'cancelled')

    def test_restart_marks_partial_answers_interrupted(self):
        c=self.app.store.create_chat()
        job=self.app.store.enqueue(c['id'],'ciao',[],DEFAULTS)
        self.app.store.execute("UPDATE jobs SET status='running' WHERE id=?",(job,))
        s=Store(self.data)
        self.assertEqual(s.one('SELECT status FROM jobs WHERE id=?',(job,))['status'],'interrupted')
        self.assertEqual(s.chat(c['id'])['messages'][-1]['status'],'interrupted')

    def test_bad_settings_and_attachment_limits(self):
        for p in ({'backend':'remote'},{'context':True},{'width':510},{'temperature':float('nan')},{'chat_model':'sd15'},{'profile':'nope'}):
            with self.assertRaises(ValueError):self.app.save_settings(p)
        with self.assertRaises(ValueError):self.app.validate_media([{}]*5)
        with self.assertRaises(ValueError):self.app.validate_media([{'id':'../passwd'}])

    def test_path_and_zip_traversal_are_rejected_before_writes(self):
        for p in ('../outside','C:/Windows/file','/outside'):
            with self.assertRaises(ValueError):safe_join(self.data,p)
        z=self.data/'bad.zip'
        with zipfile.ZipFile(z,'w') as out:
            out.writestr('good.txt','good');out.writestr('../outside.txt','bad')
        with self.assertRaises(ValueError):extract_zip(z,self.data/'dest')
        self.assertFalse((self.data/'dest/good.txt').exists())

    def test_download_resume_and_checksum(self):
        import hashlib
        content=b'correct contents';sha=hashlib.sha256(content).hexdigest();target=self.data/'model.bin'
        target.with_suffix('.bin.part').write_bytes(content[:4])
        class Response(io.BytesIO):
            status=206
            headers={'Content-Range':'bytes 4-15/16'}
        with patch('h3chat.downloads.request',return_value=Response(content[4:])):
            download('https://example.com/m',target,sha,len(content),threading.Event(),lambda *_:None)
        self.assertEqual(target.read_bytes(),content)
        bad=self.data/'bad.bin'
        class Whole(io.BytesIO):
            status=200
            headers={}
        with patch('h3chat.downloads.request',return_value=Whole(b'bad')):
            with self.assertRaisesRegex(ValueError,'SHA-256'):
                download('https://example.com/m',bad,'0'*64,3,threading.Event(),lambda *_:None)
        self.assertFalse(bad.exists());self.assertFalse(bad.with_suffix('.bin.part').exists())

    def test_partial_canvas_json_stream_escapes(self):
        source=json.dumps({'reply':'Fatto.','title':'Somma','content':'# Ciao\n\\frac{1}{2}\n"code"'})
        for end in range(1,len(source)+1):
            result=partial_string(source[:end],'content')
            self.assertTrue('# Ciao\n\\frac{1}{2}\n"code"'.startswith(result))
        self.assertEqual(partial_string(source,'content'),'# Ciao\n\\frac{1}{2}\n"code"')

    def test_multiref_arguments_retain_order_and_reject_extra(self):
        model=self.app.catalog['flux2-klein4'];settings=DEFAULTS|{'profile':'cpu'}
        refs=[{'path':f'uploads/{i}.png'} for i in range(4)]
        with patch('h3chat.engine.runtime_executable',return_value=self.data/'sd-cli.exe'):
            args=self.app.engine.image_args(model,settings,'test',refs,self.data/'out.png')
            self.assertEqual(args.count('--ref-image'),4)
            paths=[str(args[i+1]) for i,arg in enumerate(args) if arg=='--ref-image']
            self.assertTrue(paths[0].endswith('0.png'));self.assertTrue(paths[-1].endswith('3.png'))
            with self.assertRaises(ValueError):self.app.engine.image_args(model,settings,'test',refs+[refs[0]],self.data/'out.png')

    def test_canvas_output_not_in_body_and_engine_release(self):
        s=self.app.store;c=s.create_chat();jobid=s.enqueue(c['id'],'Scrivi codice',[],DEFAULTS|{'chat_model':'qwen3-06'},True)
        job=s.one('SELECT * FROM jobs WHERE id=?',(jobid,))
        raw=json.dumps({'reply':'Creato nel canvas.','title':'Codice','content':'```python\nprint(42)\n```'})
        def completion(*args,**kwargs):
            kwargs['on_text'](raw[:40]);kwargs['on_text'](raw);return raw,'stop'
        with patch.object(self.app.engine,'require_model',return_value=self.app.catalog['qwen3-06']),patch.object(self.app.engine,'start_llama'),patch.object(self.app.engine,'route',return_value={'intent':'chat','prompt':''}),patch.object(self.app.engine,'completion',side_effect=completion),patch.object(self.app.engine,'stop') as stop:
            self.app.execute_job(job,threading.Event())
            stop.assert_called()
        self.assertEqual(s.chat(c['id'])['messages'][-1]['content'],'Creato nel canvas.')
        self.assertIn('print(42)',s.one('SELECT content FROM canvases WHERE chat_id=?',(c['id'],))['content'])

    def test_prompt_routing_and_pdf_sanitizer(self):
        cases=[('Crea un ritratto ad acquerello.',0,'create'),('Modifica le quattro foto allegate: combina gli oggetti.',4,'edit'),('Ricostruisci il grafico nella foto.',1,'chat'),('Scrivi una funzione Python.',0,'chat')]
        for prompt,count,expected in cases:
            self.assertEqual(explicit_route([{'content':prompt,'media':[{}]*count}]),expected)
        parser=Sanitizer();parser.feed('<script>alert(1)</script><p onclick="evil()">Testo</p><img src="file:///secret"><svg><text>Router</text></svg>')
        output=''.join(parser.output)
        self.assertNotIn('script',output);self.assertNotIn('onclick',output);self.assertNotIn('file://',output)
        self.assertIn('Router',output)
        self.assertEqual(partial_string('{"content":"\\ud83d\\ude00"}', 'content'), chr(0x1f600))

    def test_origin_and_session_guards(self):
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler);server.app=self.app
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        url=f'http://127.0.0.1:{server.server_port}'
        try:
            for headers in ({'Origin':'https://evil.example'},{'Host':'evil.example'}):
                with self.assertRaises(urllib.error.HTTPError) as cm:urllib.request.urlopen(urllib.request.Request(url+'/api/state',headers=headers))
                self.assertEqual(cm.exception.code,403)
            for token in ('',self.app.token):
                request=urllib.request.Request(url+'/api/chats',data=b'{}',headers={'Content-Type':'application/json','X-H3-Token':token})
                if not token:
                    with self.assertRaises(urllib.error.HTTPError) as cm:urllib.request.urlopen(request)
                    self.assertEqual(cm.exception.code,403)
                else:
                    with urllib.request.urlopen(request) as response:self.assertEqual(response.status,201)
        finally:server.shutdown();server.server_close()


if __name__=='__main__':unittest.main()

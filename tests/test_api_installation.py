"""Windows API installation checks with no CUDA, weights or native engines.

All databases and generated files live under a temporary fresh-clone fixture.
The provider is an in-process fake; no external/paying API is contacted.
"""
import base64
import importlib.util
import json
import shutil
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

from h3chat.installation_profile import API_SETTINGS, first_run_settings, write_profile
from h3chat.service import Service

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
spec=importlib.util.spec_from_file_location('api_clone_install',ROOT/'scripts/install.py')
installer=importlib.util.module_from_spec(spec);spec.loader.exec_module(installer)
PNG=base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aOKsAAAAASUVORK5CYII=')


def example(schema):
    if 'enum' in schema:return 'chat' if 'chat' in schema['enum'] else schema['enum'][0]
    kind=schema.get('type')
    if kind=='object':return {k:example(v) for k,v in schema.get('properties',{}).items() if k in schema.get('required',[])}
    if kind=='array':return []
    if kind=='boolean':return False
    if kind in ('integer','number'):return schema.get('minimum',1)
    return 'API fixture'


class Provider(BaseHTTPRequestHandler):
    def log_message(self,*args):pass
    def do_POST(self):
        body=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        self.server.calls.append((self.path,body));self.send_response(200);self.end_headers()
        if self.path.endswith('/images/generations'):
            value={'data':[{'b64_json':base64.b64encode(PNG).decode()}]}
        else:
            text='Risposta remota senza GPU.'
            if body['messages'][0]['content'].startswith('Return only a JSON object'):
                text=json.dumps(example(json.loads(body['messages'][0]['content'].split('\n',1)[1])))
            if body.get('stream'):
                self.wfile.write(('data: '+json.dumps({'choices':[{'delta':{'content':text},'finish_reason':'stop'}]})+'\n\ndata: [DONE]\n\n').encode());return
            value={'choices':[{'message':{'content':text},'finish_reason':'stop'}]}
        self.wfile.write(json.dumps(value).encode())


class ApiInstallationTests(unittest.TestCase):
    def test_api_installer_downloads_only_document_tools_and_never_starts_native_engines(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            with patch.object(installer,'ROOT',root),patch.object(installer,'install_bundle') as bundle,patch.object(installer,'install_runtime') as runtime,patch.object(installer.subprocess,'run') as native:
                installer.install_components(api_only=True)
            bundle.assert_called_once_with();runtime.assert_called_once_with('tools_documents');native.assert_not_called()
            self.assertEqual(first_run_settings(root,False),API_SETTINGS)
            self.assertFalse((root/'data').exists());self.assertFalse((root/'models').exists())

    def test_first_run_api_preferences_do_not_migrate_or_change_existing_users(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);self.assertEqual(first_run_settings(root,False),{})
            write_profile(root,True);self.assertEqual(first_run_settings(root,True),{})
            value=first_run_settings(root,False);self.assertEqual(value['rag_device'],'cpu');self.assertEqual(value['music_model'],'')
            value['backend']='cuda';self.assertEqual(API_SETTINGS['backend'],'cpu')
            write_profile(root,False);self.assertEqual(first_run_settings(root,False),{})
            (root/'runtime/installation-profile.json').write_text('{broken')
            self.assertEqual(first_run_settings(root,False),{})

    def test_standard_install_still_prepares_and_checks_cpu_engines(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            reply=type('Reply',(),{'returncode':0,'stdout':b'{"event":"hello"}'})()
            with patch.object(installer,'ROOT',root),patch.object(installer,'install_bundle'),patch.object(installer,'install_runtime') as runtime,patch.object(installer.subprocess,'run',return_value=reply) as native:
                installer.install_components()
            self.assertEqual([call.args[0] for call in runtime.call_args_list],['cpu','music_cpu','tools_documents'])
            self.assertEqual(native.call_count,2);self.assertEqual(first_run_settings(root,False),{})

    def test_fresh_clone_runs_api_chat_canvas_and_images_without_any_native_runtime(self):
        with tempfile.TemporaryDirectory(prefix='H3 fresh clone ') as folder:
            root=Path(folder)
            for name in ('catalog.json','runtimes.json','tools-models.json','upscale-runtimes.json','remix-runtimes.json'):
                shutil.copyfile(ROOT/name,root/name)
            write_profile(root,True)
            app=Service(root,start_worker=False)
            server=None
            try:
                settings=app.store.settings();self.assertEqual(settings['backend'],'cpu');self.assertEqual(settings['music_model'],'')
                self.assertEqual(list(root.glob('runtime/*/llama/*.exe')),[]);self.assertFalse((root/'models').exists())
                server=ThreadingHTTPServer(('127.0.0.1',0),Provider);server.calls=[]
                thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start();url=f'http://127.0.0.1:{server.server_port}/v1'
                llm=app.provider_request({'name':'API-only QA','base_url':url,'model':'qa-llm','vision':False,'max_refs':4,'thinking':'none','format':'json_object','api_key':''})
                image=app.media_provider_request({'name':'Remote image','base_url':url,'model':'qa-image','role':'image','adapter':'openai-images'})
                app.save_settings({'chat_model':llm['id'],'create_model':image['id'],'edit_model':image['id'],'setup_done':True})
                with patch('h3chat.residency.subprocess.Popen',side_effect=AssertionError('A local model must not start in API-only checks')),patch('h3chat.downloads.Downloads.start',side_effect=AssertionError('No automatic model downloads')):
                    chat=app.store.create_chat()
                    sent=app.send(chat['id'],{'prompt':'Spiegami i generatori Python','media':[]})
                    app.execute_job(app.store.one('SELECT * FROM jobs WHERE id=?',(sent['job_id'],)),threading.Event())
                    answer=app.store.messages(chat['id'])[-1];self.assertEqual(answer['status'],'done',answer);self.assertEqual(answer['content'],'Risposta remota senza GPU.');self.assertTrue(answer['meta']['api'])
                    sent=app.send(chat['id'],{'prompt':'Spiega nel canvas','media':[],'canvas':True})
                    app.execute_job(app.store.one('SELECT * FROM jobs WHERE id=?',(sent['job_id'],)),threading.Event())
                    answer=app.store.messages(chat['id'])[-1];self.assertEqual(answer['status'],'done',answer);self.assertEqual(answer['meta']['artifact']['content'],'API fixture')
                    sent=app.send(chat['id'],{'prompt':'Crea un cerchio blu','media':[],'image_model':image['id'],'assistant':False})
                    app.execute_job(app.store.one('SELECT * FROM jobs WHERE id=?',(sent['job_id'],)),threading.Event())
                    answer=app.store.messages(chat['id'])[-1];self.assertEqual(answer['status'],'done',answer)
                    output=(app.data/answer['media'][0]['path']).read_bytes();self.assertTrue(output.startswith(PNG[:33]));self.assertTrue(output.endswith(PNG[-12:]));self.assertIn(b'h3_creation',output)
                    self.assertEqual(app.engine.sessions,{})
                self.assertTrue(any(path.endswith('/chat/completions') for path,_ in server.calls));self.assertTrue(any(path.endswith('/images/generations') for path,_ in server.calls))
                hardware={'cpu_name':'CPU only QA','cpu_threads':4,'ram':{'total_mb':8192,'free_mb':6144},'gpu':[],'note':'Fixture senza GPU'}
                with patch('h3chat.service.detect_hardware',return_value=hardware):report=app.assess({})
                self.assertEqual(report['overall']['vram_gb'],0);self.assertEqual(report['hardware']['gpu'],[])
                # Reopening the same database must not reapply the installer defaults.
                app.close();app=Service(root,start_worker=False);self.assertEqual(app.store.settings()['chat_model'],llm['id'])
            finally:
                app.close()
                if server:server.shutdown();server.server_close()


if __name__=='__main__':unittest.main()

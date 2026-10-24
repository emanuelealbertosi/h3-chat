"""Smoke tests of the staged Apple distribution, with disposable user data only."""
import hashlib,json,os,platform,shutil,subprocess,sys,tempfile,threading,time,urllib.request
from pathlib import Path
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
ROOT=Path(__file__).resolve().parents[1]
STAGE=Path(json.loads((ROOT/'build/macos-stage.json').read_text())['path'])
sys.path[:0]=[str(STAGE),str(STAGE/'runtime/tools/documents')]
from h3chat.service import Service
from h3chat.providers import protect
from h3chat.engine import runtime_executable
from h3chat.tools_runtime import status

assert sys.platform=='darwin' and platform.machine()=='arm64'
errors=[]
subprocess.run(['codesign','--verify','--deep','--strict',STAGE/'H3-Chat.app'],check=True)
for backend in ('cpu','metal'):
    exe=runtime_executable(STAGE,backend,'llama');assert exe
    try:result=subprocess.run([exe,'--version'],capture_output=True,text=True,timeout=120)
    except subprocess.TimeoutExpired as exc:
        print('Native startup stdout:',(exc.stdout or b'')[-4000:],flush=True)
        print('Native startup stderr:',(exc.stderr or b'')[-8000:],flush=True)
        raise
    assert result.returncode==0,(backend,result.stderr)
assert status(STAGE)['documents']['ready']
assert protect(protect('h3-macos-disposable-test'),True)=='h3-macos-disposable-test'

class FakeProvider(BaseHTTPRequestHandler):
    def log_message(self,*args):pass
    def do_POST(self):
        request=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        schema=request.get('response_format',{}).get('json_schema',{}).get('schema')
        text=json.dumps({'intent':'chat','prompt':''}) if schema and 'intent' in schema.get('properties',{}) else 'Risposta del provider di prova Mac.'
        if request.get('stream'):
            data=('data: '+json.dumps({'choices':[{'delta':{'content':text},'finish_reason':'stop'}]})+'\n\ndata: [DONE]\n\n').encode();content_type='text/event-stream'
        else:
            data=json.dumps({'choices':[{'message':{'role':'assistant','content':text},'finish_reason':'stop'}]}).encode();content_type='application/json'
        self.send_response(200);self.send_header('Content-Type',content_type);self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)

server=ThreadingHTTPServer(('127.0.0.1',0),FakeProvider);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
try:
 with tempfile.TemporaryDirectory(prefix='h3-macos-test-') as folder:
    data=Path(folder);app=Service(STAGE,data,start_worker=False)
    try:
        state=app.state();assert state['platform']['system']=='darwin';assert state['runtimes']['cpu']['ready'];assert state['runtimes']['metal']['ready']
        provider=app.provider_request({'name':'Mac test','base_url':f'http://127.0.0.1:{server.server_port}/v1','model':'test','vision':False,'max_refs':4,'thinking':'none','format':'json_schema','api_key':'disposable-macos-key'})
        app.save_settings({'chat_model':provider['id'],'web_auto':False})
        chat=app.store.create_chat()['id'];sent=app.send(chat,{'prompt':'Rispondi in italiano','canvas':False})
        job=app.store.one('SELECT * FROM jobs WHERE id=?',(sent['job_id'],));app.execute_job(job,threading.Event())
        answer=app.store.messages(chat)[-1];assert answer['status']=='done',answer['meta'].get('error');assert 'provider di prova Mac' in answer['content']
        assert 'disposable-macos-key' not in json.dumps(app.state())
        from docx import Document
        path=data/'uploads/mac-test.docx';path.parent.mkdir(exist_ok=True);doc=Document();doc.add_paragraph('Documento Mac: velocità 42 e colore blu.');doc.save(path)
        read=app.engine.read_document({'id':'mac-test','name':path.name,'path':'uploads/mac-test.docx','mime':'application/vnd.openxmlformats-officedocument.wordprocessingml.document'},threading.Event(),lambda _:None,data/'logs/document-test.log')
        assert 'velocità 42' in str(read)
        project=app.knowledge.save({'name':'Mac RAG','instructions':'Usa soltanto le fonti.','sources_only':True})
        app.store.execute('INSERT INTO project_sources(id,project_id,path,name) VALUES (?,?,?,?)',('mac-rag-source',project['id'],str(path),path.name))
        rows,mode=app.knowledge.retrieve(project['id'],'colore',app.store.settings(),threading.Event(),lambda _:None)
        assert rows and 'blu' in str(rows) and mode=='lessicale'
        # The HTTP app binds only to loopback and authenticates its existing routes.
        sys.path.insert(0,str(STAGE));from app import Handler,ThreadingHTTPServer as AppServer
        http=AppServer(('127.0.0.1',0),Handler);http.app=app
        from h3chat.access import Access
        from h3chat.workspaces import Workspaces
        http.access=Access(data);http.workspaces=Workspaces(app)
        http.network=None
        runner=threading.Thread(target=http.serve_forever,daemon=True);runner.start()
        try:
            with urllib.request.urlopen(f'http://127.0.0.1:{http.server_port}/api/health',timeout=5) as response:assert json.load(response)['app']=='h3-chat'
        finally:http.shutdown();http.server_close();http.workspaces.close()
        from h3chat.pdf_export import export_pdf
        try:
            result=export_pdf(STAGE,data,{'title':'Mac PDF','html':'<h1>PDF vettoriale di prova Mac</h1><p>Contenuto verificato.</p>'})
            assert (data/result['url'].lstrip('/')).read_bytes().startswith(b'%PDF-'),result
        except Exception as exc:
            errors.append('PDF: '+str(exc));print(errors[-1],flush=True)
    finally:app.close()
finally:server.shutdown();server.server_close()

# Exercise the actual .app executable after relocating the complete portable folder.
# Hard links avoid copying the browser twice; all mutable files go to disposable data.
def linked_copy(source,target):
    try:os.link(source,target);return target
    except OSError:return shutil.copy2(source,target)

with tempfile.TemporaryDirectory(prefix='h3-macos-relocated-') as folder:
    relocated=Path(folder).resolve()/'H3 Chat with spaces'
    shutil.copytree(STAGE,relocated,symlinks=True,copy_function=linked_copy,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    executable=relocated/'H3-Chat.app/Contents/MacOS/H3-Chat'
    with (Path(folder)/'launcher.log').open('wb') as log:
        process=subprocess.Popen([executable,'--logs-only'],stdout=log,stderr=log)
        try:
            expected=hashlib.sha256(str(relocated).encode()).hexdigest()[:16]
            ready=False;deadline=time.monotonic()+50
            while time.monotonic()<deadline:
                marker=relocated/'data/port.json'
                if marker.exists():
                    port=json.loads(marker.read_text())
                    try:
                        with urllib.request.urlopen(f'http://127.0.0.1:{port}/api/health',timeout=2) as response:ready=json.load(response)['instance']==expected
                        if ready:break
                    except OSError:pass
                if process.poll() is not None:break
                time.sleep(.3)
            assert ready,'Relocated native app launcher did not expose its owned loopback server.'
            assert (relocated/'data').stat().st_mode&0o077==0,'Mac user data must be private.'
        finally:
            subprocess.run([executable,'--stop'],capture_output=True,timeout=50)
            try:process.wait(timeout=12)
            except subprocess.TimeoutExpired:process.terminate();process.wait(timeout=5)
assert not errors,errors
print('macOS arm64: native CPU/Metal startup, Keychain, API chat, documents, RAG, PDF, loopback HTTP and relocated native app launcher/stop passed. No model weights loaded.')

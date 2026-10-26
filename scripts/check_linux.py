"""Linux packaged smoke tests, temporary data and a simulated API provider."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer

ROOT=Path(__file__).resolve().parents[1]
stage=Path(sys.argv[1]).resolve() if len(sys.argv)>1 else ROOT/'build/linux/H3-Chat'
sys.path[:0]=[str(stage),str(stage/'runtime/tools/documents')]
assert sys.platform.startswith('linux') and os.geteuid()!=0

class Provider(BaseHTTPRequestHandler):
    def log_message(self,*args):pass
    def do_POST(self):
        value=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        schema=value.get('response_format',{}).get('json_schema',{}).get('schema',{})
        text=json.dumps({'intent':'chat','prompt':''}) if 'intent' in schema.get('properties',{}) else 'Risposta Linux verificata.'
        if value.get('stream'):raw=('data: '+json.dumps({'choices':[{'delta':{'content':text},'finish_reason':'stop'}]})+'\n\ndata: [DONE]\n\n').encode();mime='text/event-stream'
        else:raw=json.dumps({'choices':[{'message':{'role':'assistant','content':text},'finish_reason':'stop'}]}).encode();mime='application/json'
        self.send_response(200);self.send_header('Content-Type',mime);self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)


from h3chat.service import Service
from h3chat.providers import protect
from h3chat.tools_runtime import status
from h3chat.pdf_export import export_pdf
from h3chat.engine import runtime_executable
from docx import Document
assert protect(protect('h3-linux-disposable-test'),True)=='h3-linux-disposable-test'
for key in ('documents','lab','asr','latex'):assert status(stage)[key]['ready'],(key,status(stage))
llama=runtime_executable(stage,'cpu','llama');assert llama
result=subprocess.run([str(llama),'--version'],capture_output=True,timeout=60);assert result.returncode==0,result.stderr[-2000:]
for worker in (stage/'native/h3-sd-worker',stage/'runtime/music/cpu/h3-music-worker'):
    result=subprocess.run([str(worker)],input=b'',capture_output=True,timeout=60);assert result.returncode==0,(worker,result.stderr[-2000:])
    assert json.loads(result.stdout.splitlines()[0])['event']=='hello'
server=ThreadingHTTPServer(('127.0.0.1',0),Provider);threading.Thread(target=server.serve_forever,daemon=True).start()
try:
 with tempfile.TemporaryDirectory(prefix='h3-linux-data-') as temporary:
    data=Path(temporary);app=Service(stage,data,start_worker=False)
    try:
        model=app.provider_request({'name':'Linux test','base_url':f'http://127.0.0.1:{server.server_port}/v1','model':'test','vision':False,'max_refs':1,'thinking':'none','format':'json_schema','api_key':'disposable-test-only'})
        app.save_settings({'chat_model':model['id'],'web_auto':False})
        chat=app.store.create_chat()['id'];sent=app.send(chat,{'prompt':'Rispondi in italiano','canvas':False})
        job=app.store.one('SELECT * FROM jobs WHERE id=?',(sent['job_id'],));app.execute_job(job,threading.Event())
        answer=app.store.messages(chat)[-1];assert answer['status']=='done',answer['meta'];assert 'Linux verificata' in answer['content']
        path=data/'uploads/test.docx';path.parent.mkdir(exist_ok=True);doc=Document();doc.add_paragraph('Fonte Linux: colore blu e velocità 42.');doc.save(path)
        project=app.knowledge.save({'name':'RAG Linux','sources_only':True})
        app.store.execute('INSERT INTO project_sources(id,project_id,path,name) VALUES (?,?,?,?)',('linux-source',project['id'],str(path),path.name))
        rows,mode=app.knowledge.retrieve(project['id'],'colore',app.store.settings(),threading.Event(),lambda _:None)
        assert rows and 'blu' in str(rows),rows
        exported=export_pdf(stage,data,{'title':'Linux PDF','html':'<h1>PDF di prova Linux</h1>'});assert (data/exported['url'].lstrip('/')).read_bytes().startswith(b'%PDF-')
    finally:app.close()
finally:server.shutdown();server.server_close()
sys.path.insert(0,str(ROOT))
from scripts.check_posix import check
check(stage)
print('Linux native CPU/API, Secret Service, documents, RAG, PDF and Agent boundaries passed. No GPU inference or administrator prompt.')

"""Isolated CPU/GPU switch browser fixture; never loads a model."""
import json,sys,tempfile,struct
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from app import Handler,ThreadingHTTPServer
from h3chat.service import Service
with tempfile.TemporaryDirectory(prefix='h3-execution-') as folder:
 app=Service(ROOT,folder,start_worker=False)
 path=Path(folder)/'fake.gguf'
 def string(s):
  b=s.encode();return struct.pack('<Q',len(b))+b
 path.write_bytes(b'GGUF'+struct.pack('<IQQ',3,0,2)+b''.join(string(k)+struct.pack('<I',8)+string(v) for k,v in {'general.architecture':'gemma4','general.name':'Gemma CPU fixture'}.items()))
 model=app.external_model({'profile':'chat','name':'Gemma CPU fixture','files':{'model':str(path)},'projector_mode':'off'})
 app.store.save_settings({'setup_done':True,'chat_model':model['id'],'rag_device':'gpu','memory_policy':'resident'})
 provider=app.provider_request({'name':'External fixture','base_url':'http://127.0.0.1:9/v1','model':'test','vision':False,'max_refs':4,'thinking':'none','format':'json_object','api_key':''})
 app.save_settings({'cpu_chat_model':provider['id']})
 class FixtureHandler(Handler):
  def log_message(self,*args):pass
 server=ThreadingHTTPServer(('127.0.0.1',0),FixtureHandler);server.app=app
 print(json.dumps({'url':f'http://127.0.0.1:{server.server_port}','local':model['id'],'api':provider['id']}),flush=True)
 try:server.serve_forever()
 finally:server.server_close();app.close()

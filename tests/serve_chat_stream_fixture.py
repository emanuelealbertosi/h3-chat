"""Normal-chat streaming UI fixture. No real LLM or GPU calls."""
import json,sys,threading,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'tests')]
from app import Handler,ThreadingHTTPServer
from test_visual_models import VisualModelsTests
fixture=VisualModelsTests();fixture.setUp();app=fixture.app
app.store.save_settings({'setup_done':True});chat=app.store.create_chat()['id']
ticket=app.send(chat,{'prompt':'Scrivi una risposta di prova','assistant':False});job=app.store.one('SELECT * FROM jobs WHERE id=?',(ticket['job_id'],))
meta={'intent':'chat','model':'Stream fixture','canvas':False};app.store.update_answer(job,'Inizio ',meta=meta);app.store.execute("UPDATE jobs SET status='running',stage='Scrittura' WHERE id=?",(job['id'],))
start=threading.Event();final='Inizio '+('Testo reale ricevuto progressivamente. '*12)+'Fine 😀.'
def writer():
 start.wait(15)
 for amount in (100,220,len(final)):
  app.store.update_answer(job,final[:amount],meta=meta);time.sleep(.55)
 app.store.update_answer(job,final,'done',meta=meta);app.store.execute("UPDATE jobs SET status='done' WHERE id=?",(job['id'],))
threading.Thread(target=writer,daemon=True).start()
class FixtureHandler(Handler):
 identity={'role':'owner'}
 def do_GET(self):
  if self.path.endswith('/live'):start.set()
  return super().do_GET()
 def log_message(self,*args):pass
server=ThreadingHTTPServer(('127.0.0.1',0),FixtureHandler);server.app=app
print(json.dumps({'url':f'http://127.0.0.1:{server.server_port}','chat_id':chat,'message_id':job['message_id'],'final':final}),flush=True)
try:server.serve_forever()
finally:server.server_close();fixture.tearDown()

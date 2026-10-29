"""Disposable Studio HTTP fixture, no inference and no production database."""
import json,sys,threading
from pathlib import Path
from contextlib import ExitStack
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'tests'),str(ROOT/'runtime/tools/documents')]
from app import Handler,ThreadingHTTPServer
from test_visual_models import VisualModelsTests
from test_study import completion

def main():
    case=VisualModelsTests();case.setUp();app=case.app;app.store.save_settings({'setup_done':True});project=app.knowledge.save({'name':'Notebook fixture','sources_only':True});chat=app.store.create_chat('Studio fixture',project_id=project['id'])['id']
    class Fixture(Handler):
        def handle_request(self):
            if self.path=='/fixture/execute':
                self.guard();body=self.read_body();job=app.store.one('SELECT * FROM jobs WHERE id=?',(body['job'],));app.execute_job(job,threading.Event());return self.json({'ok':True})
            return super().handle_request()
        do_GET=do_POST=do_PATCH=do_DELETE=do_PUT=handle_request
    with ExitStack() as stack:
        for name,value in [('prepare',lambda *a,**k:None),('start_llama',lambda *a,**k:None),('prepare_tools',lambda h,*a,**k:(h,{},[],[])),('completion',completion)]:stack.enter_context(patch.object(app.engine,name,side_effect=value))
        stack.enter_context(patch('h3chat.web_search.fetch',return_value='<h1>Le piante</h1><p>La fotosintesi utilizza luce, acqua e anidride carbonica. Le piante producono ossigeno e zuccheri.</p>'))
        server=ThreadingHTTPServer(('127.0.0.1',0),Fixture);server.app=app
        print(json.dumps({'url':f'http://127.0.0.1:{server.server_port}','chat':chat,'project':project['id']}),flush=True)
        try:server.serve_forever()
        finally:server.server_close();case.tearDown()
if __name__=='__main__':main()

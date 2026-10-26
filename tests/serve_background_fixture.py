"""Isolated background API/browser fixture. No generation engine is started."""
import json,sys,threading
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'tests')]
from app import Handler,ThreadingHTTPServer
from test_slide_backgrounds import BackgroundTests

fixture=BackgroundTests();fixture.setUp();app=fixture.app
app.store.save_settings({'setup_done':True})
chat,job=fixture.ticket({'name':'Biblioteca botanica','variants':4,'seed_mode':'fixed','seed':42})
with patch.object(app.engine,'generate',side_effect=fixture.generate):app.execute_job(job,threading.Event())
from h3chat.infographics import options as infographic_options
from h3chat.slide_background_style import assign
from h3chat.slide_backgrounds import listing
from h3chat.infographic_document import document
saved=listing(app)['items'][0];media=[item['media'] for item in saved['images']]
# These browser fixtures start from the original form defaults; recovery from
# historical requests is covered separately in the preferences tests.
from h3chat.presentation_preferences import empty
(app.data/'presentation-preferences.json').write_text(json.dumps(empty()),encoding='utf8')
style=dict(base='collection',decorations=True,set_id=saved['id'],asset_ids=[media[0]['id']],opacity=20,veil='auto')
opts=infographic_options(value={'background_style':style,'layout':'columns2','voice':False,'images':'provided','music':'none','duration':5,'scenes':1,'output':'static'})
deck=dict(version=1,engine='llm',format='16:9',pages=[dict(title='Scena',status='ready',html='<style>body{font:30px Arial;background:white}section{padding:30px}</style><section data-panel="1"><h1 data-motion="fade">AND</h1></section><section data-panel="2"><h1 data-motion="fade">OR</h1></section>')],infographic=dict(version=1,options=opts,durations=[5],transition='cut',sfx='none'))
assign(deck,style,media);offline_document=document(ROOT,app.data,deck,media).encode('utf8')
class FixtureHandler(Handler):
    def log_message(self,*args):pass
    def do_GET(self):
        if self.path=='/fixture/background-infographic.html':
            self.send_response(200);self.send_header('Content-Type','text/html; charset=utf-8');self.end_headers();self.wfile.write(offline_document);return
        super().do_GET()
server=ThreadingHTTPServer(('127.0.0.1',0),FixtureHandler);server.app=app
print(json.dumps({'url':f'http://127.0.0.1:{server.server_port}','chat_id':chat,'model':fixture.qwen['id']}),flush=True)
try:server.serve_forever()
finally:server.server_close();fixture.tearDown()

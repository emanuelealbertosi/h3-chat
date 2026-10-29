"""Isolated UI fixture; all model responses are local deterministic functions."""
import json
import sys
import time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'tests')]
from app import Handler,ThreadingHTTPServer
from test_visual_models import VisualModelsTests
from test_agent_runtime import decision

fixture=VisualModelsTests();fixture.setUp();app=fixture.app
app.store.save_settings({'setup_done':True})
app.save_settings({'context':32768,'max_tokens':3000})
chat=app.store.create_chat()['id'];sandbox_path=fixture.base/'sandbox';sandbox_path.mkdir()
app.engine.prepare=lambda *a,**kw:None
app.engine.start_llama=lambda *a,**kw:None
def completion(messages,settings,cancel,**kwargs):
    props=(kwargs.get('schema') or {}).get('properties',{})
    if 'summary' in props:return json.dumps({'summary':'Verifica permessi e risultato reale.','checks':['Usa un tool concreto.']}),'stop'
    if 'action' in props:
        data=json.loads(messages[-1]['content'])
        if 'ferma' in data['request'].lower():
            while not cancel.is_set():cancel.wait(.05)
            from h3chat.downloads import Cancelled
            raise Cancelled()
        if 'pausa' in data['request'].lower():
            return decision('finish',message='Ripresa completata.') if data['observations'] else decision('list_artifacts')
        if 'amministratore' in data['request'].lower():
            return decision('request_admin',{'command':'Write-Output test','reason':'Prova della finestra, nessun comando approvato automaticamente.'})
        if 'connessione' in data['request'].lower():
            return decision('finish',message='Collegamento salvato senza cambiare il modello predefinito.') if data['observations'] else decision('configure_api',{'name':'Server prova Agent','base_url':'http://127.0.0.1:9/v1','model':'example-model'})
        if 'consenso internet' in data['request'].lower():
            return decision('finish',message='Consenso Web verificato.') if data['observations'] else decision('request_web_access',{'reason':'Internet necessario per il compito di prova.'})
        if 'chiarimento' in data['request'].lower():
            return decision('finish',message='Chiarimento ricevuto: '+json.loads(data['observations'][-1]['data'])['answer']) if data['observations'] else decision('ask_user',{'question':'Quante pagine vuoi?','options':['5','10']})
        return decision('finish',message='Presentazione salvata.') if data['artifacts'] else decision('create_slides',{'prompt':'Crea una slide sulle porte logiche','count':1},'Creo una slide sulle porte logiche.')
    if 'slides' in props:return json.dumps({'title':'Porte logiche','visual_direction':'Diagrammi semplici','slides':[{'title':'AND','purpose':'Congiunzione'}]}),'stop'
    if 'content' in props:return json.dumps({'content':'La porta AND produce uno solo se entrambi gli ingressi sono uno.','visual_plan':'Tabella','notes':'Spiegazione completa','sources':[]}),'stop'
    text='<style>body{font:36px Arial;background:#fff;color:#123}h1{margin:30px}</style><h1>La porta AND</h1><p>Entrambi gli ingressi devono essere uno.</p>'
    if kwargs.get('on_text'):kwargs['on_text'](text)
    return text,'stop'
app.engine.completion=completion
app.worker.start()
class FixtureHandler(Handler):
    identity={'role':'owner'}
    def log_message(self,*args):pass
server=ThreadingHTTPServer(('127.0.0.1',0),FixtureHandler);server.app=app
asset_path='outputs/'+('f'*32)+'/asset/sample.bin';asset=app.data/asset_path;asset.parent.mkdir(parents=True);asset.write_bytes(b'Safe fixture download.')
app.store.gallery.register([{'id':'f'*32,'name':'sample.bin','path':asset_path,'mime':'application/octet-stream'}]);asset.with_name('unpublished.bin').write_bytes(b'Not published')
print(json.dumps({'url':f'http://127.0.0.1:{server.server_port}','chat_id':chat,'sandbox_path':str(sandbox_path),'asset_path':asset_path}),flush=True)
try:server.serve_forever()
finally:server.server_close();fixture.tearDown()

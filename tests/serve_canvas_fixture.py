"""Disposable browser fixture: synthetic artifacts only, no model inference."""
import base64
import json
from pathlib import Path
import sys
import struct
import tempfile
import threading

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app import Handler, ThreadingHTTPServer
from h3chat.service import Service
from h3chat.store import DEFAULTS


def main():
    with tempfile.TemporaryDirectory(prefix='h3-canvas-') as folder:
        app = Service(ROOT, Path(folder), start_worker=False)
        chat = app.store.create_chat('Collaudo cronologia')['id']
        other = app.store.create_chat('Altra conversazione')['id']
        app.store.save_settings({'setup_done':True})
        def fixture_model(filename, alias, internal):
            path=Path(folder)/'models'/filename;path.parent.mkdir(exist_ok=True)
            def string(value):
                raw=value.encode();return struct.pack('<Q',len(raw))+raw
            values={'general.architecture':'qwen35','general.name':internal}
            data=b'GGUF'+struct.pack('<IQQ',3,0,len(values))
            for k,v in values.items():data+=string(k)+struct.pack('<I',8)+string(v)
            path.write_bytes(data)
            return app.external_model({'profile':'chat','name':alias,'files':{'model':str(path)},'projector_mode':'off'})
        model=fixture_model('Qwen-OrcaRouter-IQ3_XXS.gguf','Staged_Tmpl','Staged_Tmpl')
        second=fixture_model('RVN-IQ3_M-mtp.gguf','Qwen fixture','Internal Ara')
        app.store.save_settings({'chat_model':model['id']})
        outputs = Path(folder) / 'outputs'; outputs.mkdir(exist_ok=True)
        (outputs / 'fixture.png').write_bytes(base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Wl6P4AAAAAASUVORK5CYII='))
        original = {'title':'Documento iniziale', 'content':'# Documento iniziale\n\nVersione originale.\n\n$x^2$\n\n```python\nprint(42)\n```', 'media':[]}
        image = {'title':'Immagine precedente', 'content':'', 'media':[{'id':'a'*32, 'name':'fixture.png', 'path':'outputs/fixture.png', 'mime':'image/png'}]}
        latest = {'title':'Documento recente', 'content':'# Documento recente\n\nContenuto più recente.', 'media':[]}
        # Deliberately bypass history to exercise recovery from older chats.
        for i, value in enumerate((original, image, latest)):
            app.store.execute("INSERT INTO messages(id,chat_id,role,content,created,meta) VALUES (?,?,'assistant','Artefatto creato.',?,?)",
                (str(i), chat, i + 1, json.dumps({'canvas':True, 'artifact':value})))
        app.store.execute('INSERT INTO canvases VALUES (?,?,?,?,?)', (chat, latest['title'], latest['content'], '[]', 3))
        active = None

        class FixtureHandler(Handler):
            def handle_request(self):
                nonlocal active
                if self.path.startswith('/fixture/'):
                    self.guard(); self.read_body()
                    if self.path.startswith('/fixture/slides/'):
                        from h3chat.slides import encode
                        phase=self.path.rsplit('/',1)[-1]
                        if phase=='start':
                            ident=app.store.enqueue(chat,'Crea 3 slide sintetiche',[],DEFAULTS|{'_lab':'slides'},True)
                            active=app.store.one('SELECT * FROM jobs WHERE id=?',(ident,))
                            app.store.execute("UPDATE jobs SET status='running',stage='Slide · composizione progressiva' WHERE id=?",(ident,))
                        def n(ident,kind,text='',**kw):return {'id':ident,'parent':'root','kind':kind,'text':text,'asset_id':'','language':'text','style':{}}|kw
                        pages=[{'title':'Fonti e formule','status':'ready','nodes':[n('title','heading','Fonti e formule'),n('text','text','Una formula precisa: $A=\\pi r^2$. Dati dalla fonte [R1].')],'notes':'Nota dalla fonte sintetica.','sources':['R1']},
                               {'title':'Diagramma','status':'ready','nodes':[n('title','heading','Diagramma'),n('graph','mermaid','flowchart LR\n A[Documento] --> B[Slide]')],'notes':'Relazioni verificabili.','sources':[]},
                               {'title':'Figura','status':'writing','nodes':[n('title','heading','Figura'),n('text','text','Prima parte' if phase=='start' else 'Prima parte e testo completato'),n('image','image','Immagine originale',asset_id='a'*32)],'notes':'Figura autorizzata.','sources':[]}]
                        if phase=='done':pages[-1]['status']='ready'
                        deck={'version':1,'format':'4:3','title':'Presentazione sintetica','references':[{'id':'R1','label':'Fonte sintetica · pagina 2'}],'pages':pages,'active':2}
                        value={'title':deck['title'],'content':encode(deck),'media':image['media']}
                        app.save_artifact(chat,value['title'],value['content'],value['media'])
                        app.store.update_answer(active,'Slide nel canvas.','done' if phase=='done' else 'running',[],{'canvas':True,'intent':'slides','artifact':value,'rag_sources':[{'citation':'R1','name':'Fonte sintetica','location':'pagina 2','text':'Una formula precisa','source_id':'synthetic','chunk_id':1,'page':2,'url':''}]})
                        if phase=='done':app.store.execute("UPDATE jobs SET status='done' WHERE id=?",(active['id'],))
                    elif self.path == '/fixture/start':
                        ident = app.store.enqueue(chat, 'Synthetic generation', [], DEFAULTS, True)
                        active = app.store.one('SELECT * FROM jobs WHERE id=?', (ident,))
                        app.store.execute("UPDATE jobs SET status='running' WHERE id=?", (ident,))
                        app.save_artifact(chat, 'Nuovo documento', '# Nuovo documento\n\nPrima parte', [])
                    elif self.path == '/fixture/finish':
                        value = {'title':'Nuovo documento', 'content':'# Nuovo documento\n\nGenerazione completata', 'media':[]}
                        app.save_artifact(chat, value['title'], value['content'], [])
                        app.store.update_answer(active, 'Ho scritto nel canvas.', 'done', [], {'canvas':True, 'artifact':value})
                        app.store.execute("UPDATE jobs SET status='done' WHERE id=?", (active['id'],))
                    return self.json({'ok':True})
                return super().handle_request()
            do_GET = do_POST = do_PUT = do_PATCH = do_DELETE = handle_request

        server = ThreadingHTTPServer(('127.0.0.1', 0), FixtureHandler); server.app = app
        print(json.dumps({'url':f'http://127.0.0.1:{server.server_port}', 'chat':chat, 'other':other, 'model':model['id'], 'second_model':second['id']}), flush=True)
        try:
            server.serve_forever()
        finally:
            server.server_close(); app.close()


if __name__ == '__main__':
    main()

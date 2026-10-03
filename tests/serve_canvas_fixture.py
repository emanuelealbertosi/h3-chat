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
        sys.path.insert(0,str(ROOT/'runtime/tools/documents'))
        from PIL import Image,ImageDraw
        picture=Image.new('RGB',(320,180),'#087f8c');drawing=ImageDraw.Draw(picture);drawing.rectangle((20,20,140,140),fill='#d7ef92');drawing.ellipse((175,40,290,155),fill='#f5b5a9');picture.save(outputs/'fixture.png')
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
                        from h3chat.slides import encode,partial_page
                        phase=self.path.rsplit('/',1)[-1]
                        if phase in ('start','design'):
                            ident=app.store.enqueue(chat,'Crea 3 slide sintetiche',[],DEFAULTS|{'_lab':'slides'},True)
                            active=app.store.one('SELECT * FROM jobs WHERE id=?',(ident,))
                            app.store.execute("UPDATE jobs SET status='running',stage='Slide · composizione progressiva' WHERE id=?",(ident,))
                        def n(ident,kind,text='',**kw):return {'id':ident,'parent':'root','kind':kind,'text':text,'asset_id':'','language':'text','style':{}}|kw
                        pages=[{'title':'Fonti e formule','status':'ready','nodes':[n('title','heading','Fonti e formule'),n('text','text','Una formula precisa: $A=\\pi r^2$. Dati dalla fonte [R1].')],'notes':'Nota dalla fonte sintetica.','sources':['R1']},
                               {'title':'Diagramma','status':'ready','nodes':[n('title','heading','Diagramma'),n('graph','mermaid','flowchart LR\n A[Documento] --> B[Slide]')],'notes':'Relazioni verificabili.','sources':[]},
                               {'title':'Figura','status':'writing','nodes':[n('title','heading','Figura'),n('text','text','Prima parte' if phase=='start' else 'Prima parte e testo completato'),n('image','image','Immagine originale',asset_id='a'*32)],'notes':'Figura autorizzata.','sources':[]}]
                        if phase=='done':pages[-1]['status']='ready'
                        if phase=='early':
                            pages[-1]['nodes']=partial_page('{"nodes":[{"text":"Contenuto già visibile prima di completare la pagina',set(),set())['nodes']
                        elif phase=='orphan':
                            raw='{"nodes":['+json.dumps(n('1. Titolo','heading','Gruppo ancora in composizione',parent='layout futuro'))+',{"text":"Testo che cresce mentre arriva il gruppo'
                            pages[-1]['nodes']=partial_page(raw,set(),set())['nodes']
                        deck={'version':1,'format':'4:3','title':'Presentazione sintetica','references':[{'id':'R1','label':'Fonte sintetica · pagina 2'}],'pages':pages,'active':2}
                        if phase=='design':
                            long=' '.join(f'Concetto{i}: il documento spiega un risultato verificabile con esempi e dettagli precisi.' for i in range(60))
                            pages=[{'title':'Progetti che prendono forma','status':'ready','nodes':[n('title','heading','Progetti che prendono forma'),n('intro','text','Documenti, esempi e dati diventano una presentazione leggibile. **Il contenuto resta modificabile.**')],'notes':'Collaudo di design e modifica.','sources':[]},
                                   {'title':'Confrontare le alternative','status':'ready','nodes':[n('title','heading','Confrontare le alternative'),n('one','text','### Metodo A\nDati verificabili e passaggi espliciti.'),n('two','text','### Metodo B\nUna vista compatta per decidere.'),n('three','text','### Risultato\nUna scelta motivata dalle fonti.')],'notes':'Layout a più colonne.','sources':[]},
                                   {'title':'Contenuti senza tagli','status':'ready','nodes':[n('title','heading','Contenuti senza tagli'),n('long','text',long),n('code','code','\n'.join(f'print("Riga {i}")' for i in range(40)),language='python'),n('list','text','\n'.join(f'- Punto verificabile {i}' for i in range(20)))],'notes':'Tutti i marcatori devono essere conservati.','sources':[]},
                                   {'title':'Dati e coordinate precise','status':'ready','nodes':[n('title','heading','Dati e coordinate precise'),n('bars','chart',json.dumps({'type':'bar','title':'Valori verificati','labels':['A','B','C'],'datasets':[{'label':'Serie','data':[10,30,20]}]})),n('scatter','chart',json.dumps({'type':'scatter','title':'Coordinate originali','labels':[],'datasets':[{'label':'Prima','data':[{'x':-2,'y':4},{'x':0,'y':0},{'x':2,'y':4}]},{'label':'Seconda','data':[{'x':-1,'y':1},{'x':1,'y':1}]}]}))],'notes':'Valori e coordinate restano modificabili in PowerPoint.','sources':[]}]
                            deck={'version':1,'format':'16:9','theme':'indigo','typography':'modern','title':'Presentazione di collaudo','references':[],'pages':pages,'active':0}
                        finished=phase in ('done','design')
                        value={'title':deck['title'],'content':encode(deck),'media':image['media']}
                        app.save_artifact(chat,value['title'],value['content'],value['media'])
                        app.store.update_answer(active,'Slide nel canvas.','done' if finished else 'running',[],{'canvas':True,'intent':'slides','artifact':value,'rag_sources':[{'citation':'R1','name':'Fonte sintetica','location':'pagina 2','text':'Una formula precisa','source_id':'synthetic','chunk_id':1,'page':2,'url':''}]})
                        if finished:app.store.execute("UPDATE jobs SET status='done' WHERE id=?",(active['id'],))
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

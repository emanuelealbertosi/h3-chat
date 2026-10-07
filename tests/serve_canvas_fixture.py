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
                    self.guard(); fixture_body=self.read_body()
                    if self.path=='/fixture/manim-duration':
                        import av
                        ident=app.store.enqueue(chat,'Manim 20 secondi',[],DEFAULTS|{'_lab':'manim'},True)
                        job=app.store.one('SELECT * FROM jobs WHERE id=?',(ident,));folder=outputs/ident;folder.mkdir()
                        with av.open(str(folder/'animation.mp4'),'w') as movie:
                            video=movie.add_stream('libx264',rate=5);video.width=320;video.height=240;video.pix_fmt='yuv420p'
                            for i in range(140):
                                frame=av.VideoFrame.from_image(Image.new('RGB',(320,240),(20+i,90,130)))
                                for packet in video.encode(frame):movie.mux(packet)
                            for packet in video.encode(None):movie.mux(packet)
                        value={'title':'Manim da recuperare','content':'Scena sintetica.','media':[]}
                        app.store.update_answer(job,'Solo codice.', 'failed',[],{'intent':'manim','canvas':True,'artifact':value,'error':'Durata errata: il video dura 28.00 s; richiesti 20 s. Correggi i tempi.'})
                        app.store.execute("UPDATE jobs SET status='failed' WHERE id=?",(ident,))
                        return self.json({'message_id':job['message_id']})
                    if self.path=='/fixture/audio':
                        import io,math,wave
                        stream=io.BytesIO()
                        with wave.open(stream,'wb') as audio:
                            audio.setnchannels(1);audio.setsampwidth(2);audio.setframerate(44100)
                            audio.writeframes(b''.join(struct.pack('<h',round(7000*math.sin(2*math.pi*440*i/44100))) for i in range(44100)))
                        track=app.upload({'name':'Brano sintetico.wav','data':base64.b64encode(stream.getvalue()).decode()})
                        app.store.execute("INSERT INTO messages(id,chat_id,role,content,created,media) VALUES (? ,?,'assistant','Audio sintetico.',999,?)",('audio-fixture',chat,json.dumps([track])))
                        app.save_artifact(chat,'Brano sintetico','Audio nel canvas.',[track])
                        return self.json({'ok':True})
                    if self.path.startswith('/fixture/slides/'):
                        from h3chat.slides import encode,partial_page
                        phase=self.path.rsplit('/',1)[-1]
                        if phase in ('start','design','contrast'):
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
                        if phase=='contrast':
                            surface=lambda name:{'flow':'stack','columns':[1,1],'surface':name,'gap':12}
                            cover=[n('title','heading','Testi sempre leggibili'),n('cover-panel','group',style=surface('accent')),
                                   n('cover-text','text','Paragrafi, **evidenziazioni**, codice `inline` e formule $A=\\pi r^2$.',parent='cover-panel'),
                                   n('cover-table','text','| Voce | Valore |\n|---|---|\n| Fonte verificata | 42 |',parent='cover-panel')]
                            cases=[n('title','heading','Riquadri e codice')]
                            for name in ('plain','soft','accent','dark'):
                                cases.extend([n('panel-'+name,'group',style=surface(name)),
                                              n('text-'+name,'text','Testo '+name+' · **grassetto** e `codice inline`.\n\n- Voce leggibile',parent='panel-'+name),
                                              n('code-'+name,'code','# Commento leggibile\nprint("Un esempio")',parent='panel-'+name,language='python')])
                            charts=[n('title','heading','Grafici su sfondo scuro'),n('dark-panel','group',style=surface('dark')),
                                    n('chart','chart',json.dumps({'type':'bar','title':'Dati leggibili','labels':['A','B'],'datasets':[{'label':'Verificato','data':[10,20]}]}),parent='dark-panel'),
                                    n('diagram','mermaid','flowchart LR\n A[Documento] --> B[Slide]',parent='dark-panel')]
                            pages=[{'title':title,'status':'ready','nodes':nodes,'notes':'Collaudo sintetico del contrasto.','sources':[]} for title,nodes in (('Copertina',cover),('Superfici',cases),('Grafici',charts))]
                            pages[1]['overrides']={'text-plain':{'color':'#ffffff','background':'#ffffff'},'text-soft':{'color':'#000000','background':'#000000'}}
                            deck={'version':1,'format':'16:9','theme':fixture_body.get('theme','lagoon'),'design':fixture_body.get('design','professional'),'title':'Collaudo contrasto','references':[],'pages':pages,'active':0}
                        if phase in ('html','html-stream','html-bounds'):
                            if not active:
                                ident=app.store.enqueue(chat,'Slide HTML sintetiche',[],DEFAULTS,True);active=app.store.one('SELECT * FROM jobs WHERE id=?',(ident,));app.store.execute("UPDATE jobs SET status='running' WHERE id=?",(ident,))
                            raw='<style>body{background:#102e45;color:#faf3d7;font:30px Georgia;padding:60px}h1{font-size:70px;color:#ffd166;margin:0 0 30px}main{display:grid;grid-template-columns:2fr 1fr;gap:40px}img{width:350px;height:240px;object-fit:contain}svg{width:220px;height:180px}</style><h1>Pagina creata dal modello</h1><main><p>Spiegazione completa, grafica originale e font scelti liberamente [R1].</p><img data-asset-id="'+('a'*32)+'"></main><svg viewBox="0 0 200 150"><circle cx="80" cy="70" r="60" fill="#ef476f"/></svg><script>parent.__h3Injected=true</script><img src="https://example.com/tracker.png" onerror="parent.__h3Injected=true"><style>@import url(https://example.com/leak.css);</style>'
                            if phase=='html-stream':raw=raw[:raw.index('</main>')]
                            if phase=='html':raw=raw.replace('scelti liberamente [R1]','scelti liberamente $A=\\pi r^2$ [R1]')+'<div style="position:absolute;top:20px;right:20px;width:240px;height:24px;background:linear-gradient(90deg,#ef476f,#ffd166)"></div>'
                            deck={'version':1,'engine':'llm','format':'16:9','title':'HTML originale','references':[{'id':'R1','label':'Documento sintetico · pagina 2'}],'pages':[{'title':'Pagina libera','html':raw,'nodes':[],'status':'ready' if phase=='html' else 'writing','notes':'','sources':['R1']}],'active':0}
                            if not app.store.chat(chat).get('project_id'):
                                p=app.knowledge.save({'name':'Figure sintetiche'})
                                app.store.execute('UPDATE chats SET project_id=? WHERE id=?',(p['id'],chat))
                                app.store.execute('INSERT INTO project_sources(id,project_id,path,name) VALUES (?,?,?,?)',('fig-source',p['id'],str(outputs/'fixture.png'),'Libro illustrato.pdf'))
                                app.store.execute('INSERT INTO rag_chunks(source_id,location,page,text,image_path,modality) VALUES (?,?,?,?,?,?)',('fig-source','pagina 12',12,'Figura della batteria','outputs/fixture.png','image'))
                        if phase=='html-bounds':
                            svg='<style>body{margin:0;background:#163e48;color:white;font:24px Arial}.main{position:absolute;inset:110px 50px 60px;display:grid;grid-template-columns:340px 1fr;gap:30px}.text{display:flex;flex-direction:column}.diagram{display:flex;align-items:center;justify-content:center;padding:20px}svg{width:100%;height:100%}</style><div class="main"><div class="text"><h1>Testo originale</h1><p>Stessa composizione e caratteri.</p></div><div class="diagram"><svg viewBox="0 0 300 450"><circle cx="150" cy="225" r="130" fill="#fa8c45"/><text x="-30" y="225" fill="white">Etichetta intera</text><text x="90" y="445" fill="white">Nodo inferiore</text></svg></div></div>'
                            oversized='<style>body{margin:0;background:#faf3d7;color:#163e48}.picture{position:absolute;left:80px;top:100px;width:400px;height:300px}img{width:950px;height:850px;object-fit:fill}</style><h1>Immagine senza deformazioni</h1><div class="picture"><img data-asset-id="'+('a'*32)+'"></div>'
                            normal='<style>body{margin:0;background:#eef4ed;color:#163e48}.ok{position:absolute;left:100px;top:100px;width:900px;height:500px;display:flex;align-items:center;justify-content:center}p{font:28px Georgia}</style><section class="ok"><p>HTML libero già corretto</p></section>'
                            deck={'version':1,'engine':'llm','format':'16:9','title':'Limiti delle figure','references':[], 'pages':[{'title':title,'status':'ready','html':html,'sources':[]} for title,html in [('SVG e griglia',svg),('Immagine grande',oversized),('Layout corretto',normal)]],'active':0}
                        finished=phase in ('done','design','contrast','html','html-bounds')
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

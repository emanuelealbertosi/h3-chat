"""Disposable full-stack fixture. Synthetic LLM output, no inference or real DB."""
import json,re,sys,threading,time
from pathlib import Path
from contextlib import ExitStack
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'tests'),str(ROOT/'runtime/tools/documents')]
from app import Handler,ThreadingHTTPServer
from test_visual_models import VisualModelsTests
from test_posters import plan


def main():
    case=VisualModelsTests();case.setUp();app=case.app
    app.store.save_settings({'setup_done':True});chat=app.store.create_chat('Poster fixture')['id'];calls=[]
    def complete(messages,settings,cancel,**kw):
        calls.append({'schema':bool(kw.get('schema'))})
        if kw.get('schema'):
            if 'zones' in kw['schema']['properties']:
                import html
                data=json.loads(messages[-1]['content']);zones=[]
                for z in data['zones']:
                    copy=html.escape(z['text'])
                    markup='<p style="margin:0;font-family:Manrope;font-size:32px;color:inherit">'+copy+'</p>'
                    if z['role']=='title':markup='<svg viewBox="0 0 900 160" style="width:100%;height:160px"><defs><linearGradient id="ink"><stop offset="0" stop-color="#ffe49a"/><stop offset="1" stop-color="#f37855"/></linearGradient></defs><text x="10" y="122" style="font-family:BebasNeue;font-size:130px;fill:url(#ink);stroke:#112d38;stroke-width:2px;paint-order:stroke">'+copy+'</text></svg>'
                    zones.append({'id':z['id'],'html':markup})
                return json.dumps({'zones':zones}),'stop'
            count=kw['schema']['properties']['variants']['minItems'];return json.dumps(plan(count)),'stop'
        if any('TYPE SPECIMEN' in str(m.get('content','')) for m in messages):
            from test_poster_visual import layout
            from h3chat.poster_visual import validate,compose
            from h3chat.slides import FORMATS
            opts=settings['_posters'];value=layout();value['zones'][0].update(renderer='html',text='Un mondo di idee',font_size=120,bbox=[60,100,940,480])
            value['zones'][1].update(role='body',text='INCONTRO 1 — IDEE\nTipografia coordinata alla grafica.\nOgni dettaglio resta leggibile.',font_size=34,bbox=[60,600,940,900])
            value['objects'][0]['bbox']=[650,490,950,590]
            width,height=FORMATS[opts['format']];styled=validate(value,width,height,5,ROOT,opts)
            return compose(styled,'f'*32,width,height),'stop'
        text=messages[-1]['content'];second='variante 2' in text.lower();background='#fff1d7' if second else '#102d38';ink='#102d38' if second else '#fff1d7'
        html=f'''<main><p class="kicker">LABORATORIO APERTO</p><h1>OPEN<br>LAB</h1><div class="graphic"><svg viewBox="0 0 600 600"><path d="M40 300 300 40 560 300 300 560Z" fill="#f37855"/><circle cx="300" cy="300" r="135" fill="{background}"/><text x="300" y="340" text-anchor="middle" fill="{ink}" font-size="100">AI</text></svg></div><section class="info"><p>12 novembre · ore 17</p><p>Aula Blu</p></section></main><style>*{{box-sizing:border-box}}body{{margin:0;background:{background};color:{ink};font-family:Arial}}main{{position:relative;padding:90px;width:1280px;min-height:100vh;overflow:hidden}}.kicker{{font-size:30px;letter-spacing:8px;margin:0 0 45px}}h1{{font-size:205px;line-height:.85;letter-spacing:-10px;margin:0;position:relative;z-index:1}}.graphic{{width:770px;margin:40px 0 30px 200px;transform:rotate(12deg)}}svg{{display:block;width:100%;height:auto}}.info p{{font-size:44px;margin:12px 0}}.info{{border-top:3px solid;padding-top:30px}}</style>'''
        if kw.get('on_text'):
            kw['on_text'](html[:700]);time.sleep(.4);kw['on_text'](html)
        return html,'stop'
    class Fixture(Handler):
        def handle_request(self):
            if self.path.startswith('/fixture/'):
                self.guard();body=self.read_body()
                if self.path=='/fixture/execute':
                    job=app.store.one('SELECT * FROM jobs WHERE id=?',(body['job'],));app.execute_job(job,threading.Event())
                    return self.json({'ok':True,'calls':calls})
                if self.path=='/fixture/seed-expressive':
                    import base64,io
                    from PIL import Image
                    from test_poster_overlay import prepared,fragments
                    from h3chat.posters import options
                    from h3chat.poster_overlay import compose
                    from h3chat.slides import FORMATS,encode
                    pixels=io.BytesIO();Image.new('RGB',(32,32),'#112d38').save(pixels,format='PNG')
                    image=app.upload({'name':'Sfondo prova.png','data':base64.b64encode(pixels.getvalue()).decode()});layout=prepared();parts=fragments(layout);w,h=FORMATS['A3']
                    page={'title':'Prova espressiva','status':'ready','html':compose(layout,image['id'],w,h,parts),'nodes':[],'notes':'','sources':[],'poster_layout':layout,'poster_background':image['id'],'poster_fragments':parts}
                    deck={'version':1,'engine':'llm','document_kind':'poster','poster':options(value={'composition':'moss_layout'}),'format':'A3','title':'Prova espressiva','theme':'lagoon','typography':'modern','design':'professional','detail':'concise','motion':'static','references':[],'active':0,'pages':[page]}
                    value=app.store.canvas_history.save(chat,{'title':deck['title'],'content':encode(deck),'media':[image]})
                    return self.json({'id':value['id'],'background':image['id']})
                if self.path=='/fixture/proof':
                    from pypdf import PdfReader
                    results=[]
                    for file in app.data.glob('exports/*/document.pdf'):
                        pdf=PdfReader(file);results.append({'pages':len(pdf.pages),'sizes_mm':[[float(p.mediabox.width)*25.4/72,float(p.mediabox.height)*25.4/72] for p in pdf.pages],'text':' '.join(p.extract_text() or '' for p in pdf.pages)})
                    return self.json({'pdf':results,'calls':calls})
                return self.json({'error':'fixture unknown'},404)
            return super().handle_request()
        do_GET=do_POST=do_PATCH=do_DELETE=do_PUT=handle_request
    with ExitStack() as stack:
        for name,value in [('prepare',lambda *a,**k:None),('start_llama',lambda *a,**k:None),('prepare_tools',lambda h,*a,**k:(h,{},[],[])),('completion',complete)]:stack.enter_context(patch.object(app.engine,name,side_effect=value))
        server=ThreadingHTTPServer(('127.0.0.1',0),Fixture);server.app=app
        print(json.dumps({'url':f'http://127.0.0.1:{server.server_port}','chat':chat}),flush=True)
        try:server.serve_forever()
        finally:server.server_close();case.tearDown()


if __name__=='__main__':main()

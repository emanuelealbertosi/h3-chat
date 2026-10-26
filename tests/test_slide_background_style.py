import copy,json,threading,unittest
from unittest.mock import patch
import test_slide_backgrounds as fixture
from h3chat.slide_backgrounds import listing
from h3chat.slide_background_style import options,assign,geometry,brief,resolve
from h3chat.slides import PREFIX,encode,validate_content
from h3chat.slide_revision import enqueue as revise


class BackgroundStyleTests(unittest.TestCase):
    setUp=fixture.BackgroundTests.setUp
    tearDown=fixture.BackgroundTests.tearDown
    generate=fixture.BackgroundTests.generate
    ticket=fixture.BackgroundTests.ticket

    def library(self):
        chat,job=self.ticket({'variants':3})
        with patch.object(self.app.engine,'generate',side_effect=self.generate):self.app.execute_job(job,threading.Event())
        collection=listing(self.app)['items'][0]
        return chat,collection,dict(base='collection',decorations=False,set_id=collection['id'],asset_ids=[item['media']['id'] for item in collection['images']][::-1],opacity=20,veil='auto')

    def test_validation_and_exact_rotation_no_default_change(self):
        from h3chat.slides import options as slide_options
        self.assertNotIn('background_style',slide_options(''))
        for invalid in ({'base':'other'},{'decorations':1},{'base':'collection'},{'opacity':100},{'veil':'url(x)'},{'extra':'x'}):
            with self.assertRaises(ValueError):options(invalid)
        chat,collection,style=self.library();media=resolve(self.app,style)
        deck={'version':1,'engine':'llm','format':'16:9','pages':[{'title':str(n),'status':'ready','html':'<main><h1>Una pagina</h1></main>'} for n in range(5)]}
        assign(deck,style,media)
        self.assertEqual([p['background_asset_id'] for p in deck['pages']],style['asset_ids']+style['asset_ids'][:2])
        validate_content(encode(deck),media)
        box=geometry(deck,deck['pages'][0],media);self.assertAlmostEqual(box['width'],1280*.76);self.assertAlmostEqual(box['height'],720*.76)
        self.assertIn('Area di composizione effettiva',brief(deck,deck['pages'][0],media))
        bad=copy.deepcopy(deck);bad['pages'][0]['background_asset_id']='f'*32
        with self.assertRaises(ValueError):validate_content(encode(bad),media)

    def test_automatic_base_keeps_decorations_independent(self):
        self.assertIsNone(options({'base':'auto','decorations':False}))
        style=options({'base':'auto','decorations':True})
        deck={'version':1,'engine':'llm','format':'16:9','pages':[{'title':'Titolo','status':'ready','html':'<h1>Titolo</h1>'}]}
        assign(deck,style,[]);validate_content(encode(deck),[])
        self.assertEqual(deck['background_style']['base'],'auto');self.assertTrue(deck['background_style']['decorations'])
        self.assertIn('Scegli liberamente il fondo',brief(deck,deck['pages'][0],[]))
        self.assertEqual(geometry(deck,deck['pages'][0],[]),{'x':56,'y':56,'width':1168,'height':608})
        deck['pages'][0]['content_viewport']={'width':1168,'height':608};validate_content(encode(deck),[])
        for invalid in ({'width':2000,'height':608},{'width':True,'height':608},{'width':1168,'height':0}):
            deck['pages'][0]['content_viewport']=invalid
            with self.assertRaises(ValueError):validate_content(encode(deck),[])

    def test_full_send_and_single_page_revision_keep_assigned_background(self):
        chat,collection,style=self.library();before=self.app.store.settings()
        request=self.app.send(chat,{'prompt':'Crea 5 slide sulle porte logiche','lab':'slides','rag':False,'slides':{'count':5,'engine':'llm','background_style':style}})
        job=self.app.store.one('SELECT * FROM jobs WHERE id=?',(request['job_id'],));observed=[]
        def completion(messages,settings,cancel,**kw):
            schema=kw.get('schema',{}).get('properties',{})
            if 'slides' in schema:return json.dumps({'title':'Porte logiche','visual_direction':'Diagrammi chiari','slides':[{'title':str(n),'purpose':'Spiega'} for n in range(5)]}),'stop'
            if 'content' in schema:return json.dumps({'content':'Spiegazione della porta AND e un esempio.','visual_plan':'Due segnali e un risultato.','notes':'Spiega il risultato.','sources':[]}),'stop'
            observed.append(messages[-1]['content']);return '<main><h1>Porta AND</h1><p>Due ingressi, una uscita.</p></main>','stop'
        with patch.object(self.app.engine,'prepare'),patch.object(self.app.engine,'start_llama'),patch.object(self.app.engine,'completion',side_effect=completion),patch.object(self.app.engine,'generate') as generate:
            self.app.execute_job(job,threading.Event())
        answer=self.app.store.messages(chat)[-1];self.assertEqual(answer['status'],'done',answer['meta'])
        artifact=answer['meta']['artifact'];deck=json.loads(artifact['content'][len(PREFIX):-4]);ids=[p['background_asset_id'] for p in deck['pages']]
        self.assertEqual(ids,style['asset_ids']+style['asset_ids'][:2]);generate.assert_not_called();self.assertEqual(len(observed),5)
        self.assertTrue(all('SFONDO GESTITO DALL’APP' in text for text in observed));self.assertEqual(self.app.store.settings(),before)
        for page,text in zip(deck['pages'],observed):
            box=geometry(deck,page,artifact['media']);self.assertEqual(page['content_viewport'],{'width':box['width'],'height':box['height']})
            self.assertIn(f'Viewport {box["width"]:g}x{box["height"]:g} px.',text)
        saved=self.app.store.canvas_history.get(chat)
        response=revise(self.app,chat,{'artifact_id':saved['id'],'page':2,'prompt':'Amplia la spiegazione'})
        job=self.app.store.one('SELECT * FROM jobs WHERE id=?',(response['job_id'],))
        with patch.object(self.app.engine,'prepare'),patch.object(self.app.engine,'start_llama'),patch.object(self.app.engine,'completion',return_value=('<main style="font:30px sans-serif;color:blue"><h1>Porta AND aggiornata</h1><p>Nuova spiegazione completa.</p></main>','stop')):
            self.app.execute_job(job,threading.Event())
        answer=self.app.store.messages(chat)[-1];self.assertEqual(answer['status'],'done',answer['meta'])
        revised=json.loads(answer['meta']['artifact']['content'][len(PREFIX):-4]);self.assertEqual([p['background_asset_id'] for p in revised['pages']],ids)
        from h3chat.slide_resume import enqueue as resume
        revised['pages'][4].update(status='pending',html='')
        snapshot=self.app.store.canvas_history.save(chat,{'title':revised['title'],'content':encode(revised),'media':artifact['media']})
        response=resume(self.app,chat,{'artifact_id':snapshot['id']});job=self.app.store.one('SELECT * FROM jobs WHERE id=?',(response['job_id'],))
        with patch.object(self.app.engine,'prepare'),patch.object(self.app.engine,'start_llama'),patch.object(self.app.engine,'completion',return_value=('<main style="color:blue"><h1>Pagina completata</h1><p>Spiegazione finale.</p></main>','stop')):
            self.app.execute_job(job,threading.Event())
        answer=self.app.store.messages(chat)[-1];self.assertEqual(answer['status'],'done',answer['meta'].get('error'))
        completed=json.loads(answer['meta']['artifact']['content'][len(PREFIX):-4]);self.assertEqual([p['background_asset_id'] for p in completed['pages']],ids)
        self.assertEqual(completed['pages'][2]['html'],revised['pages'][2]['html'])

    def test_missing_or_foreign_assets_rejected_without_substitution(self):
        chat,collection,style=self.library();bad=style|{'asset_ids':['e'*32]}
        with self.assertRaises(ValueError):resolve(self.app,bad)
        image=collection['images'][0]['media'];(self.app.data/image['path']).unlink()
        with self.assertRaises(ValueError):resolve(self.app,style)

    def test_infographic_static_settings_and_offline_document(self):
        from h3chat.infographics import options as infographic_options
        from h3chat.infographic_document import document
        chat,collection,style=self.library();media=resolve(self.app,style)
        opts=infographic_options(value={'background_style':style,'video_background':'auto','video_id':'old-video','voice':False,'images':'provided','music':'none'})
        self.assertEqual(opts['video_background'],'off');self.assertEqual(opts['video_id'],'')
        deck={'version':1,'engine':'llm','format':'16:9','pages':[{'title':'Scena','status':'ready','html':'<main><h1 data-motion="fade">Porte logiche</h1></main>'}],
              'infographic':{'version':1,'options':opts,'durations':[5],'transition':'cut','sfx':'none'}}
        assign(deck,style,media);doc=document(self.app.root,self.app.data,deck,media)
        self.assertIn('data-h3-background-spec',doc);self.assertIn('data:image/png;base64,',doc)
        self.assertNotIn('http://',doc)


if __name__=='__main__':unittest.main()

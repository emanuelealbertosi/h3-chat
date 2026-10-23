import copy
import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch
from h3chat.service import Service
from h3chat.slides import PREFIX,encode,options
from h3chat.slide_revision import enqueue
from h3chat.downloads import Cancelled
from h3chat.voice import DEFAULTS as VOICE,controls,validate_fields

ROOT=Path(__file__).resolve().parents[1]


class SlideAITests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.app=Service(ROOT,self.temp.name,start_worker=False);self.addCleanup(self.app.close)
        self.model={'id':'fixture-chat','name':'Chat fixture','capabilities':['chat'],'files':[],'vision':{'enabled':False}}
        self.image={'id':'fixture-image','name':'Anima fixture','capabilities':['create'],'files':[],'architecture':'anima'}
        self.events=[]

    def model_for(self,ident,capability):return self.image if capability=='create' else self.model

    def deck(self,chat):
        deck={'version':1,'engine':'llm','format':'4:3','title':'Corso','design':'playful','detail':'full','visual_direction':'Palette calda',
              'references':[{'id':'R1','label':'Libro · pagina 2'}],'pages':[
              {'title':'Prima','status':'ready','html':'<main><h1>Prima</h1><p>Testo originale [R1]</p></main>','sources':['R1']},
              {'title':'Seconda','status':'ready','html':'<main><h1>Seconda</h1><svg><circle r="5"/></svg></main>','sources':[]}]}
        saved=self.app.store.canvas_history.save(chat,{'title':'Corso','content':encode(deck),'media':[]})
        return saved,deck

    def test_revision_changes_only_selected_page_and_preserves_original_history(self):
        chat=self.app.store.create_chat()['id'];saved,original=self.deck(chat)
        original['pages'][0].update(notes='Approfondimento del relatore [R1].',editorial={'content':'Spiegazione estesa.', 'visual_plan':'Confronto annotato.'})
        saved=self.app.store.canvas_history.save(chat,{'title':'Corso','content':encode(original),'media':[]})
        with patch.object(self.app.engine,'require_model',side_effect=self.model_for):
            sent=enqueue(self.app,chat,{'artifact_id':saved['id'],'page':0,'prompt':'Rendi il titolo più vivace'})
        job=self.app.store.one('SELECT * FROM jobs WHERE id=?',(sent['job_id'],))
        def complete(messages,settings,cancel,**kw):
            self.assertIn('Palette calda',messages[-2]['content']);self.assertIn('1280, 960',messages[-2]['content'])
            self.assertIn('STILE VISIVO: giocoso / colorato',messages[0]['content'])
            self.assertIn('Illustrazioni: immaginative',messages[0]['content'])
            self.assertIn('Spiegazione estesa.',messages[-2]['content'])
            self.assertIn('Approfondimento del relatore',messages[-2]['content'])
            self.assertIn('Rendi il titolo più vivace',messages[-1]['content'])
            self.assertNotIn('Spiegazione estesa.',messages[-1]['content'])
            kw['on_text']('<main><h1>Nuovo')
            return '<main style="color:#123"><h1>Nuovo titolo</h1><p>Testo corretto [R1]</p></main>','stop'
        with patch.object(self.app.engine,'require_model',side_effect=self.model_for),patch.object(self.app.engine,'prepare'),patch.object(self.app.engine,'start_llama'),patch.object(self.app.engine,'completion',side_effect=complete):
            self.app.execute_job(job,threading.Event())
        answer=self.app.store.messages(chat)[-1];self.assertEqual(answer['status'],'done',answer['meta'].get('error'))
        result=json.loads(answer['meta']['artifact']['content'][len(PREFIX):-4])
        self.assertEqual(result['pages'][1],original['pages'][1]);self.assertIn('Nuovo titolo',result['pages'][0]['html'])
        self.assertEqual(result['pages'][0]['notes'],original['pages'][0]['notes'])
        self.assertEqual(result['pages'][0]['editorial'],original['pages'][0]['editorial'])
        self.assertEqual(self.app.store.canvas_history.get(chat,saved['id'])['content'],encode(original))
        self.assertEqual(len(self.app.store.canvas_history.listing(chat)['items']),3)
        self.assertNotIn('<main>',answer['content'])

    def test_current_edit_is_separate_and_original_html_is_not_cut_at_12000_characters(self):
        chat=self.app.store.create_chat()['id'];_,deck=self.deck(chat)
        original='<main><h1>Originale</h1><p>'+('Contenuto originale importante. '*1100)+'</p></main><style>body{background:purple}</style>'
        deck['pages'][0].update(html=original,editorial={'content':'Vecchie istruzioni: sfondo viola.', 'visual_plan':'Conserva il vecchio colore.'})
        saved=self.app.store.canvas_history.save(chat,{'title':deck['title'],'content':encode(deck),'media':[]})
        self.app.store.save_settings({'context':80000,'max_tokens':40000})
        prompt='Cambia lo sfondo in giallo e aggiungi un diagramma.'
        with patch.object(self.app.engine,'require_model',side_effect=self.model_for):sent=enqueue(self.app,chat,{'artifact_id':saved['id'],'page':0,'prompt':prompt})
        job=self.app.store.one('SELECT * FROM jobs WHERE id=?',(sent['job_id'],));payload=json.loads(job['payload'])
        self.assertEqual(payload['settings']['_slide_revision']['prompt'],prompt)
        def complete(messages,settings,cancel,**kw):
            data=json.loads(messages[-2]['content'].split('\n',1)[1])
            self.assertEqual(data['original_html'],original)
            self.assertIn('background:purple',messages[-2]['content'])
            self.assertNotIn('sfondo viola',messages[-1]['content'])
            self.assertIn(prompt,messages[-1]['content'])
            self.assertIn('prevale',messages[0]['content'])
            return '<main><h1>Nuova composizione</h1><svg><rect width="30" height="40"/></svg></main><style>body{background:yellow}</style>','stop'
        with patch.object(self.app.engine,'require_model',side_effect=self.model_for),patch.object(self.app.engine,'prepare'),patch.object(self.app.engine,'start_llama'),patch.object(self.app.engine,'completion',side_effect=complete):self.app.execute_job(job,threading.Event())
        answer=self.app.store.messages(chat)[-1];self.assertEqual(answer['status'],'done',answer['meta'].get('error'))
        self.assertNotIn('original_html',answer['meta']['slide_revision']['input']['truncated_fields'])
        self.assertEqual(answer['meta']['slide_revision']['input']['html_included_characters'],len(original))

    def test_css_only_stream_keeps_previous_preview_and_reports_progress_before_html(self):
        from types import SimpleNamespace
        import itertools
        chat=self.app.store.create_chat()['id'];saved,original=self.deck(chat)
        with patch.object(self.app.engine,'require_model',side_effect=self.model_for):sent=enqueue(self.app,chat,{'artifact_id':saved['id'],'page':0,'prompt':'Aggiungi uno schema con tre frecce'})
        job=self.app.store.one('SELECT * FROM jobs WHERE id=?',(sent['job_id'],))
        css='<style>body{background:yellow;color:black}'
        visible=css+'</style><main><h1>Schema nuovo</h1><svg><path d="M0 0L5 5"/></svg></main>'
        def complete(messages,settings,cancel,**kw):
            kw['on_text'](css)
            answer=self.app.store.messages(chat)[-1];progress=answer['meta']['slide_revision']
            current=json.loads(answer['meta']['artifact']['content'][len(PREFIX):-4])
            self.assertEqual(current['pages'][0]['html'],original['pages'][0]['html'])
            self.assertEqual(progress['characters'],len(css));self.assertEqual(progress['phase'],'generating');self.assertGreater(progress['elapsed_seconds'],0)
            self.assertIn('caratteri ricevuti',self.app.store.one('SELECT stage FROM jobs WHERE id=?',(job['id'],))['stage'])
            kw['on_text'](visible)
            current=json.loads(self.app.store.messages(chat)[-1]['meta']['artifact']['content'][len(PREFIX):-4])
            self.assertEqual(current['pages'][0]['html'],visible)
            return visible,'stop'
        clock=SimpleNamespace(monotonic=lambda:next(ticks));ticks=iter(itertools.count(100,.5))
        with patch.object(self.app.engine,'require_model',side_effect=self.model_for),patch.object(self.app.engine,'prepare'),patch.object(self.app.engine,'start_llama'),patch.object(self.app.engine,'completion',side_effect=complete),patch('h3chat.slide_revision.time',clock):self.app.execute_job(job,threading.Event())
        answer=self.app.store.messages(chat)[-1];self.assertEqual(answer['status'],'done',answer['meta'].get('error'))
        self.assertEqual(answer['meta']['slide_revision']['phase'],'ready');self.assertGreater(answer['meta']['slide_timing']['revision_seconds'],0)

    def test_identical_html_gets_one_targeted_repair_for_the_current_edit(self):
        chat=self.app.store.create_chat()['id'];_,deck=self.deck(chat)
        original='<main style="color:purple"><h1>Prima</h1></main>'
        deck['pages'][0]['html']=original;saved=self.app.store.canvas_history.save(chat,{'title':deck['title'],'content':encode(deck),'media':[]})
        prompt='Usa il verde al posto del viola.'
        with patch.object(self.app.engine,'require_model',side_effect=self.model_for):sent=enqueue(self.app,chat,{'artifact_id':saved['id'],'page':0,'prompt':prompt})
        job=self.app.store.one('SELECT * FROM jobs WHERE id=?',(sent['job_id'],));calls=[]
        def complete(messages,settings,cancel,**kw):
            calls.append(messages)
            if len(calls)==1:return original,'stop'
            self.assertIn('HTML identico',messages[-1]['content']);self.assertIn(prompt,messages[-1]['content'])
            return original.replace('purple','green'),'stop'
        with patch.object(self.app.engine,'require_model',side_effect=self.model_for),patch.object(self.app.engine,'prepare'),patch.object(self.app.engine,'start_llama'),patch.object(self.app.engine,'completion',side_effect=complete):self.app.execute_job(job,threading.Event())
        answer=self.app.store.messages(chat)[-1];self.assertEqual(answer['status'],'done',answer['meta'].get('error'));self.assertEqual(len(calls),2)
        self.assertTrue(answer['meta']['slide_revision']['changed']);self.assertTrue(answer['meta']['slide_revision']['unchanged_response']);self.assertEqual(answer['meta']['slide_revision']['attempt'],2)
        result=json.loads(answer['meta']['artifact']['content'][len(PREFIX):-4]);self.assertNotIn('revision_prompt',result['pages'][0]);self.assertEqual(result['pages'][1],deck['pages'][1])

    def test_identical_second_response_fails_without_losing_current_edit_or_other_pages(self):
        chat=self.app.store.create_chat()['id'];_,deck=self.deck(chat);original='<main style="color:purple"><h1>Prima</h1></main>'
        deck['pages'][0]['html']=original;saved=self.app.store.canvas_history.save(chat,{'title':deck['title'],'content':encode(deck),'media':[]})
        prompt='Cambia i colori e aggiungi il diagramma.'
        with patch.object(self.app.engine,'require_model',side_effect=self.model_for):sent=enqueue(self.app,chat,{'artifact_id':saved['id'],'page':0,'prompt':prompt})
        job=self.app.store.one('SELECT * FROM jobs WHERE id=?',(sent['job_id'],))
        with patch.object(self.app.engine,'require_model',side_effect=self.model_for),patch.object(self.app.engine,'prepare'),patch.object(self.app.engine,'start_llama'),patch.object(self.app.engine,'completion',return_value=(original,'stop')) as complete:self.app.execute_job(job,threading.Event())
        answer=self.app.store.messages(chat)[-1];self.assertEqual(answer['status'],'failed');self.assertEqual(complete.call_count,2)
        self.assertIn('identica',answer['meta']['error']);self.assertEqual(answer['meta']['slide_revision']['phase'],'interrupted')
        result=json.loads(answer['meta']['artifact']['content'][len(PREFIX):-4]);self.assertEqual(result['pages'][0]['revision_prompt'],prompt);self.assertEqual(result['pages'][0]['html'],original)
        self.assertEqual(result['pages'][1],deck['pages'][1]);self.assertEqual(self.app.store.canvas_history.get(chat,saved['id'])['content'],encode(deck))

    def test_resume_may_reuse_an_already_prepared_engine(self):
        from h3chat.slide_revision import build
        chat=self.app.store.create_chat()['id'];saved,deck=self.deck(chat)
        with patch.object(self.app.engine,'require_model',side_effect=self.model_for):sent=enqueue(self.app,chat,{'artifact_id':saved['id'],'page':0,'prompt':'Titolo nuovo'})
        job=self.app.store.one('SELECT * FROM jobs WHERE id=?',(sent['job_id'],));payload=json.loads(job['payload'])
        with patch.object(self.app.engine,'prepare') as prepare,patch.object(self.app.engine,'start_llama') as start,patch.object(self.app.engine,'completion',return_value=('<main style="color:green"><h1>Nuovo</h1></main>','stop')):
            artifact=build(self.app,job,payload,payload['settings'],self.model,threading.Event(),lambda value:None,Path(self.temp.name)/'resume.log',{},prepare_engine=False)
        prepare.assert_not_called();start.assert_not_called();result=json.loads(artifact['content'][len(PREFIX):-4]);self.assertEqual(result['pages'][0]['status'],'ready');self.assertEqual(result['pages'][1],deck['pages'][1])

    def test_resume_can_validate_unchanged_complete_html_without_treating_it_as_ignored_edit(self):
        from h3chat.slide_revision import build
        chat=self.app.store.create_chat()['id'];_,deck=self.deck(chat)
        html='<main style="color:purple"><h1>Pagina già ricevuta per intero</h1></main>'
        deck['pages'][0].update(html=html,status='interrupted')
        saved=self.app.store.canvas_history.save(chat,{'title':deck['title'],'content':encode(deck),'media':[]})
        with patch.object(self.app.engine,'require_model',side_effect=self.model_for):sent=enqueue(self.app,chat,{'artifact_id':saved['id'],'page':0,'prompt':'Completa la pagina interrotta.'})
        job=self.app.store.one('SELECT * FROM jobs WHERE id=?',(sent['job_id'],));payload=json.loads(job['payload'])
        settings=payload['settings'];settings['_slide_revision']['allow_unchanged']=True;meta={}
        with patch.object(self.app.engine,'completion',return_value=(html,'stop')) as complete:
            artifact=build(self.app,job,payload,settings,self.model,threading.Event(),lambda value:None,Path(self.temp.name)/'resume.log',meta,prepare_engine=False)
        self.assertEqual(complete.call_count,1);result=json.loads(artifact['content'][len(PREFIX):-4])
        self.assertEqual(result['pages'][0]['status'],'ready');self.assertEqual(result['pages'][0]['html'],html)
        self.assertNotIn('revision_prompt',result['pages'][0]);self.assertEqual(result['pages'][1],deck['pages'][1]);self.assertFalse(meta['slide_revision']['changed'])

    def test_cancelled_completion_does_not_persist_a_machine_prompt_as_a_human_edit(self):
        from h3chat.slide_revision import build
        chat=self.app.store.create_chat()['id'];saved,deck=self.deck(chat)
        with patch.object(self.app.engine,'require_model',side_effect=self.model_for):sent=enqueue(self.app,chat,{'artifact_id':saved['id'],'page':0,'prompt':'Completa la pagina.'})
        job=self.app.store.one('SELECT * FROM jobs WHERE id=?',(sent['job_id'],));payload=json.loads(job['payload']);settings=payload['settings'];settings['_slide_revision']['allow_unchanged']=True;meta={}
        def complete(*args,**kwargs):kwargs['on_text']('<style>body{color:green}');raise Cancelled()
        with patch.object(self.app.engine,'completion',side_effect=complete),self.assertRaises(Cancelled):
            build(self.app,job,payload,settings,self.model,threading.Event(),lambda value:None,Path(self.temp.name)/'resume.log',meta,prepare_engine=False)
        result=json.loads(meta['artifact']['content'][len(PREFIX):-4]);self.assertEqual(result['pages'][0]['status'],'interrupted');self.assertNotIn('revision_prompt',result['pages'][0]);self.assertEqual(result['pages'][1],deck['pages'][1])

    def test_only_explicit_resume_plan_reinserts_an_assigned_image(self):
        from h3chat.slide_revision import build
        chat=self.app.store.create_chat()['id'];_,deck=self.deck(chat)
        picture=self.app.upload({'name':'diagram.png','data':'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aOKsAAAAASUVORK5CYII='})
        saved=self.app.store.canvas_history.save(chat,{'title':deck['title'],'content':encode(deck),'media':[picture]})
        for planned in (False,True):
            with patch.object(self.app.engine,'require_model',side_effect=self.model_for):sent=enqueue(self.app,chat,{'artifact_id':saved['id'],'page':0,'prompt':'Ricrea la composizione.'})
            job=self.app.store.one('SELECT * FROM jobs WHERE id=?',(sent['job_id'],));payload=json.loads(job['payload']);settings=payload['settings'];meta={};calls=[]
            if planned:settings['_slide_revision']['planned_images']=[{'slide':1,'asset_id':picture['id'],'description':'Diagramma assegnato'}]
            def complete(messages,settings,cancel,**kw):
                calls.append(messages);figure=''
                if len(calls)==2:
                    self.assertIn('illustrazioni già generate',messages[-1]['content']);self.assertIn(picture['id'],messages[-1]['content'])
                    figure='<img data-asset-id="'+picture['id']+'">'
                return '<main style="color:green"><h1>Nuova composizione</h1>'+figure+'</main>','stop'
            with patch.object(self.app.engine,'completion',side_effect=complete):
                artifact=build(self.app,job,payload,settings,self.model,threading.Event(),lambda value:None,Path(self.temp.name)/'resume.log',meta,prepare_engine=False)
            self.app.store.execute("UPDATE jobs SET status='done' WHERE id=?",(job['id'],))
            result=json.loads(artifact['content'][len(PREFIX):-4]);self.assertEqual(len(calls),2 if planned else 1);self.assertEqual(picture['id'] in result['pages'][0]['html'],planned);self.assertEqual(result['pages'][1],deck['pages'][1])

    def test_revision_uses_saved_slide_colors_not_current_infographic_palette(self):
        chat=self.app.store.create_chat()['id'];_,deck=self.deck(chat)
        deck.update(background='dark',palette='vivid')
        saved=self.app.store.canvas_history.save(chat,{'title':deck['title'],'content':encode(deck),'media':[]})
        with patch.object(self.app.engine,'require_model',side_effect=self.model_for):
            sent=enqueue(self.app,chat,{'artifact_id':saved['id'],'page':0,'prompt':'Amplia la spiegazione'})
        job=self.app.store.one('SELECT * FROM jobs WHERE id=?',(sent['job_id'],))
        def complete(messages,settings,cancel,**kw):
            self.assertIn('Sfondo principale scuro',messages[0]['content'])
            self.assertIn('colori vivaci e saturi',messages[0]['content'])
            return '<style>body{background:#123;color:white}</style><main><h1>Nuova spiegazione</h1></main>','stop'
        with patch.object(self.app.engine,'require_model',side_effect=self.model_for),patch.object(self.app.engine,'prepare'),patch.object(self.app.engine,'start_llama'),patch.object(self.app.engine,'completion',side_effect=complete):
            self.app.execute_job(job,threading.Event())
        answer=self.app.store.messages(chat)[-1];self.assertEqual(answer['status'],'done',answer['meta'].get('error'))
        result=json.loads(answer['meta']['artifact']['content'][len(PREFIX):-4])
        self.assertEqual(result['background'],'dark');self.assertEqual(result['palette'],'vivid')
        self.assertEqual(result['pages'][1],deck['pages'][1])

    def test_unstyled_revision_is_not_marked_ready_and_keeps_other_pages(self):
        chat=self.app.store.create_chat()['id'];saved,original=self.deck(chat)
        with patch.object(self.app.engine,'require_model',side_effect=self.model_for):
            sent=enqueue(self.app,chat,{'artifact_id':saved['id'],'page':0,'prompt':'Ricrea con grafica completa'})
        job=self.app.store.one('SELECT * FROM jobs WHERE id=?',(sent['job_id'],))
        def complete(*args,**kw):
            html='<main class="layout"><h1>Testo senza CSS</h1></main>'
            kw['on_text'](html)
            return html,'stop'
        with patch.object(self.app.engine,'require_model',side_effect=self.model_for),patch.object(self.app.engine,'prepare'),patch.object(self.app.engine,'start_llama'),patch.object(self.app.engine,'completion',side_effect=complete) as completion:
            self.app.execute_job(job,threading.Event())
        answer=self.app.store.messages(chat)[-1]
        self.assertEqual(answer['status'],'failed');self.assertEqual(completion.call_count,2)
        self.assertIn('CSS',answer['meta']['error'])
        result=json.loads(answer['meta']['artifact']['content'][len(PREFIX):-4])
        self.assertEqual(result['pages'][0]['status'],'interrupted')
        self.assertEqual(result['pages'][1],original['pages'][1])
        self.assertEqual(self.app.store.canvas_history.get(chat,saved['id'])['content'],encode(original))

    def test_static_revision_can_receive_choreography_without_rewriting_other_pages_or_audio(self):
        from h3chat.infographic_choreography import targets
        from h3chat.infographic_animation import playable
        chat=self.app.store.create_chat()['id'];_,deck=self.deck(chat)
        deck['infographic']={'version':1,'durations':[3,3],'transition':'fade','sfx':'none','options':{'output':'video'}}
        deck['pages'][0]['notes']='Spiegazione già registrata.'
        saved=self.app.store.canvas_history.save(chat,{'title':deck['title'],'content':encode(deck),'media':[]})
        with patch.object(self.app.engine,'require_model',side_effect=self.model_for):
            sent=enqueue(self.app,chat,{'artifact_id':saved['id'],'page':0,'prompt':'Anima la spiegazione'})
        job=self.app.store.one('SELECT * FROM jobs WHERE id=?',(sent['job_id'],));html=deck['pages'][0]['html'];calls=[]
        def complete(messages,settings,cancel,**kw):
            calls.append(messages)
            if kw.get('schema'):
                row=next(row for row in targets(html) if row['tag']=='h1')
                return json.dumps({'animations':[{'target':row['id'],'motion':'fade','start':.2,'duration':.7,'out':-1,'ease':'smooth'}]}),'stop'
            return html,'stop'
        with patch.object(self.app.engine,'require_model',side_effect=self.model_for),patch.object(self.app.engine,'prepare'),patch.object(self.app.engine,'start_llama'),patch.object(self.app.engine,'completion',side_effect=complete),patch('h3chat.voice.synthesize') as voice:
            self.app.execute_job(job,threading.Event())
        answer=self.app.store.messages(chat)[-1];self.assertEqual(answer['status'],'done',answer['meta'].get('error'))
        result=json.loads(answer['meta']['artifact']['content'][len(PREFIX):-4])
        self.assertTrue(playable(result['pages'][0]['html'],3));self.assertEqual(len(calls),3)
        self.assertEqual(result['pages'][0]['notes'],deck['pages'][0]['notes']);self.assertEqual(result['pages'][1],deck['pages'][1]);voice.assert_not_called()

    def test_revision_refuses_foreign_artifact_and_cancel_keeps_other_pages(self):
        chat=self.app.store.create_chat()['id'];other=self.app.store.create_chat()['id'];saved,original=self.deck(chat)
        with self.assertRaises(ValueError):enqueue(self.app,other,{'artifact_id':saved['id'],'page':0,'prompt':'Cambia'})
        with patch.object(self.app.engine,'require_model',side_effect=self.model_for):sent=enqueue(self.app,chat,{'artifact_id':saved['id'],'page':0,'prompt':'Cambia'})
        job=self.app.store.one('SELECT * FROM jobs WHERE id=?',(sent['job_id'],))
        def complete(*args,**kw):kw['on_text']('<main><h1>Parziale');raise Cancelled()
        with patch.object(self.app.engine,'require_model',side_effect=self.model_for),patch.object(self.app.engine,'prepare'),patch.object(self.app.engine,'start_llama'),patch.object(self.app.engine,'completion',side_effect=complete):self.app.execute_job(job,threading.Event())
        answer=self.app.store.messages(chat)[-1];self.assertEqual(answer['status'],'cancelled')
        result=json.loads(answer['meta']['artifact']['content'][len(PREFIX):-4])
        self.assertEqual(result['pages'][1],original['pages'][1]);self.assertEqual(result['pages'][0]['status'],'interrupted')

    def test_infographic_revision_recreates_motion_but_movie_updates_only_on_explicit_export(self):
        chat=self.app.store.create_chat()['id'];_,deck=self.deck(chat)
        deck['infographic']={'version':1,'durations':[3,3],'transition':'cut','sfx':'none','voice_id':'voice','music_id':'music','options':{'layout':'columns2','panel_appearance':'sequence','panel_order':'21'}}
        media=[{'id':ident,'name':ident+'.wav','mime':'audio/wav','path':'uploads/'+ident+'.wav'} for ident in ('voice','music')]
        media.append({'id':'old','name':'old.mp4','mime':'video/mp4','path':'outputs/old.mp4'})
        for item in media:
            path=self.app.data/item['path'];path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(b'fixture')
        saved=self.app.store.canvas_history.save(chat,{'title':deck['title'],'content':encode(deck),'media':media})
        with patch.object(self.app.engine,'require_model',side_effect=self.model_for):sent=enqueue(self.app,chat,{'artifact_id':saved['id'],'page':0,'prompt':'Cambia il titolo e anima i due pannelli'})
        job=self.app.store.one('SELECT * FROM jobs WHERE id=?',(sent['job_id'],))
        attempts=[]
        def complete(messages,settings,cancel,**kw):
            self.assertIn('data-motion=',messages[0]['content']);self.assertIn('ordine 21',messages[0]['content']);self.assertIn('3 secondi',messages[0]['content'])
            self.assertNotIn('HTML statico completo.',messages[0]['content']);attempts.append(messages)
            if len(attempts)==1:return '<section data-panel="1"><h1>Nuovo</h1></section><section data-panel="2"><p>Secondo pannello</p></section>','stop'
            self.assertIn('La scena restituita è statica',messages[-1]['content'])
            return '<section data-panel="1"><h1 data-motion="fade" data-start=".8">Nuovo</h1></section><section data-panel="2"><p data-motion="slide">Secondo pannello</p></section>','stop'
        def tool(worker,request,*args,**kwargs):
            self.assertEqual(worker,'infographic-worker.py');self.assertEqual(request['deck']['pages'][1],deck['pages'][1])
            self.assertEqual(request['voice'],str(self.app.data/'uploads/voice.wav'));self.assertEqual(request['music'],str(self.app.data/'uploads/music.wav'))
            Path(request['output']).write_bytes(b'updated movie');return {}
        with patch.object(self.app.engine,'require_model',side_effect=self.model_for),patch.object(self.app.engine,'prepare'),patch.object(self.app.engine,'start_llama'),patch.object(self.app.engine,'completion',side_effect=complete),patch.object(self.app.engine,'tool_call',side_effect=tool) as render,patch.object(self.app.engine,'stop'):
            self.app.execute_job(job,threading.Event())
        answer=self.app.store.messages(chat)[-1];self.assertEqual(answer['status'],'done',answer['meta'].get('error'));render.assert_not_called()
        artifact=answer['meta']['artifact'];self.assertNotIn('aggiornato anche il filmato',answer['content'])
        self.assertEqual(len(attempts),2)
        self.assertEqual(artifact['media'],media)
        self.assertEqual(self.app.store.canvas_history.get(chat,saved['id'])['content'],encode(deck))
        from h3chat.infographics import enqueue_render
        current=self.app.store.canvas_history.get(chat)
        queued=enqueue_render(self.app,chat,{'artifact_id':current['id']})
        render_job=self.app.store.one('SELECT * FROM jobs WHERE id=?',(queued['job_id'],))
        with patch.object(self.app.engine,'tool_call',side_effect=tool) as explicit_render,patch.object(self.app.engine,'stop'):
            self.app.execute_job(render_job,threading.Event())
        answer=self.app.store.messages(chat)[-1];self.assertEqual(answer['status'],'done',answer['meta'].get('error'));self.assertEqual(explicit_render.call_count,1)
        self.assertNotIn('old',{m['id'] for m in answer['meta']['artifact']['media']});self.assertTrue({'voice','music'}<={m['id'] for m in answer['meta']['artifact']['media']})

    def test_all_images_are_planned_then_generated_before_html_and_catalog_is_reused(self):
        chat=self.app.store.create_chat()['id']
        with patch.object(self.app.engine,'require_model',side_effect=self.model_for):
            sent=self.app.send(chat,{'prompt':'Crea 2 slide','slides':{'generate_images':True,'image_model':'fixture-image'}})
        job=self.app.store.one('SELECT * FROM jobs WHERE id=?',(sent['job_id'],));generated=[]
        def complete(messages,settings,cancel,**kw):
            schema=kw.get('schema')
            if schema and 'slides' in schema['properties']:
                self.events.append('outline');return json.dumps({'title':'Corso','slides':[{'title':'A','purpose':'Introduzione'},{'title':'B','purpose':'Esempio'}]}),'stop'
            if schema and 'content' in schema['properties']:
                self.events.append('editorial')
                return json.dumps({'content':'Esempio concreto di confronto.', 'visual_plan':'Confronto annotato fra due procedure.', 'notes':'Note complete del relatore.','sources':[]}),'stop'
            if schema and 'images' in schema['properties']:
                self.events.append('image-plan');self.assertIn('tag descrittivi in inglese',messages[-1]['content'])
                self.assertIn('IMMAGINI GENERATE SENZA TESTO',messages[0]['content'])
                self.assertIn('Nessun testo, neppure grande',messages[-1]['content'])
                self.assertIn('Esempio concreto di confronto.',messages[-1]['content'])
                return json.dumps({'images':[{'slide':i,'prompt':'colorful illustration, abstract shapes','description':'Illustrazione '+str(i)} for i in (1,2)]}),'stop'
            self.events.append('html');self.assertEqual(len(generated),2);self.assertTrue(all(image['id'] in str(messages) for image in generated))
            repair=messages[-1]['content'].startswith('Questa pagina deve usare')
            index=1 if repair or 'Crea SOLO la pagina 2/' in messages[-1]['content'] else 0
            figure='' if index==1 and not repair else '<img data-asset-id="'+generated[index]['id']+'">'
            html='<main><h1>Slide</h1>'+figure+'</main>';kw['on_text'](html);return html,'stop'
        def generate(model,settings,prompt,refs,ident,cancel,stage):
            self.events.append('image');self.assertEqual(settings['memory_policy'],'on_demand');self.assertEqual(settings['ram_cache_gb'],0)
            self.assertIn('no text',prompt);self.assertIn('no letters',prompt)
            image={'id':ident,'mime':'image/png','name':'image.png','path':'outputs/'+ident+'/image.png'};generated.append(image);return image
        with patch.object(self.app.engine,'require_model',side_effect=self.model_for),patch.object(self.app.engine,'prepare'),patch.object(self.app.engine,'start_llama') as llm,patch.object(self.app.engine,'generate',side_effect=generate),patch.object(self.app.engine,'completion',side_effect=complete):self.app.execute_job(job,threading.Event())
        answer=self.app.store.messages(chat)[-1];self.assertEqual(answer['status'],'done',answer['meta'].get('error'))
        self.assertEqual(self.events,['outline','editorial','editorial','image-plan','image','image','html','html','html']);self.assertEqual(llm.call_count,2)
        self.assertEqual(len(answer['meta']['artifact']['media']),2)
        deck=json.loads(answer['meta']['artifact']['content'][len(PREFIX):-4])
        for index,image in enumerate(generated):self.assertIn(image['id'],deck['pages'][index]['html'])
        self.assertEqual([item['asset_id'] for item in deck['image_generation']['plan']],[image['id'] for image in generated])
        self.assertFalse(options('').get('generate_images',False))
        with self.assertRaises(ValueError):options('',{'generate_images':'yes'})

    def test_portrait_revision_measures_composition_and_asks_llm_to_reflow_without_movie_export(self):
        chat=self.app.store.create_chat()['id'];_,deck=self.deck(chat);deck['format']='9:16'
        deck['infographic']={'version':1,'durations':[10,10],'transition':'cut','sfx':'none','options':{'output':'video'}}
        deck['pages'][0]['notes']='Una narrazione già registrata.'
        saved=self.app.store.canvas_history.save(chat,{'title':deck['title'],'content':encode(deck),'media':[]})
        with patch.object(self.app.engine,'require_model',side_effect=self.model_for):sent=enqueue(self.app,chat,{'artifact_id':saved['id'],'page':0,'prompt':'Adatta la composizione al formato verticale'})
        job=self.app.store.one('SELECT * FROM jobs WHERE id=?',(sent['job_id'],));calls=[];probes=[]
        def complete(messages,settings,cancel,**kw):
            calls.append(messages)
            if len(calls)==1:
                self.assertIn('VERTICALE',messages[-1]['content']);self.assertIn('Una narrazione già registrata.',messages[-1]['content'])
                return '<h1 data-motion="fade">Layout compatto</h1>','stop'
            self.assertIn('950 px',messages[-1]['content'])
            return '<main data-motion="fade"><h1>Layout verticale</h1></main>','stop'
        def tool(worker,request,*args,**kw):
            self.assertEqual(request['mode'],'layout');self.assertEqual(len(request['deck']['pages']),1);probes.append(request)
            return {'pages':[{'issue':len(probes)==1,'largest_gap':950,'gap_ratio':.42}]}
        with patch.object(self.app.engine,'require_model',side_effect=self.model_for),patch.object(self.app.engine,'prepare'),patch.object(self.app.engine,'start_llama'),patch.object(self.app.engine,'completion',side_effect=complete),patch.object(self.app.engine,'tool_call',side_effect=tool):self.app.execute_job(job,threading.Event())
        answer=self.app.store.messages(chat)[-1];self.assertEqual(answer['status'],'done',answer['meta'].get('error'))
        result=json.loads(answer['meta']['artifact']['content'][len(PREFIX):-4]);self.assertEqual(len(probes),2);self.assertEqual(result['pages'][1],deck['pages'][1]);self.assertIn('Layout verticale',result['pages'][0]['html'])
        self.assertEqual(result['pages'][0]['notes'],deck['pages'][0]['notes']);self.assertEqual(answer['meta']['artifact']['media'],[])


class NaturalVoiceTests(unittest.TestCase):
    def test_natural_voice_does_not_force_flat_prosody_and_other_controls_remain_explicit(self):
        _,natural=controls(copy.deepcopy(VOICE),'Leggi questo testo')
        self.assertNotIn('prosody:expressive_low',natural['tags']);self.assertNotIn('prosody:expressive_high',natural['tags'])
        _,warm=controls(VOICE|{'_voice_fields':{'expressiveness':'high','emotion':'affection'}},'Leggi il testo')
        self.assertIn('prosody:expressive_high',warm['tags']);self.assertIn('emotion:affection',warm['tags'])
        _,quiet=controls(VOICE|{'_voice_fields':{'expressiveness':'low'}},'Leggi il testo')
        self.assertIn('prosody:expressive_low',quiet['tags'])
        with self.assertRaises(ValueError):validate_fields({'expressiveness':'unknown'})

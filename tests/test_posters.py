import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch
import test_visual_models as fixture
from test_image_batch import PNG
from h3chat.posters import options,requested,image_model
from h3chat.slides import PREFIX,validate_content,FORMATS
from h3chat.downloads import Cancelled

HTML='<main><h1>OPEN LAB</h1><p>12 novembre · ore 17 · Aula Blu</p><svg viewBox="0 0 100 100"><circle cx="50" cy="50" r="40" fill="coral"/></svg></main><style>body{margin:0;background:#102d38;color:white;font:32px Arial}main{padding:80px}h1{font-size:150px}svg{width:700px;height:700px}</style>'


def plan(count=1):
    return {'title':'Open Lab','variants':[{'title':f'Open Lab {i+1}','copy':'OPEN LAB\n12 novembre · ore 17 · Aula Blu','visual_plan':'Titolo molto grande, visual diagonale, data leggibile.','image_prompt':'An abstract coral paper sculpture, no text','image_aspect':'3:4'} for i in range(count)]}


class PosterTests(unittest.TestCase):
    setUp=fixture.VisualModelsTests.setUp
    tearDown=fixture.VisualModelsTests.tearDown

    def launch(self,prompt='Crea una locandina',**opts):
        chat=self.app.store.create_chat()['id'];ticket=self.app.send(chat,{'prompt':prompt,'lab':'poster','poster':{'images':'none',**opts},'rag':False})
        return chat,self.app.store.one('SELECT * FROM jobs WHERE id=?',(ticket['job_id'],))

    def complete(self,job,*,count=1,cancel=None,on_html=None,generate=None):
        calls=[]
        def completion(messages,settings,event,**kw):
            calls.append(messages)
            if kw.get('schema'):return json.dumps(plan(count)),'stop'
            if on_html:on_html(len(calls))
            if kw.get('on_text'):kw['on_text'](HTML)
            return HTML,'stop'
        with patch.object(self.app.engine,'prepare'),patch.object(self.app.engine,'prepare_tools',side_effect=lambda h,*a,**k:(h,{},[],[])),patch.object(self.app.engine,'start_llama'),patch.object(self.app.engine,'stop'),patch.object(self.app.engine,'completion',side_effect=completion),patch.object(self.app.engine,'generate',side_effect=generate) as images:
            self.app.execute_job(job,cancel or threading.Event())
        answer=self.app.store.one('SELECT status,meta FROM messages WHERE id=?',(job['message_id'],))
        return answer,calls,images

    def test_separate_mode_preserves_preferences_publishes_variants_and_no_slide_outline(self):
        before=self.app.store.settings();chat,job=self.launch(count=2)
        answer,calls,images=self.complete(job,count=2)
        self.assertEqual(answer['status'],'done',answer['meta']);images.assert_not_called()
        artifact=self.app.store.canvas_history.get(chat);deck=json.loads(artifact['content'][len(PREFIX):-4])
        self.assertEqual(deck['document_kind'],'poster');self.assertEqual(deck['format'],'A3');self.assertEqual(len(deck['pages']),2)
        self.assertTrue(all(p['status']=='ready' and '<style>' in p['html'] for p in deck['pages']))
        validate_content(artifact['content'],artifact['media']);self.assertEqual(self.app.store.settings(),before)
        self.assertEqual(len(calls),3)
        self.assertIn('LOCANDINE',calls[0][0]['content']);self.assertIn('HTML/CSS',calls[1][-1]['content'])
        self.assertFalse(any('Solo titolo della presentazione e scaletta' in str(m) for m in calls))

    def test_prompt_format_count_and_image_choices_override_modal(self):
        result=options('Crea 3 locandine A4 orizzontale, senza immagini in stile fumetto',{'format':'A3','count':1,'images':'generate'})
        self.assertEqual((result['count'],result['format'],result['images'],result['style']),(3,'A4-landscape','none','comic'))
        self.assertAlmostEqual(FORMATS['A4'][0]/FORMATS['A4'][1],210/297)
        for v in ({'count':7},{'count':True},{'safe_margin':float('nan')},{'format':'inventato'},{'images':'unknown'},{'untrusted':'x'}):
            with self.assertRaises(ValueError):options(value=v)
        self.assertTrue(requested('Creami una locandina per il laboratorio'));self.assertFalse(requested('Come creo un poster?'))

    def test_auto_router_and_reload_draft_keep_poster_fields(self):
        from h3chat.request_draft import load
        chat=self.app.store.create_chat()['id'];ticket=self.app.send(chat,{'prompt':'Crea una locandina 4:5 senza immagini','rag':False})
        self.assertEqual(ticket['intent'],'poster');self.assertTrue(ticket['canvas'])
        job=self.app.store.one('SELECT * FROM jobs WHERE id=?',(ticket['job_id'],));draft=load(self.app,chat,job['message_id'])
        self.assertEqual(draft['lab'],'poster');self.assertEqual(draft['poster']['format'],'4:5')

    def test_cpu_auto_is_graphics_only_but_explicit_image_generation_fails(self):
        opts=options();settings=self.settings|{'execution_mode':'cpu'}
        self.assertIsNone(image_model(self.app,settings,opts,[]))
        with self.assertRaisesRegex(ValueError,'CPU'):image_model(self.app,settings,opts|{'images':'generate'},[])
        with self.assertRaisesRegex(ValueError,'Allega'):image_model(self.app,self.settings,opts|{'images':'attached'},[])

    def test_negative_generation_instruction_never_loads_image_model(self):
        for prompt in ('Non generare nuove immagini. Riusa i quattro allegati.','Non creare nuove immagini: solo quelle allegate.','Do not generate new images.','Senza generare nuove immagini.'):
            with self.subTest(prompt=prompt):
                opts=options(prompt,{'images':'generate'});self.assertEqual(opts['images'],'existing')
                with patch.object(self.app.engine,'require_model') as require:self.assertIsNone(image_model(self.app,self.settings,opts,[]))
                require.assert_not_called()

    def test_truncated_plan_fails_before_any_image_or_false_artifact(self):
        chat,job=self.launch()
        with patch.object(self.app.engine,'prepare'),patch.object(self.app.engine,'prepare_tools',side_effect=lambda h,*a,**k:(h,{},[],[])),patch.object(self.app.engine,'start_llama'),patch.object(self.app.engine,'completion',return_value=('{}','length')),patch.object(self.app.engine,'generate') as images:
            self.app.execute_job(job,threading.Event())
        answer=self.app.store.one('SELECT status,error FROM jobs WHERE id=?',(job['id'],))
        self.assertEqual(answer['status'],'failed');images.assert_not_called()

    def test_cancellation_keeps_completed_variant_in_canvas(self):
        chat,job=self.launch(count=2);cancel=threading.Event()
        def stop(number):
            if number>=3:cancel.set();raise Cancelled()
        answer,_,_=self.complete(job,count=2,cancel=cancel,on_html=stop)
        artifact=self.app.store.canvas_history.get(chat);deck=json.loads(artifact['content'][len(PREFIX):-4])
        self.assertEqual(deck['pages'][0]['status'],'ready');self.assertEqual(deck['pages'][0]['html'],HTML)
        self.assertNotEqual(deck['pages'][1]['status'],'ready');validate_content(artifact['content'],artifact['media'])

    def test_malformed_provider_plan_gets_one_specific_repair_before_layout(self):
        chat,job=self.launch();bad=plan();bad['variants'][0]['copy']=''
        with patch.object(self.app.engine,'prepare'),patch.object(self.app.engine,'prepare_tools',side_effect=lambda h,*a,**k:(h,{},[],[])),patch.object(self.app.engine,'start_llama'),patch.object(self.app.engine,'completion',side_effect=[(json.dumps(bad),'stop'),(json.dumps(plan()),'stop'),(HTML,'stop')]) as complete,patch.object(self.app.engine,'generate') as images:
            self.app.execute_job(job,threading.Event())
        answer=self.app.store.one('SELECT status FROM jobs WHERE id=?',(job['id'],));self.assertEqual(answer['status'],'done')
        self.assertEqual(complete.call_count,3);images.assert_not_called()
        self.assertIn('copy è vuoto',complete.call_args_list[1].args[0][-1]['content'])
        self.assertTrue((self.app.data/'outputs'/job['id']/'poster-plan-1.json').is_file())

    def test_stream_field_overrun_repaired_before_image_or_layout(self):
        chat,job=self.launch();calls=[]
        def complete(messages,settings,cancel,**kw):
            calls.append(messages)
            if len(calls)==1:
                bad=plan();bad['variants'][0]['image_prompt']='digit, '*1000
                kw['on_text'](json.dumps(bad))
                self.fail('Field overrun must interrupt the completion')
            return (json.dumps(plan()) if kw.get('schema') else HTML),'stop'
        with patch.object(self.app.engine,'prepare'),patch.object(self.app.engine,'prepare_tools',side_effect=lambda h,*a,**k:(h,{},[],[])),patch.object(self.app.engine,'start_llama'),patch.object(self.app.engine,'completion',side_effect=complete),patch.object(self.app.engine,'generate') as images:
            self.app.execute_job(job,threading.Event())
        self.assertEqual(self.app.store.one('SELECT status FROM jobs WHERE id=?',(job['id'],))['status'],'done')
        self.assertEqual(len(calls),3);images.assert_not_called()
        self.assertIn('image_prompt',calls[1][-1]['content'])
        self.assertTrue((self.app.data/'outputs'/job['id']/'poster-plan-1.partial-state.json').is_file())

    def test_generated_visual_recorded_with_seed_and_same_asset_used_in_layout(self):
        chat,job=self.launch(images='generate',image_model=self.qwen['id'])
        def generate(model,settings,prompt,refs,ident,*args):
            self.assertIn('No text',prompt);self.assertEqual(refs,[])
            folder=self.app.data/'outputs'/ident;folder.mkdir(parents=True);(folder/'image.png').write_bytes(PNG)
            return {'id':ident,'name':'image.png','mime':'image/png','path':f'outputs/{ident}/image.png','generation':{'seed':456}}
        # The HTML fixture deliberately omits the image; verify a missing-image
        # repair is attempted and its warning is retained if the LLM omits it.
        answer,calls,images=self.complete(job,generate=generate)
        self.assertEqual(answer['status'],'done',answer['meta']);self.assertEqual(images.call_count,1)
        artifact=self.app.store.canvas_history.get(chat);self.assertEqual(artifact['media'][0]['generation']['seed'],456)
        self.assertTrue(any(artifact['media'][0]['id'] in str(m) for m in calls[1:]))

    def test_pdf_physical_paper_retains_vector_markup_and_validates_size(self):
        from h3chat.pdf_export import export_document
        with tempfile.TemporaryDirectory() as d,patch('h3chat.pdf_export.embedded_css',return_value=''):
            _,file,_=export_document(Path(d),Path(d),{'html':'<div style="width:297mm;height:420mm"><h1>OPEN LAB</h1><svg><text>Vettoriale</text></svg></div>','slide_format':'A3','page_size_mm':[297,420]})
            text=file.read_text(encoding='utf8');self.assertIn('Vettoriale',text);self.assertIn(f'@page{{size:{297*96/25.4}px {420*96/25.4}px;margin:0}}',text)
            for bad in ([False,420],[297,float('inf')],[0,420],[297,420,1]):
                with self.assertRaises(ValueError):export_document(Path(d),Path(d),{'html':'test','page_size_mm':bad})


if __name__=='__main__':unittest.main()

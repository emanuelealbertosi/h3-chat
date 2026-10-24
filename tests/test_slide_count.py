import json
import threading
import unittest
from unittest.mock import patch
from tests import test_slides as fixtures
from tests.test_slides_html import editorial_response
from h3chat.slides import PREFIX,options,edit_options,encode,validate_content
from h3chat.slide_count import MAX_SLIDES,outline_bounds
from h3chat.slide_context import artifact_summary


class CountOptionsTests(unittest.TestCase):
    def test_explicit_counts_win_and_automatic_is_opt_in(self):
        self.assertEqual(options('')['count'],8)
        self.assertEqual(options('',{'count':'auto'})['count'],'auto')
        for prompt in ('Crea 100 slide','Una presentazione di 100 diapositive','Numero di slide: 100','Slide: 100'):
            self.assertEqual(options(prompt,{'count':'auto'})['count'],100)
        for prompt in ('Decidi tu quante slide servono','Scegli il numero di slide','Numero di slide automatico','Numero automatico di slide','Calcola automaticamente il numero di diapositive','Crea una presentazione, scegli tu quante ne servono'):
            self.assertEqual(options(prompt,{'count':12})['count'],'auto')
        self.assertEqual(options('Crea 20 slide, scegli tu il numero di slide',{'count':'auto'})['count'],20)
        for value in (0,101,True,False,2.5,'100',None,[],{}):
            with self.assertRaises(ValueError):options('',{'count':value})
        with self.assertRaises(ValueError):options('Crea 101 slide',{'count':'auto'})
        for prompt in ('Decidi tu quante slide servono, massimo 100 slide','Scegli tu quante slide servono, da 1 a 100 slide'):
            self.assertEqual(options(prompt)['count'],'auto')
        self.assertEqual(options('Massimo 20 slide',{'count':'auto'})['count'],'auto')
        self.assertEqual(outline_bounds('Tra 10 e 20 slide','auto'),(10,20))
        self.assertEqual(outline_bounds('Massimo 20 slide','auto'),(1,20))
        with self.assertRaises(ValueError):options('Decidi tu quante slide servono, da 40 a 20 slide')

    def test_decks_edits_and_context_include_all_100_pages(self):
        pages=[{'title':f'Pagina {i+1}','nodes':[]} for i in range(100)]
        content=encode({'version':1,'format':'16:9','pages':pages})
        validate_content(content,[])
        self.assertEqual(len(json.loads(artifact_summary(content))['pages']),100)
        self.assertEqual(edit_options('Cambia i colori',content)['count'],100)
        self.assertEqual(edit_options('Decidi tu quante slide servono',content)['count'],'auto')
        with self.assertRaises(ValueError):edit_options('Aggiungi 1 slide',content)
        with self.assertRaises(ValueError):validate_content(encode({'version':1,'format':'16:9','pages':pages+[pages[-1]]}),[])


class CountGenerationTests(unittest.TestCase):
    setUp=fixtures.GenerationTests.setUp
    enqueue=fixtures.GenerationTests.enqueue

    def execute_count(self,job,count):
        calls=[]
        def complete(messages,settings,cancel,**kw):
            properties=kw.get('schema',{}).get('properties',{})
            calls.append((messages,kw.get('schema')))
            if 'slides' in properties:
                return json.dumps({'title':'Lezione','visual_direction':'Tipografia leggibile e variazioni coerenti.',
                    'slides':[{'title':f'Pagina {i+1}','purpose':f'Spiegazione del punto {i+1}'} for i in range(count)]}),'stop'
            if 'content' in properties:return editorial_response()
            if kw.get('schema'):return json.dumps({'nodes':[fixtures.node(text='Spiegazione')],'notes':'Nota','sources':[]}),'stop'
            return '<style>main{color:#123456}</style><main><h1>Spiegazione</h1></main>','stop'
        with patch.object(self.app.engine,'require_model',return_value=self.model),patch.object(self.app.engine,'prepare'),patch.object(self.app.engine,'start_llama'),patch.object(self.app.engine,'completion',side_effect=complete):
            self.app.execute_job(job,threading.Event())
        answer=self.app.store.messages(job['chat_id'])[-1]
        return answer,calls

    def test_automatic_count_is_resolved_once_and_persisted_with_request_draft(self):
        from h3chat.request_draft import load
        for engine in ('llm','deterministic'):
            with self.subTest(engine=engine):
                job=self.enqueue('Crea una presentazione dal documento, decidi tu quante slide servono',slides={'count':8,'engine':engine})
                self.assertEqual(json.loads(job['payload'])['settings']['_slides']['count'],'auto')
                answer,calls=self.execute_count(job,3)
                self.assertEqual(answer['status'],'done',answer['meta'].get('error'))
                plan=calls[0][1]['properties']['slides']
                self.assertEqual((plan['minItems'],plan['maxItems']),(1,100))
                self.assertIn('fonti disponibili',calls[0][0][-1]['content'])
                deck=json.loads(answer['meta']['artifact']['content'][len(PREFIX):-4])
                self.assertEqual((len(deck['pages']),deck['count_mode']),(3,'auto'))
                self.assertEqual(answer['meta']['slide_count'],{'mode':'auto','requested':'auto','resolved':3})
                self.assertEqual(answer['meta']['slides_count'],3)
                self.assertEqual(sum(bool(s and 'slides' in s['properties']) for _,s in calls),1)
                self.assertEqual(load(self.app,job['chat_id'],job['message_id'])['slides']['count'],'auto')

    def test_100_page_generation_and_explicit_prompt_overrides_automatic_setting(self):
        job=self.enqueue('Crea 100 slide',slides={'count':'auto','engine':'deterministic'})
        answer,calls=self.execute_count(job,100)
        self.assertEqual(answer['status'],'done',answer['meta'].get('error'))
        self.assertEqual(calls[0][1]['properties']['slides']['minItems'],100)
        self.assertEqual(calls[0][1]['properties']['slides']['maxItems'],100)
        deck=json.loads(answer['meta']['artifact']['content'][len(PREFIX):-4])
        self.assertEqual(len(deck['pages']),MAX_SLIDES)
        self.assertEqual(deck['pages'][-1]['status'],'ready')
        validate_content(answer['meta']['artifact']['content'],[])

    def test_invalid_outline_cannot_escape_automatic_or_fixed_limits(self):
        for prompt,body,returned in (('Crea una presentazione',{'count':'auto'},101),('Crea una presentazione',{'count':'auto'},0),('Crea 100 slide',{'count':'auto'},99)):
            with self.subTest(returned=returned):
                job=self.enqueue(prompt,slides=body)
                answer,calls=self.execute_count(job,returned)
                self.assertEqual(answer['status'],'failed')
                self.assertIn('Scaletta slide non valida',answer['meta']['error'])
                self.assertEqual(len(calls),1)


if __name__=='__main__':unittest.main()

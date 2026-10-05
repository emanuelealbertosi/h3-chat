import json
import threading
import unittest
from unittest.mock import patch
from tests import test_slides as fixtures
from h3chat.slides import PREFIX, options,validate_content,encode,edit_options

class HTMLTests(fixtures.GenerationTests):
    # Reuse fixture methods, not the declarative engine's test cases.
    def enqueue(self,prompt='Crea 2 slide con testi completi',**body):
        return super().enqueue(prompt,**(body|{'slides':{'engine':'llm','design':'playful'}}))

    def test_html_is_streamed_verbatim_and_no_page_schema_or_layout_nodes(self):
        job=self.enqueue();self.job=job;calls=[]
        def complete(messages,settings,cancel,**kw):
            calls.append((messages,kw.get('schema')))
            if kw.get('schema'):
                return json.dumps({'title':'Corso','slides':[{'title':'A','purpose':'Introduzione'},{'title':'B','purpose':'Esempio'}]}),'stop'
            html='<style>body{background:#153a51;color:white;font:32px Georgia}h1{font-size:72px}</style><main><h1>Libertà creativa</h1><p>Un paragrafo completo [R1]</p><svg viewBox="0 0 20 20"><circle cx="10" cy="10" r="8" fill="orange"/></svg></main>'
            kw['on_text'](html[:155])
            saved=json.loads(self.app.store.canvas_history.get(job['chat_id'])['content'][len(PREFIX):-4])
            self.assertTrue(any('Libertà' in p.get('html','') for p in saved['pages']))
            return html,'stop'
        with patch.object(self.app.engine,'require_model',return_value=self.model),patch.object(self.app.engine,'prepare'),patch.object(self.app.engine,'start_llama'),patch.object(self.app.engine,'completion',side_effect=complete):
            self.app.execute_job(job,threading.Event())
        answer=self.app.store.messages(job['chat_id'])[-1];self.assertEqual(answer['status'],'done',answer['meta'].get('error'))
        artifact=answer['meta']['artifact'];validate_content(artifact['content'],[])
        deck=json.loads(artifact['content'][len(PREFIX):-4]);self.assertEqual(deck['engine'],'llm')
        self.assertTrue(all('<svg' in p['html'] and p['nodes']==[] for p in deck['pages']))
        self.assertTrue(all(schema is None for _,schema in calls[1:]));self.assertIn('HTML e CSS ORIGINALI',calls[0][0][0]['content'])
        self.assertNotIn('Non creare codice HTML',calls[0][0][0]['content'])
        self.assertNotIn('<style>',answer['content'])

    def test_default_and_legacy_edit_engines(self):
        self.assertEqual(options('')['engine'],'llm')
        self.assertEqual(options('',{'engine':'deterministic'})['engine'],'deterministic')
        with self.assertRaises(ValueError):options('',{'engine':'unknown'})
        legacy=encode({'version':1,'format':'4:3','pages':[{'title':'A','nodes':[]}]})
        self.assertEqual(edit_options('Cambia titolo',legacy)['engine'],'deterministic')

    def test_html_manual_updates_are_validated(self):
        deck={'version':1,'engine':'llm','format':'16:9','pages':[{'title':'A','status':'ready','html':'<div style="font-size:55px">Edited</div>'}]}
        validate_content(encode(deck),[])
        for invalid in (None,'x'*80001,'no HTML'):
            deck['pages'][0]['html']=invalid
            with self.assertRaises(ValueError):validate_content(encode(deck),[])

# Inherited tests exercise the deterministic engine and should not be rerun
# with a different completion protocol in this class.
for name in list(vars(fixtures.GenerationTests)):
    if name.startswith('test_'):setattr(HTMLTests,name,None)

if __name__=='__main__':unittest.main()

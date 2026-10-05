import json
import unittest
from h3chat.slide_context import compact_history


class SlideContextTests(unittest.TestCase):
    def test_complete_vision_is_explicit_and_invalid_modes_are_rejected(self):
        from h3chat.slides import options
        self.assertEqual(options('Crea 4 slide',{'vision_scope':'all'})['vision_scope'],'all')
        self.assertEqual(options('Crea 4 slide, analizza tutte le immagini')['vision_scope'],'all')
        with self.assertRaises(ValueError):options('Crea 4 slide',{'vision_scope':'invalid'})

    def test_old_html_is_summarized_and_current_sources_are_preserved(self):
        html='<style>HUGE_PREVIOUS_HTML</style>'*3000
        content='```h3-slides\n'+json.dumps({'title':'Prima lezione','pages':[{'title':'Introduzione','purpose':'Spiegare il tema','html':html}]})+'\n```'
        artifact={'content':content,'media':[{'id':'figure'}]}
        history=[{'role':'user','seq':1,'content':'Usa uno stile colorato','media':[]},
                 {'role':'assistant','seq':2,'content':'Fatto\nArtefatto nel canvas:\n'+content,'media':artifact['media'],'meta':{'artifact':artifact}},
                 {'role':'user','seq':3,'content':'Crea 4 slide\n<fonti_progetto>[R1] Dati completi e verificati</fonti_progetto>','media':[]}]
        result=compact_history(history)
        self.assertNotIn('HUGE_PREVIOUS_HTML',json.dumps([m['content'] for m in result]))
        self.assertIn('Prima lezione',result[1]['content']);self.assertEqual(result[-1],history[-1])
        self.assertEqual(result[1]['media'],artifact['media']);self.assertIn('HUGE_PREVIOUS_HTML',history[1]['content'])
        self.assertEqual(compact_history(result),result)

    def test_current_canvas_sample_is_bounded_but_keeps_design(self):
        content='```h3-slides\n'+json.dumps({'title':'Da modificare','active':0,'pages':[{'title':'Pagina','html':'<style>background:blue</style>'+('content '*10000)}]})+'\n```'
        history=[{'role':'user','seq':-1,'content':'Canvas attuale da modificare se richiesto:\n'+content,'media':[]},
                 {'role':'user','seq':3,'content':'Cambia il titolo','media':[]}]
        result=compact_history(history)
        self.assertLess(len(result[0]['content']),7000);self.assertIn('background:blue',result[0]['content'])
        self.assertEqual(compact_history(result),result)

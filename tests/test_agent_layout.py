"""Opt-in real CPU renderer probe; never starts an inference model."""
import os
import threading
import time
import unittest
import test_visual_models as fixture

@unittest.skipUnless(os.environ.get('H3_AGENT_LAYOUT_TEST')=='1','Real offline browser probe is opt-in.')
class AgentLayoutTests(unittest.TestCase):
    setUp=fixture.VisualModelsTests.setUp
    def tearDown(self):
        self.app.close()
        for attempt in range(20):
            try:self.tmp.cleanup();return
            except PermissionError:
                if attempt==19:raise
                time.sleep(.15)

    def test_measures_text_beyond_slide_border(self):
        deck={'version':1,'engine':'llm','format':'16:9','title':'CPU probe','pages':[
            {'title':'Inside','status':'ready','html':'<style>body{font:36px Arial}h1{margin:30px}</style><h1>Dentro i bordi</h1>'},
            {'title':'Outside','status':'ready','html':'<style>body{font:36px Arial}p{position:absolute;left:1240px;top:30px;width:200px}</style><p>Testo fuori bordo</p>'}]}
        value=self.app.engine.tool_call('agent-layout-worker.py',{'data':str(self.app.data),'deck':deck,'media':[],
            'folder':str(self.app.data/'outputs'/'cpu-probe')},threading.Event(),lambda s:None,self.base/'layout.log',timeout=90)
        self.assertEqual(value['renderer'],'CPU offline');self.assertFalse(value['visual_review'])
        self.assertFalse(value['pages'][0]['issue']);self.assertTrue(value['pages'][1]['issue'])
        self.assertIn('Testo fuori bordo',str(value['pages'][1]['out_of_bounds']))

if __name__=='__main__':unittest.main()

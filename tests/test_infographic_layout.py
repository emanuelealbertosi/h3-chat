import copy,tempfile,threading,unittest
from pathlib import Path
from unittest.mock import Mock
from h3chat.infographic_layout import brief,ensure
from h3chat.downloads import Cancelled

class PortraitLayoutTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.app=Mock();self.app.data=Path(self.temp.name)
        self.html='<h1 data-motion="fade">Pagina verticale</h1>'
        self.deck={'format':'9:16','pages':[{'html':self.html},{'html':'Seconda'}],'active':1,'infographic':{'version':1,'durations':[10,12],'sfx':'none','transition':'cut','options':{'output':'video'}}}
        self.cancel=threading.Event();self.on_text=Mock();self.stage=Mock()
    def run_check(self):return ensure(self.app,{'id':'job'},self.deck,0,[],[],{'max_tokens':40000},self.cancel,self.html,self.on_text,self.stage,self.app.data/'log')
    def test_sparse_portrait_is_recomposed_by_llm_using_real_measurements(self):
        original=copy.deepcopy(self.deck);fixed='<main data-motion="fade"><h1>Nuova composizione verticale</h1></main>'
        self.app.engine.tool_call.side_effect=[{'pages':[{'issue':True,'largest_gap':950,'gap_ratio':.418}]},{'pages':[{'issue':False}]}]
        self.app.engine.completion.return_value=(fixed,'stop')
        self.assertEqual(self.run_check(),(fixed,None));self.assertEqual(self.deck,original)
        request=self.app.engine.tool_call.call_args_list[0].args[1]
        self.assertEqual(request['mode'],'layout');self.assertEqual(len(request['deck']['pages']),1);self.assertEqual(request['deck']['infographic']['durations'],[10])
        prompt=self.app.engine.completion.call_args.args[0][-1]['content'];self.assertIn('950 px',prompt);self.assertIn('VERTICALE',prompt);self.assertIn('tempi ed effetti',prompt)
    def test_balanced_scene_and_other_formats_need_no_llm_repair(self):
        self.app.engine.tool_call.return_value={'pages':[{'issue':False}]}
        self.assertEqual(self.run_check(),(self.html,None));self.app.engine.completion.assert_not_called()
        self.app.engine.tool_call.reset_mock()
        for key,value in (('format','16:9'),('layout','columns3'),('output','static')):
            if key=='format':self.deck['format']=value
            else:self.deck['format']='9:16';self.deck['infographic']['options'][key]=value
            self.assertEqual(self.run_check(),(self.html,None))
        self.app.engine.tool_call.assert_not_called()
    def test_still_sparse_result_has_warning_instead_of_deterministic_relayout(self):
        self.app.engine.tool_call.return_value={'pages':[{'issue':True,'largest_gap':950,'gap_ratio':.418}]};self.app.engine.completion.return_value=(self.html,'stop')
        html,warning=self.run_check();self.assertEqual(html,self.html);self.assertIn('spazio vuoto',warning);self.assertEqual(self.app.engine.completion.call_count,1)
    def test_truncated_or_cancelled_repair_is_not_accepted(self):
        self.app.engine.tool_call.return_value={'pages':[{'issue':True}]};self.app.engine.completion.return_value=(self.html,'length')
        with self.assertRaisesRegex(ValueError,'incompleta'):self.run_check()
        self.cancel.set()
        with self.assertRaises(Cancelled):self.run_check()
    def test_explicit_portrait_dimensions_and_guidance(self):
        text=brief('9:16');self.assertIn('1280 × 2275.56',text);self.assertIn('TUTTE le scene',text);self.assertIn('metà superiore',text)
    def test_optional_measurement_failure_preserves_generated_html_but_cancel_stops(self):
        self.app.engine.tool_call.side_effect=RuntimeError('Renderer non disponibile')
        with self.assertLogs('h3chat.infographic_layout',level='WARNING'):
            html,warning=self.run_check()
        self.assertEqual(html,self.html);self.assertIn('non disponibile',warning);self.app.engine.completion.assert_not_called()
        self.app.engine.tool_call.side_effect=Cancelled()
        with self.assertRaises(Cancelled):self.run_check()

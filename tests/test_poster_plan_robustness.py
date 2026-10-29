"""Public regressions use synthetic copy; only failing geometry patterns are retained."""
import copy,json,tempfile,threading,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from h3chat import poster_visual as visual,poster_overlay as overlay
from h3chat.posters import options
from h3chat.slides import FORMATS
from test_poster_overlay import prepared,fragments,PROOF
from test_poster_visual import layout
ROOT=Path(__file__).resolve().parents[1]

class PosterRobustnessTests(unittest.TestCase):
    def test_exact_source_intervals_allow_title_before_eyebrow_and_grouping_across_title(self):
        source='Istituto Delta\nLABORATORIO APERTO\nScopri il corso\nTre incontri di prova\nIstituto Delta'
        zones=[{'id':'title','text':'LABORATORIO APERTO'},{'id':'left','text':'Istituto Delta\nScopri il corso\nTre incontri di prova'},{'id':'footer','text':'Istituto Delta'}]
        self.assertTrue(visual.verify_copy(source,zones))
        zones[1]['text']='Istituto Delta\nScopri corso il\nTre incontri di prova'
        with self.assertRaisesRegex(ValueError,'riordinata|riscritta'):visual.verify_copy(source,zones)
    def test_interval_matching_rejects_duplicate_paragraph_even_if_word_bag_matches(self):
        source='uno due tre\nuno tre due'
        with self.assertRaises(ValueError):visual.verify_copy(source,[{'id':'a','text':'uno due tre'},{'id':'b','text':'uno due tre'}])
        with self.assertRaises(ValueError):visual.verify_copy(source,[{'id':'a','text':'uno due\ntre uno tre due extra'}])
    def test_markdown_is_formatting_but_literal_code_and_factual_numbers_survive(self):
        source='# Laboratorio Delta\n**Tre incontri · 6 ore**\n## Programma\n- Prima attività\n- Seconda attività\n---\nUsa `#tag` e `a_b`.'
        zones=[{'id':'title','text':'Laboratorio Delta'},{'id':'body','text':'Tre incontri · 6 ore\nProgramma\n• Prima attività\nSeconda attività\nUsa #tag e a_b.'}]
        self.assertTrue(visual.verify_copy(source,zones));self.assertNotIn('**',visual.plain_copy(source));self.assertIn('#tag',visual.plain_copy(source))
        zones[1]['text']=zones[1]['text'].replace('6 ore','9 ore')
        with self.assertRaises(ValueError):visual.verify_copy(source,zones)
    def test_dense_program_pattern_can_fit_at_twenty_without_lowering_below_eighteen(self):
        value=layout();value['coordinate_space']='pixels';value['objects'][0]['bbox']=[700,120,1240,760]
        value['zones'][0].update(renderer='html',text='PROVA TECNICA',bbox=[70,110,660,300],font_size=120)
        paragraph='Esaminiamo materiali, strumenti e procedure attraverso esempi concreti. Gli incontri prevedono attività pratiche, osservazioni guidate e momenti di confronto. I partecipanti raccolgono risultati, discutono le scelte e preparano una breve dimostrazione. '
        body='Programma\n\n1 — Giorno 1 · Materiali\n\n'+paragraph+'\n\n2 — Giorno 2 · Strumenti\n\n'+paragraph+'\n\n3 — Giorno 3 · Procedure\n\n'+paragraph
        value['zones'][1].update(role='program',renderer='html',text=body,bbox=[660,1330,1210,2120],font_size=23)
        w,h=FORMATS['9:16'];opts=options(value={'format':'9:16'})
        fitted=visual.validate(value,w,h,5,ROOT,opts);zone=fitted['zones'][1]
        self.assertGreaterEqual(zone['font_size'],18);self.assertLess(zone['font_size'],22);self.assertEqual(zone['text'],body)
        with self.assertRaisesRegex(ValueError,'troppo lungo'):visual.validate(value,w,h,5,ROOT,opts|{'typography_engine':'preset'})
    def test_safe_numeric_and_family_normalization_is_recorded_but_invalid_values_stay_rejected(self):
        value=layout();value['zones'][0].update(tracking=8,font_family='Bebas Neue',font_size=110.0,italic='false',color='#fff')
        normalized=visual.normalize_typography(value);zone=normalized['zones'][0]
        self.assertEqual((zone['tracking'],zone['font_family'],zone['font_size'],zone['italic'],zone['color']),(6,'BebasNeue',110,False,'#ffffff'));self.assertIs(type(zone['font_size']),int);self.assertEqual(value['zones'][0]['tracking'],8);self.assertGreater(len(normalized['typography_adjustments']),3)
        bad=visual.normalize_typography(value);bad['zones'][0]['font_family']='Unknown remote font'
        with self.assertRaises(ValueError):visual.validate(bad,*FORMATS['9:16'],5,ROOT)
        bad=visual.normalize_typography(value);bad['zones'][0]['tracking']=float('nan')
        with self.assertRaises(ValueError):visual.validate(bad,*FORMATS['9:16'],5,ROOT)
    def test_colliding_art_requires_real_geometry_correction_not_identical_retry(self):
        bad=layout();bad['zones'][0].update(renderer='html');bad['objects'][0]['bbox']=[650,60,950,300]
        fixed=copy.deepcopy(bad);fixed['objects'][0]['bbox']=[650,250,950,550];calls=[]
        def complete(messages,*a,**kw):calls.append(copy.deepcopy(messages));return json.dumps(bad if len(calls)==1 else fixed),'stop'
        opts=options()|{'_settings':{'max_tokens':8000,'context':32768}};row={'copy':'\n'.join(z['text'] for z in bad['zones']),'visual_plan':'Fictional event'}
        with tempfile.TemporaryDirectory() as folder:result=visual.plan(SimpleNamespace(completion=complete),[{'role':'system','content':'Poster'}],row,opts,*FORMATS['9:16'],ROOT,threading.Event(),lambda _:None,Path(folder),0)
        self.assertEqual(len(calls),2);self.assertIn('CONFLITTI DA CORREGGERE',calls[1][-1]['content']);self.assertEqual(result['objects'][0]['bbox'],fixed['objects'][0]['bbox'])
        with tempfile.TemporaryDirectory() as folder,self.assertRaisesRegex(ValueError,'interseca'):visual.plan(SimpleNamespace(completion=lambda *a,**kw:(json.dumps(bad),'stop')),[{'role':'system','content':'Poster'}],row,opts,*FORMATS['9:16'],ROOT,threading.Event(),lambda _:None,Path(folder),0)
    def test_cpu_overflow_only_grows_into_empty_space_then_requires_successful_remeasurement(self):
        value=prepared();before=copy.deepcopy(value);parts=fragments(value);app=SimpleNamespace(root=ROOT);report={'poster_overflow':[{'id':'title','reason':'testo tagliato dal riquadro'}]};overflow=overlay.TypographyOverflow(report)
        with patch.object(overlay,'measure',side_effect=[overflow,PROOF]) as measured:
            result=overlay.measure_before_background(app,value,parts,'A3',*FORMATS['A3'],ROOT/'work'/'probe',threading.Event(),lambda _:None,ROOT/'work'/'probe.log',options())
        self.assertEqual(measured.call_count,2);self.assertIn('geometry_adjustments',result);self.assertNotEqual(value['zones'][0]['bbox'],before['zones'][0]['bbox']);self.assertEqual(value['objects'],before['objects']);self.assertEqual([z['text'] for z in value['zones']],[z['text'] for z in before['zones']]);visual.validate(value,*FORMATS['A3'],5,ROOT,options())
        value=copy.deepcopy(before)
        with patch.object(overlay,'measure',side_effect=[overflow,overflow]),self.assertRaises(overlay.TypographyOverflow):overlay.measure_before_background(app,value,parts,'A3',*FORMATS['A3'],ROOT/'work'/'probe',threading.Event(),lambda _:None,ROOT/'work'/'probe.log',options())
        self.assertEqual(value,before)

if __name__=='__main__':unittest.main()

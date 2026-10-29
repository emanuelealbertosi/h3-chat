"""Synthetic copy with captured geometry: a 580px art group in a 560px hero gap."""
import copy,json,math,tempfile,threading,unittest
from pathlib import Path
from types import SimpleNamespace
from h3chat import poster_visual as visual
from h3chat.posters import options
from h3chat.slides import FORMATS
from test_poster_visual import layout,referenced

ROOT=Path(__file__).resolve().parents[1]

def captured_geometry():
    template=layout()['zones'][1]
    def zone(ident,role,text,box,size):return template|{'id':ident,'role':role,'renderer':'html','text':text,'bbox':box,'font_size':size,'weight':600 if role=='title' else 400}
    return {'coordinate_space':'pixels','art_caption':'A colourful exhibit figure and its platform on a continuous dark background, with quiet text areas.',
        'objects':[{'caption':'A friendly exhibit figure','bbox':[420,300,900,780]},{'caption':'A matching platform below the figure','bbox':[380,700,940,880]}],
        'zones':[zone('title','title','OFFICINA DELLE IDEE',[80,90,1200,290],110),zone('eyebrow','facts','Un laboratorio aperto',[80,290,1200,340],24),zone('facts','facts','Tre incontri pratici',[80,900,1200,1070],30),zone('body','body','Materiali\nEsperimenti e osservazioni condivise.',[80,1100,620,2020],28),zone('program','program','Programma\nTre attività guidate con esempi concreti.',[660,1100,1200,2020],26)]}

class PosterObjectGroupTests(unittest.TestCase):
    def test_group_is_fitted_uniformly_without_changing_text_or_relative_placement(self):
        value=captured_geometry();before=copy.deepcopy(value);w,h=FORMATS['9:16'];result=visual.fit_object_group(value,w,h);record=result['object_geometry_adjustments'][-1]
        self.assertEqual(record['scale'],.9);self.assertEqual(result['zones'],value['zones']);self.assertEqual(value,before)
        self.assertEqual([o['caption'] for o in result['objects']],[o['caption'] for o in value['objects']])
        scale=record['scale'];dx,dy=record['translation_after_center_scale'];a=record['group_before'];cx=(a[0]+a[2])/2;cy=(a[1]+a[3])/2
        for old,new in zip(value['objects'],result['objects']):
            for old_n,new_n,center,delta in zip(old['bbox'],new['bbox'],(cx,cy,cx,cy),(dx,dy,dx,dy)):self.assertAlmostEqual(new_n,center+(old_n-center)*scale+delta,places=5)
            self.assertAlmostEqual((old['bbox'][2]-old['bbox'][0])/(old['bbox'][3]-old['bbox'][1]),(new['bbox'][2]-new['bbox'][0])/(new['bbox'][3]-new['bbox'][1]))
        self.assertGreaterEqual(record['group_after'][1],348);self.assertLessEqual(record['group_after'][3],892)
        fitted=visual.validate(result,w,h,4,ROOT,options(value={'format':'9:16','safe_margin':4}));self.assertEqual([z['text'] for z in fitted['zones']],[z['text'] for z in value['zones']])
    def test_translation_is_preferred_over_any_scaling(self):
        value=captured_geometry();value['objects'][0]['bbox']=[420,300,900,680];value['objects'][1]['bbox']=[380,600,940,760]
        result=visual.fit_object_group(value,*FORMATS['9:16']);record=result['object_geometry_adjustments'][-1]
        self.assertEqual(record['scale'],1);self.assertEqual(record['translation_after_center_scale'],[0,48]);self.assertEqual(result['zones'],value['zones'])
    def test_impossible_group_is_rejected_instead_of_shrinking_more_or_covering_copy(self):
        value=captured_geometry();value['zones']=[value['zones'][0]|{'role':'body','text':'Testo che occupa tutta la pagina.','bbox':[0,0,1280,FORMATS['9:16'][1]],'font_size':22}]
        with self.assertRaisesRegex(ValueError,'20%'):visual.fit_object_group(value,*FORMATS['9:16'])
    def test_reduction_stops_at_twenty_percent_even_when_twenty_five_would_fit(self):
        value=captured_geometry();value['zones'][2]['bbox'][1]=820
        result=visual.fit_object_group(value,*FORMATS['9:16']);self.assertEqual(result['object_geometry_adjustments'][-1]['scale'],.8)
        value['zones'][2]['bbox'][1]=805
        with self.assertRaisesRegex(ValueError,'20%'):visual.fit_object_group(value,*FORMATS['9:16'])
    def test_legacy_validation_and_already_valid_geometry_are_unchanged(self):
        value=captured_geometry()
        with self.assertRaisesRegex(ValueError,'interseca'):visual.validate(value,*FORMATS['9:16'],4,ROOT,options(value={'format':'9:16','safe_margin':4}))
        self.assertNotIn('object_geometry_adjustments',value)
        legacy=layout();self.assertIs(visual.fit_object_group(legacy,*FORMATS['9:16']),legacy)
        valid=captured_geometry();valid['objects'][0]['bbox']=[420,360,900,700];valid['objects'][1]['bbox']=[380,700,940,880]
        self.assertIs(visual.fit_object_group(valid,*FORMATS['9:16']),valid)
    def test_unknown_units_or_invalid_boxes_are_not_guessed(self):
        for modify in (lambda v:v.update(coordinate_space='unknown'),lambda v:v['objects'][0].update(bbox=[0,0,float('nan'),900]),lambda v:v['objects'][0].update(bbox=[900,300,420,780])):
            value=captured_geometry();modify(value);self.assertIs(visual.fit_object_group(value,*FORMATS['9:16']),value)
            with self.assertRaises(ValueError):visual.validate(value,*FORMATS['9:16'],4,ROOT)
    def test_new_plan_fits_the_group_before_moss_then_runs_ordinary_validation(self):
        value=captured_geometry();request=referenced(value);calls=[]
        def complete(*args,**kwargs):calls.append(1);return json.dumps(request),'stop'
        opts=options(value={'format':'9:16','safe_margin':4})|{'_settings':{'context':32768,'max_tokens':8000}};row={'copy':'\n'.join(z['text'] for z in value['zones']),'visual_plan':'A fictional laboratory exhibition'}
        with tempfile.TemporaryDirectory() as folder:result=visual.plan(SimpleNamespace(completion=complete),[{'role':'system','content':'Poster'}],row,opts,*FORMATS['9:16'],ROOT,threading.Event(),lambda _:None,Path(folder),0)
        self.assertEqual(len(calls),1);self.assertEqual(result['object_geometry_adjustments'][-1]['scale'],.9);self.assertEqual([z['text'] for z in result['zones']],[z['text'] for z in value['zones']]);self.assertEqual(result['coordinate_space'],'normalized')

if __name__=='__main__':unittest.main()

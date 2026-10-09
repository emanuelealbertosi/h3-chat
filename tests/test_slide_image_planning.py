"""Bounded illustration planning must finish before a single image-model batch."""
import copy,json,threading,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
from h3chat.downloads import Cancelled
from h3chat.slide_generation_images import create,plan_images
from h3chat.store import DEFAULTS

class ImagePlanningTests(unittest.TestCase):
    def setUp(self):
        self.image={'id':'image','name':'Image fixture','architecture':'anima'}
        self.settings=DEFAULTS|{'context':80000,'max_tokens':40000,'prompt_max_tokens':2200,
            '_slides':{'image_model':'image','design':'playful'}}
        self.outline={'title':'Binary multiplication','visual_direction':'Consistent colorful illustrations',
            'slides':[{'title':f'Page {i}','purpose':'Illustrate a concept'} for i in range(1,16)]}
        self.engine=Mock();self.engine.require_model.return_value=self.image
        self.history=[{'role':'user','content':'Una immagine per ogni slide, stile giocoso'}]
        self.cancel=threading.Event();self.stage=Mock()
    def numbers(self,kwargs):
        return kwargs['schema']['properties']['images']['items']['properties']['slide']['enum']
    def response(self,numbers):
        return json.dumps({'images':[{'slide':n,'prompt':f'colorful shapes, binary illustration {n}',
            'description':f'Figura {n}'} for n in numbers]}),'stop'
    def run_plan(self):
        return plan_images(self.engine,self.outline,self.history,self.settings,self.image,self.cancel,self.stage)
    def test_fifteen_pages_with_2200_tokens_finish_before_one_model_switch_and_batch(self):
        events=[];before=copy.deepcopy(self.settings)
        def complete(messages,tuning,cancel,**kwargs):
            numbers=self.numbers(kwargs);events.append(('plan',numbers))
            self.assertEqual(tuning['think_level'],'off');self.assertLessEqual(tuning['max_tokens'],2200)
            self.assertIn('Binary multiplication',messages[-1]['content'])
            return self.response(numbers)
        self.engine.completion.side_effect=complete
        def generate(model,tuning,prompt,refs,ident,cancel,stage):
            events.append(('image',ident));self.assertEqual(self.engine.completion.call_count,3)
            self.assertEqual(self.engine.stop.call_count,1);self.engine.start_llama.assert_not_called()
            return {'id':ident,'mime':'image/png','path':'synthetic.png'}
        self.engine.generate.side_effect=generate;meta={}
        assets,captions=create(SimpleNamespace(engine=self.engine,store=Mock()),{'payload':'{}'},self.outline,
            self.history,self.settings,{'name':'LLM'},self.cancel,self.stage,Path('synthetic.log'),meta)
        self.assertEqual([x[1] for x in events[:3]],[list(range(1,7)),list(range(7,13)),list(range(13,16))])
        self.assertEqual(len(assets),15);self.assertEqual(len(captions),15)
        self.assertEqual([p['slide'] for p in meta['slide_image_plan']],list(range(1,16)))
        self.assertEqual(self.engine.stop.call_count,2);self.engine.start_llama.assert_called_once()
        self.assertEqual(self.settings,before)
    def test_truncated_groups_are_split_without_reusing_partial_json_or_duplicate_pages(self):
        self.outline['slides']=self.outline['slides'][:6]
        def complete(messages,tuning,cancel,**kwargs):
            numbers=self.numbers(kwargs)
            if len(numbers)>3:return '{"images":[{"slide":1','length'
            return self.response(numbers)
        self.engine.completion.side_effect=complete
        self.assertEqual([p['slide'] for p in self.run_plan()],list(range(1,7)))
        self.assertEqual(self.engine.completion.call_count,3)
        self.engine.generate.assert_not_called();self.engine.stop.assert_not_called()
    def test_empty_optional_groups_do_not_drop_other_planned_images(self):
        def complete(messages,tuning,cancel,**kwargs):
            numbers=self.numbers(kwargs)
            return self.response([numbers[-1]] if numbers[0]==7 else [])
        self.engine.completion.side_effect=complete
        self.assertEqual([p['slide'] for p in self.run_plan()],[12])
    def test_incomplete_single_page_is_bounded_and_error_names_actual_budget(self):
        self.outline['slides']=self.outline['slides'][:1];self.settings['prompt_max_tokens']=256
        self.engine.completion.return_value=('{"images":[','length')
        with self.assertRaisesRegex(ValueError,'pagina 1.*due tentativi.*256 token'):self.run_plan()
        self.assertEqual(self.engine.completion.call_count,2)
        self.engine.stop.assert_not_called();self.engine.generate.assert_not_called()
    def test_invalid_global_page_numbers_fail_before_model_switch(self):
        self.engine.completion.return_value=self.response([7])
        with self.assertRaisesRegex(ValueError,'slide non valida'):self.run_plan()
        self.assertEqual(self.engine.completion.call_count,1);self.engine.stop.assert_not_called()
    def test_provider_failure_is_not_retried_and_cancellation_stops_next_group(self):
        self.engine.completion.side_effect=RuntimeError('Provider 401')
        with self.assertRaisesRegex(RuntimeError,'401'):self.run_plan()
        self.assertEqual(self.engine.completion.call_count,1)
        self.engine.completion.reset_mock()
        def complete(messages,tuning,cancel,**kwargs):
            cancel.set();return self.response(self.numbers(kwargs))
        self.engine.completion.side_effect=complete
        with self.assertRaises(Cancelled):self.run_plan()
        self.assertEqual(self.engine.completion.call_count,1);self.engine.stop.assert_not_called()

"""Capacity, all-plan validation and persisted motion without real inference."""
import json,threading,unittest
from unittest.mock import patch
import test_visual_models as fixture
from h3chat.image_batch import plan,MAX_IMAGES
from h3chat.image_collections import generation_options
from h3chat.slides import options,edit_options,encode
from h3chat.presentation_preferences import config
from h3chat.slide_motion import brief

class CapacityMotionTests(unittest.TestCase):
    setUp=fixture.VisualModelsTests.setUp
    tearDown=fixture.VisualModelsTests.tearDown

    def test_fifty_images_planned_with_one_model_load_and_preserved_order(self):
        self.assertEqual(MAX_IMAGES,50)
        self.assertEqual(generation_options({'count':50})['count'],50)
        with self.assertRaises(ValueError):generation_options({'count':51})
        settings=self.settings|{'context':32768,'prompt_max_tokens':8192}
        calls=[]
        def completion(messages,tuning,cancel,**kw):
            data=json.loads(messages[-1]['content']);interval=data['batch_range'];calls.append(interval)
            return json.dumps({'images':[{'prompt':f'Landscape {i}','model_id':self.qwen['id'],'model_choice':'','references':[],
                'parameters':{},'loras':[],'lora_mode':'auto'} for i in range(interval['first'],interval['last']+1)]}),'stop'
        with patch.object(self.app.engine,'start_llama') as load,patch.object(self.app.engine,'completion',side_effect=completion),patch.object(self.app.engine,'generate') as generate:
            result,meta=plan(self.app,{'prompt':'Crea 50 immagini','media':[]},[],settings,threading.Event(),lambda s:None,self.base/'plan.log')
        self.assertEqual(len(result),50);self.assertEqual(meta['planning_calls'],5);load.assert_called_once();generate.assert_not_called()
        self.assertEqual([x['prompt'] for x in result],[f'Landscape {i}' for i in range(1,51)])
        self.assertEqual(calls[-1],{'first':49,'last':50,'total':50})

    def test_motion_prompt_priority_presets_and_edit(self):
        self.assertEqual(options('Crea slide animate',{'motion':'static'})['motion'],'animated')
        chosen=options('Crea slide senza animazioni',{'motion':'animated'})
        self.assertEqual(chosen['motion'],'static')
        self.assertEqual(options('',{'motion':'animated','engine':'deterministic'})['engine'],'llm')
        self.assertEqual(config('slides',{'motion':'animated'})['motion'],'animated')
        deck={'version':1,'format':'16:9','motion':'animated','pages':[{}]}
        self.assertEqual(edit_options('Cambia i colori',encode(deck))['motion'],'animated')
        self.assertIn('@keyframes',brief('animated'));self.assertIn('visibili subito',brief('static'))
        with self.assertRaises(ValueError):options('',{'motion':'nope'})

if __name__=='__main__':unittest.main()

"""Exercise the Assistant and the same batch path used by Agent, without GPU."""
import json
import threading
import unittest
from unittest.mock import patch
import test_visual_models as fixture
from h3chat.image_batch import validate_plan,schema
from h3chat.moss_layout import brief,planned,disabled

DRAFT={'summary':'A pear beside an apple.','items':[
    {'label':'object','caption':'Pear','text':'','bbox':[50,100,400,900]},
    {'label':'object','caption':'Apple','text':'','bbox':[600,100,950,900]}]}


class MossAutoLayoutTests(unittest.TestCase):
    setUp=fixture.VisualModelsTests.setUp
    tearDown=fixture.VisualModelsTests.tearDown

    def moss(self):
        return self.app.external_model({'profile':'moss','files':self.qwen['external_config']['files']})

    def test_unmarked_composition_uses_one_assistant_call_and_actual_dimensions(self):
        model=self.moss();settings=self.settings|{'image_overrides':{model['id']:{'width':1500,'height':1000}}}
        with patch.object(self.app.engine,'start_llama') as load,patch.object(self.app.engine,'completion',return_value=(json.dumps(DRAFT),'stop')) as completion:
            result,info=self.app.engine.refine_image_prompt([],'Una pera accanto a una mela',[],settings,threading.Event(),self.base/'llm.log',lambda _:None,image_model=model)
        self.assertEqual(json.loads(result)['items'][0]['bbox'],[-400,-675,400,-150])
        self.assertEqual(info['prompt_format'],'layout');self.assertEqual(completion.call_count,1);self.assertEqual(load.call_count,1)
        self.assertIn('Decide automatically',completion.call_args.args[0][0]['content'])
        self.assertIn('1500 pixels wide',completion.call_args.args[0][0]['content'])

    def test_simple_prose_optout_and_explicit_json_priority(self):
        model=self.moss()
        with patch.object(self.app.engine,'start_llama'),patch.object(self.app.engine,'completion',return_value=(json.dumps({'summary':'A sunset landscape','items':[]}),'stop')):
            result,info=self.app.engine.refine_image_prompt([],'Un paesaggio',[],self.settings,threading.Event(),self.base/'llm.log',lambda _:None,image_model=model)
        self.assertEqual(result,'A sunset landscape');self.assertEqual(info['prompt_format'],'prose')
        self.assertTrue(disabled('composizione libera, senza box'))
        authored=planned(DRAFT,1024,1024)
        with patch.object(self.app.engine,'start_llama') as load:
            result,_=self.app.engine.refine_image_prompt([],authored,[],self.settings,threading.Event(),self.base/'llm.log',lambda _:None,image_model=model)
        self.assertEqual(result,authored);load.assert_not_called()
        self.assertEqual(brief(1024,1024,automatic=True)[1]['properties']['items']['minItems'],0)
        self.assertEqual(brief(1024,1024)[1]['properties']['items']['minItems'],1)

    def test_batch_compiles_boxes_for_each_actual_aspect_without_extra_inference(self):
        model=self.moss();settings=self.settings|{'create_model':model['id']}
        items=[{'prompt':'A pear beside an apple','model_id':model['id'],'references':[],
            'parameters':{'aspect':ratio,'seed':42},'layout':DRAFT} for ratio in ('16:9','9:16')]
        with patch.object(self.app.engine,'completion') as complete:
            tasks=validate_plan(self.app,{'images':items},[],settings,2,source_prompt='Crea 2 immagini, una 16:9 e una 9:16, seed 42')
        complete.assert_not_called()
        for task in tasks:
            width,height=task['parameters']['width'],task['parameters']['height']
            self.assertEqual(json.loads(task['prompt']),json.loads(planned(DRAFT,width,height)))
            self.assertEqual(task['parameters']['seed'],42)
        self.assertNotEqual(json.loads(tasks[0]['prompt'])['items'][0]['bbox'],json.loads(tasks[1]['prompt'])['items'][0]['bbox'])
        self.assertIn('layout',schema([model['id']])['properties']['images']['items']['properties'])

    def test_complete_batch_executes_structured_prompt_with_one_plan(self):
        from test_image_batch import PNG
        model=self.moss();chat=self.app.store.create_chat()['id']
        ticket=self.app.send(chat,{'prompt':'Crea 2 immagini, pera accanto alla mela, 16:9, seed 42',
            'image_model':model['id'],'assistant':True})
        job=self.app.store.one('SELECT * FROM jobs WHERE id=?',(ticket['job_id'],))
        plan={'images':[{'prompt':'Pear beside apple','model_id':model['id'],'model_choice':'',
            'references':[],'parameters':{'aspect':'16:9','seed':42},'layout':DRAFT,'loras':[],'lora_mode':'auto'} for _ in range(2)]}
        def generate(model,settings,prompt,refs,ident,*args):
            self.assertEqual(json.loads(prompt)['bbox_format'],'yxyx')
            self.assertEqual(settings['_image_options']['seed'],42)
            folder=self.app.data/'outputs'/ident;folder.mkdir(parents=True)
            (folder/'image.png').write_bytes(PNG)
            return {'id':ident,'name':'image.png','mime':'image/png','path':f'outputs/{ident}/image.png'}
        with patch.object(self.app.engine,'start_llama'),patch.object(self.app.engine,'completion',return_value=(json.dumps(plan),'stop')) as complete,patch.object(self.app.engine,'generate',side_effect=generate) as inference:
            self.app.execute_job(job,threading.Event())
        answer=self.app.store.one('SELECT status,media,meta FROM messages WHERE id=?',(job['message_id'],))
        self.assertEqual(answer['status'],'done',answer['meta'])
        self.assertEqual((complete.call_count,inference.call_count),(1,2))
        self.assertEqual(json.loads(json.loads(answer['media'])[0]['generation']['prompt'])['bbox_format'],'yxyx')

    def test_authored_boxes_survive_agent_batch_rewrite(self):
        model=self.moss();authored=planned(DRAFT,1000,700)
        value={'images':[{'prompt':'An invented replacement','model_id':model['id'],'references':[],
            'parameters':{},'layout':{'summary':'Wrong','items':[]}}]}
        task=validate_plan(self.app,value,[],self.settings,1,source_prompt=authored)[0]
        self.assertEqual(task['prompt'],authored)

    def test_batch_does_not_send_moss_json_to_other_models_or_accept_invalid_boxes(self):
        value={'images':[{'prompt':'A scene','model_id':self.qwen['id'],'references':[],'parameters':{},'layout':DRAFT}]}
        with self.assertRaisesRegex(ValueError,'solo per MOSS'):validate_plan(self.app,value,[],self.settings,1)
        value['images'][0]['model_id']=self.moss()['id']
        value['images'][0]['layout']={'summary':'Scene','items':[{'label':'object','caption':'Pear','bbox':[600,0,400,100]}]}
        with self.assertRaises(ValueError):validate_plan(self.app,value,[],self.settings,1)


if __name__=='__main__':unittest.main()

import base64
import json
import threading
import unittest
from unittest.mock import patch
import test_visual_models as fixture
from h3chat.downloads import Cancelled
from h3chat.image_batch import requested, validate_plan, model_choice

PNG=base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aOKsAAAAASUVORK5CYII=')


class ImageBatchTests(unittest.TestCase):
    setUp=fixture.VisualModelsTests.setUp
    tearDown=fixture.VisualModelsTests.tearDown

    def image(self,color):
        # These tests inspect reference ownership/order, not pixel generation.
        return self.app.upload({'name':color+'.png','data':base64.b64encode(PNG).decode()})

    def test_detection_preserves_discussion_and_negation(self):
        for prompt in ('Creami 4 immagini, due 16:9 e due 9:16','Vorrei generare due immagini','Generate 3 images'):
            self.assertTrue(requested(prompt),prompt)
        for prompt in ('Non creare 4 immagini','Come genero 4 immagini?','Spiegami queste due immagini','Crea una foto'):
            self.assertFalse(requested(prompt),prompt)

    def test_one_plan_mixed_models_reference_isolation_order_and_partial_persistence(self):
        refs=[self.image('red'),self.image('blue')]
        moss=self.app.external_model({'profile':'moss','name':'MOSS batch test','files':self.qwen['external_config']['files']})
        plan={'images':[
            {'prompt':'A red lighthouse','model_id':self.qwen['id'],'references':[1],'parameters':{'aspect':'16:9','seed':42}},
            {'prompt':'A green lighthouse','model_id':moss['id'],'references':[],'parameters':{'aspect':'9:16','megapixels':1,'seed':-1}},
            {'prompt':'A blue lighthouse','model_id':self.qwen['id'],'references':[2],'parameters':{'aspect':'9:16','seed':42}},
            {'prompt':'A yellow lighthouse','model_id':moss['id'],'references':[],'parameters':{'aspect':'16:9','seed':-1}}]}
        for item in plan['images']:
            item.update(model_choice=self.qwen['name'] if item['model_id']==self.qwen['id'] else moss['name'],loras=[],lora_mode='auto')
        chat=self.app.store.create_chat()['id']
        ticket=self.app.send(chat,{'prompt':'Creami 4 immagini, due 16:9 e due 9:16, usa '+self.qwen['name']+' e '+moss['name']+'. La prima e la terza: seed 42. La seconda e la quarta: seed casuale.','media':[{'id':r['id']} for r in refs],'assistant':True})
        job=self.app.store.one('SELECT * FROM jobs WHERE id=?',(ticket['job_id'],));calls=[];observed=[]
        def generate(model,settings,prompt,references,output_id,cancel,stage):
            calls.append((model['id'],settings['_image_options'],references,output_id))
            previous=self.app.store.one('SELECT media FROM messages WHERE id=?',(job['message_id'],))
            observed.append(len(json.loads(previous['media'])))
            folder=self.app.data/'outputs'/output_id;folder.mkdir(parents=True)
            (folder/'image.png').write_bytes(PNG)
            return {'id':output_id,'name':'image.png','path':f'outputs/{output_id}/image.png','mime':'image/png','generation':{'seed':settings['_image_options']['seed']}}
        before=self.app.store.settings()
        with patch.object(self.app.engine,'start_llama') as load,patch.object(self.app.engine,'completion',return_value=(json.dumps(plan),'stop')) as completion,patch.object(self.app.engine,'generate',side_effect=generate),patch.object(self.app.engine,'refine_image_prompt') as refine:
            self.app.execute_job(job,threading.Event())
        answer=self.app.store.one('SELECT * FROM messages WHERE id=?',(job['message_id'],))
        self.assertEqual(answer['status'],'done',answer['meta']);self.assertEqual(load.call_count,1);self.assertEqual(completion.call_count,1);refine.assert_not_called()
        self.assertEqual([c[0] for c in calls],[self.qwen['id'],self.qwen['id'],moss['id'],moss['id']])
        self.assertEqual([[r['id'] for r in c[2]] for c in calls],[[refs[0]['id']],[refs[1]['id']],[],[]])
        self.assertEqual(observed,[0,1,2,3]);self.assertEqual(len({c[3] for c in calls}),4)
        self.assertEqual(calls[0][1]['seed'],calls[1][1]['seed']);self.assertNotEqual(calls[2][1]['seed'],calls[3][1]['seed'])
        media=json.loads(answer['media']);self.assertEqual([m['batch_index'] for m in media],[1,2,3,4]);self.assertEqual(media[1]['generation']['aspect'],'9:16')
        self.assertEqual(len(self.app.store.all('SELECT * FROM messages WHERE chat_id=? AND role=\'assistant\'',(chat,))),1)
        self.assertEqual(len(self.app.store.canvas_history.get(chat)['media']),4);self.assertEqual(before,self.app.store.settings())

    def test_invalid_later_task_fails_before_any_generation(self):
        value={'images':[{'prompt':'Lighthouse','model_id':self.qwen['id'],'references':[],'parameters':{}},
                         {'prompt':'Mountain','model_id':self.qwen['id'],'references':[2],'parameters':{}}]}
        with self.assertRaisesRegex(ValueError,'allegato'):
            validate_plan(self.app,value,[],self.settings,2)

    def test_unspecified_model_and_settings_use_captured_chat_defaults(self):
        moss=self.app.external_model({'profile':'moss','name':'MOSS defaults test','files':self.qwen['external_config']['files']})
        chat=self.app.store.create_chat()['id']
        saved={'steps':32,'cfg':2.5,'sampler':'heun','scheduler':'karras','seed':12345,
               'megapixels':1.5,'aspect':'16:9','strength':.35,'negative_prompt':'custom general negative'}
        before=self.app.store.settings()
        ticket=self.app.send(chat,{'prompt':'Creami 2 immagini. La prima: un faro. La seconda: un lago.',
            'image_model':moss['id'],'image_parameters':saved,'assistant':True})
        job=self.app.store.one('SELECT * FROM jobs WHERE id=?',(ticket['job_id'],))
        # Simulate an Assistant inventing both a different model and settings.
        plan={'images':[{'prompt':p+' 10 steps, CFG 9, seed 1, 1:1','model_id':self.qwen['id'],
            'model_choice':'','references':[],'parameters':{'steps':10,'cfg':9,'seed':1,'aspect':'1:1',
            'negative_prompt':'invented'},'loras':[],'lora_mode':'auto'} for p in ('A lighthouse','A lake')]}
        result={'id':'f'*32,'name':'fixture.png','path':'outputs/fixture.png','mime':'image/png'}
        with patch.object(self.app.engine,'start_llama'),patch.object(self.app.engine,'completion',return_value=(json.dumps(plan),'stop')) as completion,patch.object(self.app.engine,'generate',return_value=result) as generate:
            self.app.execute_job(job,threading.Event())
        answer=self.app.store.one('SELECT status FROM messages WHERE id=?',(job['message_id'],))
        self.assertEqual(answer['status'],'done')
        self.assertEqual(completion.call_count,1);self.assertEqual(generate.call_count,2)
        for call in generate.call_args_list:
            self.assertEqual(call.args[0]['id'],moss['id'])
            for key,value in saved.items():self.assertEqual(call.args[1]['_image_options'][key],value,key)
        self.assertEqual(self.app.store.settings(),before)

    def test_defaults_by_role_and_explicit_model_use_own_settings_with_partial_prompt_override(self):
        moss=self.app.external_model({'profile':'moss','name':'MOSS defaults test','files':self.qwen['external_config']['files']})
        settings=self.settings|{'create_model':moss['id'],'edit_model':self.qwen['id'],'image_overrides':{
            moss['id']:{'steps':32,'cfg':2.5,'seed':42,'negative_prompt':'moss negative'},
            self.qwen['id']:{'steps':24,'cfg':3,'seed':99,'negative_prompt':'qwen negative'}}}
        value={'images':[
            {'prompt':'Lighthouse','model_id':self.qwen['id'],'model_choice':'','references':[],'parameters':{}},
            {'prompt':'Lake','model_id':moss['id'],'model_choice':'','references':[1],'parameters':{}},
            {'prompt':'Mountain','model_id':self.qwen['id'],'model_choice':self.qwen['id'],'references':[],
             'parameters':{'steps':18,'cfg':9,'seed':1}}]}
        text='Crea 3 immagini. La prima: faro. La seconda: lago con immagine 1. La terza: montagna, '+self.qwen['id']+', 18 passi.'
        tasks=validate_plan(self.app,value,[self.image('red')],settings,3,source_prompt=text)
        self.assertEqual([t['model']['id'] for t in tasks],[moss['id'],self.qwen['id'],self.qwen['id']])
        self.assertEqual([(t['parameters']['steps'],t['parameters']['cfg'],t['parameters']['seed']) for t in tasks],[(32,2.5,42),(24,3,99),(18,3,99)])
        self.assertEqual([t['parameters']['negative_prompt'] for t in tasks],['moss negative','qwen negative','qwen negative'])

    def test_grouped_aspects_still_override_defaults_without_section_markers(self):
        value={'images':[{'prompt':'Lighthouse','model_id':self.qwen['id'],'model_choice':'','references':[],
                         'parameters':{'aspect':aspect,'steps':99}} for aspect in ('16:9','9:16')]}
        tasks=validate_plan(self.app,value,[],self.settings,2,source_prompt='Crea 2 immagini, una 16:9 e una 9:16')
        self.assertEqual([t['parameters']['aspect'] for t in tasks],['16:9','9:16'])
        self.assertTrue(all(t['parameters']['steps']!=99 for t in tasks))

    def test_ambiguous_moss_requires_variant_or_uses_selected_matching_model(self):
        models=[{'id':'moss-int8','name':'MOSS-Image SFT INT8 · opzionale'},
                {'id':'moss-bf16','name':'MOSS-Image SFT BF16 · opzionale'},
                {'id':'moss-new','name':'MOSS New v3 INT8'}]
        with self.assertRaisesRegex(ValueError,'Specifica quale'):
            model_choice(models,'MOSS','qwen','usa MOSS per la prima')
        self.assertEqual(model_choice(models,'MOSS','moss-bf16','usa MOSS per la prima'),'moss-bf16')
        self.assertEqual(model_choice(models,'MOSS BF16','qwen','usa MOSS BF16'),'moss-bf16')
        self.assertEqual(model_choice(models,'MOSS New v3','qwen','usa MOSS New v3'),'moss-new')
        with self.assertRaisesRegex(ValueError,'effettivamente scritto'):
            model_choice(models,'MOSS BF16','qwen','usa MOSS')

    def test_original_local_controls_override_omitted_or_wrong_planner_parameters(self):
        from h3chat.image_batch_controls import source_controls
        text='Creami 4 immagini, due 16:9 e due 9:16. Prima: faro, 16:9, 0.5 MP, seed fisso 99. La seconda: lago, 9:16, seed casuale. La terza e la quarta: montagna, 9:16, seed fisso 42.'
        self.assertNotIn('9:16',source_controls(text,1));self.assertIn('99',source_controls(text,1))
        plan={'images':[{'prompt':'Landscape','model_id':self.qwen['id'],'references':[],
                         'parameters':{'seed':555,'aspect':'1:1'}} for _ in range(4)]}
        tasks=validate_plan(self.app,plan,[],self.settings,4,source_prompt=text)
        self.assertEqual(tasks[0]['parameters']['seed'],99);self.assertEqual(tasks[0]['parameters']['aspect'],'16:9')
        self.assertNotEqual(tasks[1]['parameters']['seed'],555);self.assertEqual(tasks[1]['parameters']['aspect'],'9:16')
        self.assertEqual([t['parameters']['seed'] for t in tasks[2:]],[42,42])
        numbered='Creami 2 immagini:\n1) faro, seed fisso 123;\n2) lago, seed casuale'
        self.assertIn('123',source_controls(numbered,1));self.assertNotIn('123',source_controls(numbered,2))

    def test_uploaded_adapter_is_inspected_and_only_bound_to_compatible_images(self):
        from test_loras_image_options import lora
        from h3chat.image_batch_loras import uploaded
        path=lora(self.base/'adapter.safetensors','qwen_image_2.1')
        media=self.app.upload({'name':path.name,'data':base64.b64encode(path.read_bytes()).decode()})
        snapshot=uploaded(self.app,[media]);self.assertEqual(snapshot[0]['family'],'qwen21')
        moss=self.app.external_model({'profile':'moss','files':self.qwen['external_config']['files']})
        plan={'images':[{'prompt':'Mountain','model_id':self.qwen['id'],'references':[],'parameters':{},'lora_mode':'auto','loras':[]},
                        {'prompt':'Lake','model_id':moss['id'],'references':[],'parameters':{},'lora_mode':'auto','loras':[]}]}
        tasks=validate_plan(self.app,plan,[],self.settings,2,snapshot)
        self.assertEqual([len(t['loras']) for t in tasks],[1,0]);self.assertEqual(tasks[0]['loras'][0]['model_id'],self.qwen['id'])
        plan['images'][1].update(lora_mode='explicit',loras=[{'id':media['id'],'weight':.8}])
        with self.assertRaisesRegex(ValueError,'non compatibile'):validate_plan(self.app,plan,[],self.settings,2,snapshot)
        plan['images'][1].update(lora_mode='none',loras=[]);path_snapshot=self.app.data/media['path'];path_snapshot.write_bytes(path_snapshot.read_bytes()+b'\0')
        with self.assertRaisesRegex(ValueError,'cambiato'):validate_plan(self.app,plan,[],self.settings,2,snapshot)

    def test_adapter_file_in_chat_is_never_sent_as_an_image_reference(self):
        from test_loras_image_options import lora
        path=lora(self.base/'qwen-adapter.safetensors','qwen_image_2.1')
        adapter=self.app.upload({'name':path.name,'data':base64.b64encode(path.read_bytes()).decode()})
        plan={'images':[{'prompt':p,'model_id':self.qwen['id'],'model_choice':'','parameters':{'seed':42},
                         'references':[],'loras':[],'lora_mode':'auto'} for p in ('A mountain','A lake')]}
        chat=self.app.store.create_chat()['id'];ticket=self.app.send(chat,{'prompt':'Creami 2 immagini con il LoRA allegato','media':[{'id':adapter['id']}],'assistant':True})
        job=self.app.store.one('SELECT * FROM jobs WHERE id=?',(ticket['job_id'],))
        output={'id':'e'*32,'path':'outputs/fixture.png','name':'fixture.png','mime':'image/png'}
        with patch.object(self.app.engine,'start_llama'),patch.object(self.app.engine,'completion',return_value=(json.dumps(plan),'stop')),patch.object(self.app.engine,'generate',return_value=output.copy()) as generate:
            self.app.execute_job(job,threading.Event())
        self.assertEqual(self.app.store.one('SELECT status FROM jobs WHERE id=?',(job['id'],))['status'],'done')
        for call in generate.call_args_list:
            self.assertEqual(call.args[3],[])
            self.assertEqual([l['id'] for l in call.args[1]['_loras']],[adapter['id']])
        self.assertEqual(len(json.loads(job['payload'])['loras']),1)

    def test_cancel_keeps_completed_images_in_same_answer_canvas_and_gallery(self):
        plan={'images':[{'prompt':name,'model_id':self.qwen['id'],'model_choice':'','references':[],'parameters':{'seed':7},'loras':[],'lora_mode':'auto'} for name in ('Mountain','Lake')]}
        chat=self.app.store.create_chat()['id'];ticket=self.app.send(chat,{'prompt':'Crea 2 immagini, seed 7','assistant':True})
        job=self.app.store.one('SELECT * FROM jobs WHERE id=?',(ticket['job_id'],));calls=[]
        def generate(model,settings,prompt,refs,ident,cancel,stage):
            calls.append(ident)
            if len(calls)==2:raise Cancelled()
            folder=self.app.data/'outputs'/ident;folder.mkdir(parents=True);(folder/'image.png').write_bytes(PNG)
            return {'id':ident,'path':f'outputs/{ident}/image.png','mime':'image/png','name':'image.png'}
        with patch.object(self.app.engine,'start_llama'),patch.object(self.app.engine,'completion',return_value=(json.dumps(plan),'stop')),patch.object(self.app.engine,'generate',side_effect=generate):
            self.app.execute_job(job,threading.Event())
        answer=self.app.store.one('SELECT * FROM messages WHERE id=?',(job['message_id'],))
        self.assertEqual(answer['status'],'cancelled');self.assertEqual(len(json.loads(answer['media'])),1)
        self.assertEqual(len(self.app.store.canvas_history.get(chat)['media']),1)
        self.assertIsNotNone(self.app.store.one('SELECT id FROM gallery WHERE id=?',(calls[0],)))
        from h3chat.image_history import last_seed
        self.assertEqual(last_seed(self.app,self.qwen['id'])['seed'],7)


if __name__=='__main__':unittest.main()

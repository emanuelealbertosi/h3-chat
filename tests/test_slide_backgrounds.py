import base64
import json
import threading
import unittest
from unittest.mock import patch
import test_visual_models as fixture
from h3chat.downloads import Cancelled
from h3chat.slide_backgrounds import options,plan,enqueue,listing

PNG=base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aOKsAAAAASUVORK5CYII=')


class BackgroundTests(unittest.TestCase):
    setUp=fixture.VisualModelsTests.setUp
    tearDown=fixture.VisualModelsTests.tearDown

    def ticket(self,config=None):
        chat=self.app.store.create_chat()['id']
        ticket=enqueue(self.app,chat,{'prompt':'Botanica delicata, solo decorazioni ai bordi','options':{'name':'Botanica','model':self.qwen['id'],**(config or {})}})
        return chat,self.app.store.one('SELECT * FROM jobs WHERE id=?',(ticket['job_id'],))

    def generate(self,model,settings,prompt,refs,ident,cancel,stage):
        folder=self.app.data/'outputs'/ident;folder.mkdir(parents=True);(folder/'image.png').write_bytes(PNG)
        return dict(id=ident,path=f'outputs/{ident}/image.png',mime='image/png',name='fixture.png',
                    generation={'seed':settings['_image_options']['seed'],'width':settings['_image_options']['width'],'height':settings['_image_options']['height']})

    def test_validation_bounds_and_no_silent_count_truncation(self):
        for invalid in ({'variants':True},{'variants':25},{'themes':['x']*9},{'palettes':[]},{'palettes':['unknown']},
                        {'palettes':['pastel','pastel']},{'kind':'other'},{'margin':0},{'opacity':90},
                        {'palettes':['custom']},{'megapixels':float('nan')},{'seed':-2},
                        {'themes':['a','b','c'],'palettes':['pastel','warm'],'variants':5}):
            with self.subTest(invalid=invalid),self.assertRaises(ValueError):options(invalid)
        self.assertEqual(options({'themes':[' a ','a']})['themes'],['a'])
        config=options({'variants':10})
        self.assertEqual(len(plan(config,'Porte logiche',self.qwen,self.settings)),10)

    def test_matrix_presets_and_fixed_seed_without_llm(self):
        before=self.app.store.settings()
        cfg=options(dict(themes=['foglie','stelle'],palettes=['pastel','blue'],variants=2,seed_mode='fixed',seed=42))
        tasks=plan(cfg,'Delicato',self.app.engine.require_model(self.qwen['id'],'create'),before)
        self.assertEqual(len(tasks),8)
        self.assertEqual([(t['theme'],t['palette']) for t in tasks[::2]],[('foglie','pastel'),('foglie','blue'),('stelle','pastel'),('stelle','blue')])
        for task in tasks:
            p=task['parameters'];self.assertEqual(p['seed'],42);self.assertEqual(p['steps'],25)
            self.assertGreater(p['width'],p['height']);self.assertIn('completely empty',task['prompt']);self.assertIn('No written text',task['prompt'])
        self.assertEqual(self.app.store.settings(),before)

    def test_theme_precedes_generic_layout_and_topic_symbols_are_allowed(self):
        cfg=options({'themes':['informatica e porte logiche AND OR NOT']})
        text=plan(cfg,'genera gli sfondi',self.qwen,self.settings)[0]['prompt']
        self.assertTrue(text.startswith('THEME: informatica e porte logiche AND OR NOT.'))
        self.assertIn('recognizable objects and symbols from THIS THEME',text)
        self.assertLess(text.index('porte logiche'),text.index('Decorative frame'))
        self.assertNotIn('watermarks, charts',text)

    def test_job_bypasses_slides_chat_rag_and_keeps_set(self):
        self.app.store.save_settings({'chat_model':''})  # Image-only batches do not require a configured LLM.
        before=self.app.store.settings();chat,job=self.ticket({'palettes':['natural','warm'],'variants':2,'seed_mode':'fixed','seed':99})
        payload=json.loads(job['payload']);self.assertEqual(payload['media'],[]);self.assertFalse(payload['settings']['_assistant'])
        observed=[]
        def generated(*args):
            row=self.app.store.one('SELECT media FROM messages WHERE id=?',(job['message_id'],))
            observed.append(len(json.loads(row['media'])))
            return self.generate(*args)
        with patch.object(self.app.engine,'generate',side_effect=generated) as generate,patch.object(self.app.engine,'start_llama') as llm,patch.object(self.app.engine,'completion') as completion,patch.object(self.app.knowledge,'retrieve') as rag,patch('h3chat.slides.build') as slides:
            self.app.execute_job(job,threading.Event())
        answer=self.app.store.one('SELECT * FROM messages WHERE id=?',(job['message_id'],));self.assertEqual(answer['status'],'done',answer['meta'])
        llm.assert_not_called();completion.assert_not_called();rag.assert_not_called();slides.assert_not_called()
        self.assertEqual(generate.call_count,4);self.assertTrue(all(call.args[3]==[] for call in generate.call_args_list))
        self.assertEqual(observed,[0,1,2,3])
        media=json.loads(answer['media']);self.assertEqual(len(media),4);self.assertTrue(all(m['slide_background']['kind']=='frame' for m in media))
        self.assertTrue(all(m['generation']['seed']==99 for m in media))
        self.assertEqual(len(self.app.store.canvas_history.get(chat)['media']),4)
        saved=listing(self.app)['items'];self.assertEqual(len(saved),1);self.assertEqual(saved[0]['status'],'done');self.assertEqual(saved[0]['available'],4)
        self.assertEqual(saved[0]['prompt'],'Botanica delicata, solo decorazioni ai bordi')
        self.assertEqual(self.app.store.settings(),before)
        self.assertEqual(self.app.store.one('SELECT status FROM jobs WHERE id=?',(job['id'],))['status'],'done')
        # A removed file is reported unavailable without losing the recipe or other images.
        (self.app.data/media[0]['path']).unlink();self.assertEqual(listing(self.app)['items'][0]['available'],3)

    def test_cancel_retains_partial_set_canvas_and_gallery(self):
        chat,job=self.ticket({'variants':3});calls=[]
        def generate(*args):
            calls.append(args)
            if len(calls)==2:raise Cancelled()
            return self.generate(*args)
        with patch.object(self.app.engine,'generate',side_effect=generate):self.app.execute_job(job,threading.Event())
        answer=self.app.store.one('SELECT * FROM messages WHERE id=?',(job['message_id'],));self.assertEqual(answer['status'],'cancelled')
        self.assertEqual(len(json.loads(answer['media'])),1);self.assertEqual(len(self.app.store.canvas_history.get(chat)['media']),1)
        saved=listing(self.app)['items'][0];self.assertEqual(saved['status'],'cancelled');self.assertEqual(saved['available'],1)
        self.assertIsNotNone(self.app.store.one('SELECT id FROM gallery WHERE id=?',(saved['images'][0]['media']['id'],)))

    def test_cpu_and_invalid_batch_rejected_before_enqueue(self):
        chat=self.app.store.create_chat()['id']
        with self.assertRaises(ValueError):enqueue(self.app,chat,dict(prompt='test',options=dict(variants=6,themes=['a','b','c','d','e'])))
        self.assertEqual(self.app.store.all('SELECT id FROM jobs'),[])

        self.app.store.save_settings({'execution_mode':'cpu'})
        with self.assertRaisesRegex(ValueError,'CPU'):enqueue(self.app,chat,dict(prompt='test'))
        self.assertEqual(self.app.store.all('SELECT id FROM jobs'),[])

    def test_explicit_prompt_sampling_overrides_form_and_recovery_status(self):
        cfg=options(dict(seed_mode='fixed',seed=42,format='16:9'))
        tasks=plan(cfg,'Fiori, formato 9:16, seed 77, 8 passi',self.app.engine.require_model(self.qwen['id'],'create'),self.settings)
        for task in tasks:
            self.assertEqual(task['parameters']['seed'],77);self.assertEqual(task['parameters']['steps'],8)
            self.assertLess(task['parameters']['width'],task['parameters']['height'])
        chat,job=self.ticket()
        with patch.object(self.app.engine,'generate',side_effect=self.generate):self.app.execute_job(job,threading.Event())
        path=self.app.data/'slide-backgrounds'/(job['id']+'.json');collection=json.loads(path.read_text(encoding='utf8'))
        collection['status']='running';path.write_text(json.dumps(collection),encoding='utf8')
        self.assertEqual(listing(self.app)['items'][0]['status'],'done')

    def test_empty_library_and_no_cross_workspace_paths(self):
        self.assertEqual(listing(self.app),{'items':[]})
        folder=self.app.data/'slide-backgrounds';folder.mkdir()
        (folder/('a'*32+'.json')).write_text(json.dumps(dict(id='a'*32,images=[dict(media=dict(path='../outside.png',mime='image/png'))])),encoding='utf8')
        self.assertEqual(listing(self.app),{'items':[]})


if __name__=='__main__':unittest.main()

"""Real Agent adapters and saved background composition, without image inference."""
import copy
import json
import threading
import unittest
from unittest.mock import patch
from test_agent_runtime import AgentTests,decision
from h3chat import agent_state
from h3chat.slides import encode,PREFIX


class BackgroundTests(unittest.TestCase):
    setUp=AgentTests.setUp
    tearDown=AgentTests.tearDown
    ticket=AgentTests.ticket
    run_job=AgentTests.run_job
    def test_frame_created_as_background_and_used_by_slides(self):
        chat,job=self.ticket('agent: Crea una cornice a tema porte logiche e due slide in stile fumettoso',allow_images=True,confirm_writes=False)
        calls=[0];captured={}
        def completion(messages,settings,cancel,**kw):
            calls[0]+=1
            if calls[0]==1:return decision('create_slide_backgrounds',{'name':'Porte logiche','prompt':'Porte logiche AND e OR, circuiti e connessioni','count':1,'format':'16:9','model_id':self.qwen['id'],'margin':6,'design':'professional'})
            if calls[0]==2:
                data=json.loads(messages[-1]['content']);result=json.loads(data['observations'][-1]['data'])
                return decision('create_slides',{'prompt':'Due slide','count':2,'background_style':result['background_style']})
            return decision('finish')
        def generate(model,settings,prompt,refs,ident,cancel,stage):
            from test_image_batch import PNG
            self.assertFalse(refs);self.assertEqual(settings['_image_options']['aspect'],'16:9')
            self.assertIn('Porte logiche AND e OR',prompt);self.assertIn('ink-outlined comic illustration',prompt)
            self.assertNotIn('refined editorial illustration',prompt);self.assertIn('outer 6%',prompt)
            path=self.app.data/'outputs'/ident/'image.png';path.parent.mkdir(parents=True);path.write_bytes(PNG)
            return {'id':ident,'name':'Cornice','mime':'image/png','path':str(path.relative_to(self.app.data)).replace('\\','/'),'generation':{'seed':42}}
        def build(app,child,payload,history,settings,*args):
            captured.update(settings)
            from h3chat.slide_background_style import assign
            deck={'version':1,'format':'16:9','pages':[{'title':'Uno','html':'<h1>Uno</h1>','status':'ready'},{'title':'Due','html':'<h1>Due</h1>','status':'ready'}]}
            media=settings['_slide_background_assets'];assign(deck,settings['_slides']['background_style'],media)
            value={'title':'Slide','content':encode(deck),'media':media};app.save_artifact(chat,**value);return value
        with patch.object(self.app.engine,'prepare'),patch.object(self.app.engine,'start_llama'),patch.object(self.app.engine,'stop'),patch.object(self.app.engine,'completion',side_effect=completion),patch.object(self.app.engine,'generate',side_effect=generate),patch('h3chat.slides.build',side_effect=build):
            self.app.execute_job(job,threading.Event())
        state=agent_state.load(self.app,chat,job['id']);self.assertEqual(state['status'],'done',state['message'])
        self.assertEqual(state['usage']['images_started'],1)
        self.assertEqual(len(captured['_slide_background_assets']),1)
        self.assertEqual(captured['_slide_background_assets'][0]['slide_background']['margin'],6)
        self.assertEqual(captured['_slides']['design'],'comic')
        from h3chat.slide_style import explicit_design
        self.assertIsNone(explicit_design('Cornice comic e slide professional: due stili diversi'))

    def test_existing_frame_applied_without_regeneration_and_foreign_chat_denied(self):
        chat,job=self.ticket('agent: Applica la cornice',confirm_writes=False)
        from test_image_batch import PNG
        path=self.app.data/'outputs/frame.png';path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(PNG)
        image={'id':'a'*32,'name':'Cornice','mime':'image/png','path':'outputs/frame.png','generation':{'width':1024,'height':1024}}
        source=self.app.store.canvas_history.save(chat,{'title':'Cornice','content':'','media':[image]})
        original={'version':1,'engine':'llm','format':'16:9','pages':[{'title':'Uno','html':'<h1>Uno</h1>','notes':'Note conservate','status':'ready'}]}
        slide=self.app.store.canvas_history.save(chat,{'title':'Slide','content':encode(original),'media':[]})
        n=[0]
        def completion(*args,**kw):
            n[0]+=1
            return decision('apply_slide_background',{'artifact_id':slide['id'],'image_artifact_id':source['id'],'margin':6}) if n[0]==1 else decision('finish')
        _,_,generate=self.run_job(job,completion);generate.assert_not_called()
        state=agent_state.load(self.app,chat,job['id']);self.assertEqual(state['status'],'done',state)
        self.assertTrue(state['artifacts'],state['actions'])
        result=self.app.store.canvas_history.get(chat,state['artifacts'][-1]['id'])
        deck=json.loads(result['content'][len(PREFIX):-4]);self.assertEqual(deck['pages'][0]['notes'],'Note conservate')
        self.assertEqual(deck['pages'][0]['background_asset_id'],image['id'])
        self.assertEqual(result['media'][0]['slide_background']['format'],'1024:1024')
        self.assertEqual(json.loads(self.app.store.canvas_history.get(chat,slide['id'])['content'][len(PREFIX):-4]),original)
        other=self.app.store.create_chat()['id']
        from h3chat.agent_tools import artifact
        with self.assertRaises(ValueError):artifact(self.app,other,source['id'])

"""Explicit I2V binding survives Assistant and Agent planning, without GPU."""
import base64
import json
import threading
import unittest
from unittest.mock import patch
import test_video as video_fixture
import test_agent_runtime as agent_fixture
from h3chat.video_routing import requested_start_image,direct_plan
from h3chat.store import DEFAULTS


class I2VBindingTests(unittest.TestCase):
    setUp=video_fixture.VideoTests.setUp
    tearDown=video_fixture.VideoTests.tearDown

    def test_explicit_picture_two_is_the_start_not_picture_one(self):
        refs=[{'mime':'image/png'},{'mime':'image/png'}]
        prompt='Usa immagine 2 come primo fotogramma; immagine 1 come riferimento.'
        plan=direct_plan(prompt,refs,5)
        self.assertEqual(plan['images'],[{'index':1,'role':'reference','seconds':0},{'index':2,'role':'keyframe','seconds':0}])
        self.assertEqual(plan['prompt'],prompt)

    def test_explicit_i2v_needs_a_real_unambiguous_image(self):
        self.assertEqual(requested_start_image('I2V. Animate gently.',[{'mime':'image/png'}]),1)
        with self.assertRaisesRegex(ValueError,'immagine allegata'):requested_start_image('I2V',[])
        with self.assertRaisesRegex(ValueError,'quale immagine'):requested_start_image('I2V',[{'mime':'image/png'}]*2)
        with self.assertRaisesRegex(ValueError,'non disponibile'):requested_start_image('Picture 3 as first frame',[{'mime':'image/png'}])
        self.assertIsNone(requested_start_image('Use image 1 as identity reference',[{'mime':'image/png'}]))
        self.assertIsNone(requested_start_image('Do not use image 1 as first frame; use as reference.',[{'mime':'image/png'}]))

    def test_assistant_cannot_change_required_start_to_reference_or_another_picture(self):
        refs=[{'mime':'image/png','name':'identity.png'},{'mime':'image/png','name':'start.png'}]
        wrong={'prompt':'Slow camera movement.','images':[{'index':1,'role':'keyframe','seconds':0},
                {'index':2,'role':'reference','seconds':0}],'audios':[]}
        with patch.object(self.app.engine,'require_model',return_value={'id':'chat','name':'Chat','vision':{'enabled':False}}), \
             patch.object(self.app.engine,'start_llama'),patch.object(self.app.engine,'completion',return_value=(json.dumps(wrong),'stop')) as complete:
            plan,info=self.app.engine.refine_video([], 'Usa immagine 2 come primo fotogramma.',refs,self.model,
                DEFAULTS|{'_assistant':True,'vision_enabled':False},threading.Event(),self.folder/'log',lambda _:None)
        self.assertEqual(plan['images'],[{'index':1,'role':'reference','seconds':0},{'index':2,'role':'keyframe','seconds':0}])
        self.assertIn('REQUIRED I2V INITIAL FRAME: Picture 2',complete.call_args.args[0][0]['content'])
        self.assertEqual(complete.call_count,1)


class AgentI2VTests(unittest.TestCase):
    setUp=agent_fixture.AgentTests.setUp
    tearDown=agent_fixture.AgentTests.tearDown
    run_job=agent_fixture.AgentTests.run_job

    def test_agent_i2v_and_assistant_on_survive_queue_handoff(self):
        from test_external_models import safetensors
        from test_image_batch import PNG
        from h3chat.agent_state import load
        files={role:str(safetensors(self.base/(role+'-i2v.safetensors'))) for role in ('diffusion','llm','vae','audio_vae')}
        model=self.app.external_model({'profile':'minimax-h3','files':files})
        self.app.save_settings({'video_model':model['id'],'context':32768,'max_tokens':3000})
        image=self.app.upload({'name':'start.png','data':base64.b64encode(PNG).decode()})
        chat=self.app.store.create_chat()['id']
        ident=self.app.send(chat,{'prompt':'agent: Anima questa immagine.','media':[{'id':image['id']}],
            'agent':{'allow_video':True,'confirm_writes':False},'rag':False})['job_id']
        job=self.app.store.one('SELECT * FROM jobs WHERE id=?',(ident,))
        self.run_job(job,lambda *a,**k:agent_fixture.decision('create_video',{'prompt':'A slow camera movement.',
            'reference_numbers':[1],'input_mode':'i2v','assistant':True,'parameters':{'duration':5}}))
        state=load(self.app,chat,ident);self.assertEqual(state['status'],'awaiting_video',state)
        child=self.app.store.one('SELECT payload FROM jobs WHERE id=?',(state['current_job_id'],))
        body=json.loads(child['payload'])
        self.assertTrue(body['settings']['_assistant'])
        self.assertEqual([m['id'] for m in body['media']],[image['id']])
        self.assertEqual(requested_start_image(body['prompt'],body['media']),1)


if __name__=='__main__':unittest.main()

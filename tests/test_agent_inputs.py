"""Interoperability contracts and full choose/observe chains in isolated stores."""
import base64
import json
import threading
import unittest
from types import SimpleNamespace
from unittest.mock import patch
import test_agent_media as media_fixture
from test_agent_runtime import decision
from h3chat import agent_inputs,agent_state
from h3chat.agent_tools import LINKABLE,TOOLS,validate

class AgentInputTests(unittest.TestCase):
    setUp=media_fixture.AgentMediaTests.setUp
    tearDown=media_fixture.AgentMediaTests.tearDown
    ticket=media_fixture.AgentMediaTests.ticket
    media=media_fixture.AgentMediaTests.media
    drive=media_fixture.AgentMediaTests.drive

    def context(self,chat):
        return SimpleNamespace(app=self.app,job={'chat_id':chat},payload={'media':[]},state={'documents':[]})

    def save(self,chat,title,content='',media=None):
        return self.app.store.canvas_history.save(chat,{'title':title,'content':content,'media':media or []})

    def test_shared_outputs_feed_every_creation_tool_without_losing_text_or_media(self):
        chat,_=self.ticket();ctx=self.context(chat)
        producers=['read_attachment','transcribe_audio','inspect_image','create_slides','create_infographic','create_manim','calculate','create_voice','create_music','resing_music','create_image_lot','edit_image']
        for i,producer in enumerate(producers):
            source=self.save(chat,producer,'Contenuto verificato '+producer,[self.media()])
            for consumer in sorted(LINKABLE):
                with self.subTest(producer=producer,consumer=consumer):
                    agent_inputs.attach(ctx,{'source_artifact_ids':[source['id']]},consumer)
                    self.assertEqual(ctx.source_artifacts[0]['id'],source['id'])
                    self.assertIn('Contenuto verificato '+producer,ctx.active_source_documents[0]['blocks'][0]['text'])
                    self.assertEqual(ctx.tool_payload['media'][0]['id'],'b'*32)
                    self.assertIn('source_artifact_ids',TOOLS[consumer][1]['properties'])

    def test_wrong_media_requires_conversion_and_never_crosses_chat_boundary(self):
        chat,_=self.ticket();ctx=self.context(chat);audio=self.save(chat,'Solo audio',media=[self.media()])
        for tool in LINKABLE-{'create_manim','create_video','edit_video','inspect_video_timeline','assemble_video'}:
            with self.subTest(tool=tool),self.assertRaisesRegex(ValueError,'trascrivi'):agent_inputs.attach(ctx,{'source_artifact_ids':[audio['id']]},tool)
        agent_inputs.attach(ctx,{'source_artifact_ids':[audio['id']]},'create_manim')
        for tool in ('create_video','edit_video','inspect_video_timeline','assemble_video'):
            agent_inputs.attach(ctx,{'source_artifact_ids':[audio['id']]},tool)
            self.assertEqual(ctx.tool_payload['media'][0]['id'],audio['media'][0]['id'])
        image=self.save(chat,'Solo immagine',media=[self.media('image.png','image/png')])
        with self.assertRaisesRegex(ValueError,'inspect_image'):agent_inputs.attach(ctx,{'source_artifact_ids':[image['id']]},'create_music')
        ctx.state['documents']=[{'id':'b'*32,'blocks':[{'text':'Panorama montano'}]}]
        agent_inputs.attach(ctx,{'source_artifact_ids':[image['id']]},'create_music')
        self.assertIn('Panorama montano',ctx.active_source_documents[0]['blocks'][0]['text'])
        other=self.app.store.create_chat()['id'];ctx.job['chat_id']=other
        with self.assertRaises(ValueError):agent_inputs.attach(ctx,{'source_artifact_ids':[image['id']]},'create_slides')

    def test_selected_canvas_is_snapshotted_and_explicit_media_numbers_keep_order(self):
        chat,old=self.ticket();self.app.store.execute("UPDATE jobs SET status='cancelled' WHERE id=?",(old['id'],))
        image=self.media('image.png','image/png');audio=self.media();audio['id']='c'*32
        source=self.save(chat,'Punto di partenza','Testo',[image,audio])
        request=self.app.send(chat,{'prompt':'agent: Parti da qui','agent_start_artifact':source['id'],'rag':False})
        payload=json.loads(self.app.store.one('SELECT payload FROM jobs WHERE id=?',(request['job_id'],))['payload'])
        self.assertEqual(payload['settings']['_agent']['start_artifact']['id'],source['id'])
        ctx=self.context(chat)
        self.assertEqual(agent_inputs.selected(ctx,{'artifact_id':source['id'],'number':2},'audio')['id'],audio['id'])
        with self.assertRaises(ValueError):agent_inputs.selected(ctx,{'artifact_id':source['id'],'number':1},'audio')
        validate('edit_image',{'prompt':'Ritocca','artifact_id':source['id'],'number':50})

    def test_audio_to_transcript_to_slides_uses_actual_returned_id(self):
        chat,job=self.ticket('agent: Parti dall’audio salvato, trascrivi e crea una slide',confirm_writes=False)
        audio=self.save(chat,'Registrazione',media=[self.media()]);steps=[0];captured=[]
        def completion(messages,settings,cancel,**kwargs):
            data=json.loads(messages[-1]['content']);steps[0]+=1
            if steps[0]==1:return decision('transcribe_audio',{'artifact_id':audio['id'],'number':1})
            if steps[0]==2:return decision('create_slides',{'prompt':'Una slide dai dati trascritti','count':1,'source_artifact_ids':[data['artifacts'][-1]['id']]})
            return decision('finish',message='Trascrizione e slide salvate.')
        def slides(app,job,payload,history,settings,*args):
            captured.append(history[-1]['content']);value={'title':'Slide','content':'Dalla registrazione','media':[]}
            app.save_artifact(chat,**value);return value
        with patch.object(self.app.engine,'prepare'),patch.object(self.app.engine,'start_llama'),patch.object(self.app.engine,'completion',side_effect=completion),patch.object(self.app.engine,'transcribe',return_value={'text':'La porta XOR vale uno per ingressi diversi','segments':[]}),patch('h3chat.slides.build',side_effect=slides):
            self.app.execute_job(job,threading.Event())
        state=agent_state.load(self.app,chat,job['id'])
        self.assertEqual(state['status'],'done');self.assertTrue(all(a['status']=='done' for a in state['actions']),state)
        self.assertIn('XOR vale uno',captured[0]);self.assertIn('<contenuti_allegati_e_web>',captured[0])
        self.assertEqual(state['actions'][1]['result']['source_artifact_ids'],[state['artifacts'][0]['id']])

    def test_vision_counts_call_and_preserves_caption_as_source_without_real_model(self):
        chat,job=self.ticket('agent: Descrivi la figura',confirm_writes=False)
        source=self.save(chat,'Figura',media=[self.media('image.png','image/png')]);require=self.app.engine.require_model;calls=[]
        def model(ident,cap):return require(ident,cap)|({'vision':{'enabled':True}} if cap=='chat' else {})
        def completion(messages,settings,cancel,**kwargs):
            if 'action' in (kwargs.get('schema') or {}).get('properties',{}):
                data=json.loads(messages[-1]['content']);return decision('finish') if data['observations'] else decision('inspect_image',{'artifact_id':source['id'],'number':1,'prompt':'Descrivi colori e soggetto'})
            calls.append(messages);return 'Una figura con sfondo rosso.','stop'
        with patch.object(self.app.engine,'require_model',side_effect=model),patch.object(self.app.engine,'prepare'),patch.object(self.app.engine,'start_llama'),patch.object(self.app.engine,'completion',side_effect=completion),patch.object(self.app.engine,'tool_call',return_value={'image_url':'data:image/jpeg;base64,AA=='}):
            self.app.execute_job(job,threading.Event())
        state=agent_state.load(self.app,chat,job['id']);self.assertEqual(state['status'],'done');self.assertEqual(state['usage']['llm_calls'],3)
        self.assertEqual(len(calls),1);self.assertIn('sfondo rosso',state['documents'][0]['blocks'][0]['text'])
        self.assertEqual(calls[0][-1]['content'][0]['type'],'image_url')

    def test_actual_cpu_thumbnail_keeps_original_and_is_bounded(self):
        image=self.media('image.png','image/png');before=(self.app.data/image['path']).read_bytes()
        preview=self.app.engine.tool_call('agent-image-worker.py',{'data':str(self.app.data),'source':image['path']},threading.Event(),lambda s:None,self.base/'preview.log',timeout=30)
        self.assertTrue(preview['image_url'].startswith('data:image/jpeg;base64,'));self.assertLessEqual(len(base64.b64decode(preview['image_url'].split(',')[1])),128*1024)
        self.assertEqual((self.app.data/image['path']).read_bytes(),before)

    def test_resing_checks_existing_runtime_and_preserves_source(self):
        chat,job=self.ticket('agent: Ricanta con nuovo testo',allow_audio=True,confirm_writes=False)
        source=self.save(chat,'Canzone',media=[self.media()]);require=self.app.engine.require_model
        def model(ident,cap):return {'id':ident,'name':'YuE2 fixture','capabilities':['music']} if cap=='music' else require(ident,cap)
        def capture(app,settings,body,media):
            self.assertEqual(media[0]['id'],'b'*32);self.assertTrue(body['music_resing'])
            return settings|{'_music_resing':{'source':media[0],'runtime':{}}}
        with patch.object(self.app.engine,'require_model',side_effect=model),patch('h3chat.music_request.capture',side_effect=capture),patch.object(self.app.engine,'generate_music',return_value=self.media('ricantato.wav')) as generate:
            self.drive(job,'resing_music',{'artifact_id':source['id'],'number':1,'prompt':'Nuovo testo sul tema del mare'})
        self.assertEqual(generate.call_args.args[1]['_music_resing']['source']['id'],'b'*32)

if __name__=='__main__':unittest.main()

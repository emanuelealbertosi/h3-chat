"""All requested non-video Agent adapters; engines are simulated, settings real."""
import json
import threading
import unittest
from unittest.mock import patch
import test_agent_runtime as agent_fixture
from test_agent_runtime import decision
from h3chat.agent_state import load
from h3chat.agent_tools import TOOLS,permission,validate
from h3chat.slides import encode

class AgentMediaTests(unittest.TestCase):
    setUp=agent_fixture.AgentTests.setUp
    tearDown=agent_fixture.AgentTests.tearDown
    ticket=agent_fixture.AgentTests.ticket

    def media(self,name='audio.wav',mime='audio/wav'):
        from test_image_batch import PNG
        folder=self.app.data/'outputs'/'fixture';folder.mkdir(parents=True,exist_ok=True);(folder/name).write_bytes(PNG if mime=='image/png' else b'fixture')
        return {'id':'b'*32,'name':name,'mime':mime,'path':'outputs/fixture/'+name,'generation':{'seed':42}}

    def drive(self,job,action,args,*,extra=None):
        def completion(messages,settings,cancel,**kw):
            if 'action' in (kw.get('schema') or {}).get('properties',{}):
                data=json.loads(messages[-1]['content']);return decision('finish',message='Completato.') if data['artifacts'] else decision(action,args)
            return json.dumps({'title':'Test musicale','style':'Pop italiano','lyrics':'[Verse]\nUna prova originale','abc':'','instrumental':False}),'stop'
        with patch.object(self.app.engine,'prepare'),patch.object(self.app.engine,'start_llama'),patch.object(self.app.engine,'completion',side_effect=completion),patch.object(self.app.engine,'start_video') as video:
            self.app.execute_job(job,threading.Event())
        state=load(self.app,job['chat_id'],job['id']);self.assertEqual(state['status'],'done',state)
        video.assert_not_called();self.assertTrue(all(a['status']=='done' for a in state['actions']),state['actions']);return state

    def test_voice_adapter_uses_selected_voice_fields_and_saves_audio(self):
        chat,job=self.ticket('agent: Leggi questo testo',allow_audio=True,confirm_writes=False)
        def build(app,folder,parts,settings,prompt,*args):
            self.assertEqual(settings['_voice_fields']['mode'],'read');self.assertEqual(parts,[{'text':'Buongiorno a tutti.'}]);self.assertEqual(prompt,'')
            return {},[self.media()]
        with patch('h3chat.voice.synthesize',side_effect=build) as engine:
            state=self.drive(job,'create_voice',{'text':'Buongiorno a tutti.','mode':'read'})
        self.assertEqual(engine.call_count,1);self.assertEqual(len(state['artifacts']),1)

    def test_music_adapter_counts_composition_call_and_keeps_duration(self):
        chat,job=self.ticket('agent: Crea musica',allow_audio=True,confirm_writes=False)
        require=self.app.engine.require_model
        def model(ident,cap):return {'id':ident,'name':'YuE2 fixture','capabilities':['music']} if cap=='music' else require(ident,cap)
        with patch.object(self.app.engine,'require_model',side_effect=model),patch.object(self.app.engine,'generate_music',return_value=self.media()) as generate:
            state=self.drive(job,'create_music',{'prompt':'Una canzone allegra','duration':20})
        self.assertEqual(generate.call_args.args[1]['_music_max_duration'],20)
        self.assertEqual(state['usage']['llm_calls'],3)

    def test_infographic_reuses_builder_with_no_video_background(self):
        chat,job=self.ticket('agent: Crea infografica',confirm_writes=False)
        def build(app,child,payload,history,settings,*args):
            self.assertEqual(settings['_infographic']['video_background'],'off')
            self.assertEqual(settings['_infographic']['output'],'static')
            self.assertFalse(settings['_infographic']['voice']);self.assertEqual(settings['_infographic']['images'],'provided')
            value={'title':'Grafica','content':encode({'version':1,'engine':'llm','format':'16:9','pages':[{'title':'Scena','html':'<h1>Test</h1>','status':'ready'}]}),'media':[]}
            app.save_artifact(chat,value['title'],value['content'],[]);return value
        with patch('h3chat.infographics.build',side_effect=build) as builder:
            state=self.drive(job,'create_infographic',{'prompt':'Le porte logiche','format':'16:9','scenes':1})
        self.assertEqual(builder.call_count,1);self.assertEqual(state['artifacts'][0]['tool'],'create_infographic')

    def test_manim_reuses_renderer_with_cpu_and_no_raw_source(self):
        chat,job=self.ticket('agent: Anima una parabola',allow_manim=True,confirm_writes=False)
        def build(app,child,payload,history,settings,*args):
            self.assertEqual(settings['manim_device'],'cpu');self.assertEqual(settings['_lab_source'],'')
            self.assertEqual(settings['manim_duration'],10)
            return 'Parabola','# Parabola',[self.media('animazione.mp4','video/mp4')]
        with patch('h3chat.manim_artifact.build',side_effect=build) as builder:
            state=self.drive(job,'create_manim',{'prompt':'Mostra una parabola','duration':10})
        self.assertEqual(builder.call_count,1);self.assertEqual(len(state['artifacts']),1)

    def test_transcription_reads_only_chosen_chat_asset(self):
        chat,job=self.ticket('agent: Trascrivi audio',confirm_writes=False)
        media=self.media();source=self.app.store.canvas_history.save(chat,{'title':'Brano','content':'','media':[media]})
        with patch.object(self.app.engine,'transcribe',return_value={'text':'Testo riconosciuto','segments':[]}) as asr:
            state=self.drive(job,'transcribe_audio',{'artifact_id':source['id'],'number':1,'language':'it'})
        self.assertEqual(asr.call_args.args[0]['id'],media['id']);self.assertEqual(asr.call_args.args[1]['asr_language'],'it')
        self.assertIn('Testo riconosciuto',str(state['actions'][0]['result']))

    def test_permissions_and_video_exclusion(self):
        self.assertTrue({'create_voice','create_music','create_infographic','create_manim','transcribe_audio'}<=set(TOOLS))
        self.assertFalse(any(name in TOOLS for name in ('create_video','edit_video','video_timeline')))
        for name,args in [('create_voice',{'text':'Testo'}),('create_music',{'prompt':'Musica'}),('create_manim',{'prompt':'Grafico'}),('create_infographic',{'prompt':'Test','voice':True})]:
            with self.assertRaises(PermissionError):permission({'allow_images':False,'allow_audio':False,'allow_manim':False},name,args)
        with self.assertRaises(ValueError):validate('create_manim',{'prompt':'Test','code':'import os'})
        with self.assertRaises(ValueError):validate('transcribe_audio',{'number':1,'path':'C:/private.wav'})

    def test_qwen_edit_reads_selected_artifact_and_keeps_original(self):
        chat,job=self.ticket('agent: Ritocca l’immagine con Qwen',allow_images=True,confirm_writes=False)
        source=self.media('source.png','image/png');source['id']='c'*32
        selected=self.app.store.canvas_history.save(chat,{'title':'Originale','content':'','media':[source]})
        before=(self.app.data/source['path']).read_bytes()
        with patch.object(self.app.engine,'generate',return_value=self.media('edited.png','image/png')) as generate:
            state=self.drive(job,'edit_image',{'artifact_id':selected['id'],'number':1,'model_id':self.qwen['id'],'prompt':'Schiarisci lo sfondo conservando il soggetto'})
        self.assertEqual(generate.call_args.args[3][0]['id'],source['id']);self.assertEqual(generate.call_args.args[0]['id'],self.qwen['id'])
        self.assertEqual((self.app.data/source['path']).read_bytes(),before)
        edited=self.app.store.canvas_history.get(chat,state['artifacts'][0]['id']);self.assertEqual(edited['media'][0]['generation']['seed'],42)
        self.assertEqual(len(self.app.store.canvas_history.listing(chat)['items']),2)

    def infographic(self,chat):
        from h3chat.infographics import options
        opts=options(value={'scenes':2,'duration':15,'output':'static','voice':False,'images':'provided','music':'none'})
        deck={'version':1,'engine':'llm','format':'16:9','title':'Infografica','pages':[
            {'title':'Scena '+str(i),'status':'ready','html':'<style>body{font:36px Arial}</style><h1>Scena</h1>','notes':'Narrazione'} for i in range(2)],
            'infographic':{'version':1,'durations':[8,7],'options':opts,'transition':'fade','sfx':'none'}}
        return self.app.store.canvas_history.save(chat,{'title':'Infografica','content':encode(deck),'media':[]})

    def test_music_can_target_existing_infographic_duration(self):
        chat,job=self.ticket('agent: Crea musica adatta all’infografica',allow_audio=True,confirm_writes=False)
        target=self.infographic(chat);require=self.app.engine.require_model
        def model(ident,cap):return {'id':ident,'name':'YuE2 fixture','capabilities':['music']} if cap=='music' else require(ident,cap)
        with patch.object(self.app.engine,'require_model',side_effect=model),patch.object(self.app.engine,'generate_music',return_value=self.media()) as generate:
            state=self.drive(job,'create_music',{'prompt':'Sottofondo allegro per le scene','target_artifact_id':target['id']})
        self.assertEqual(generate.call_args.args[1]['_music_max_duration'],15)

    def test_soundtrack_fit_and_render_preserve_scene_content(self):
        chat,job=self.ticket('agent: Applica la musica alla infografica',allow_audio=True,confirm_writes=False)
        target=self.infographic(chat);audio=self.app.store.canvas_history.save(chat,{'title':'Musica','content':'','media':[self.media()]})
        captured=[]
        def render(app,child,settings,cancel,stage,log,meta):
            value=settings['_infographic_render'];captured.append(value)
            result={'title':value['deck']['title'],'content':encode(value['deck']),'media':value['media']}
            app.save_artifact(chat,result['title'],result['content'],result['media']);return result
        with patch.object(self.app.engine,'tool_call',return_value={'duration':15,'looped':True,'pitch_changed':False}) as fit,patch('h3chat.infographics.render_saved',side_effect=render):
            state=self.drive(job,'apply_infographic_music',{'artifact_id':target['id'],'audio_artifact_id':audio['id']})
        self.assertEqual(fit.call_args.args[1]['duration'],15);self.assertEqual(captured[0]['deck']['infographic']['durations'],[8,7])
        self.assertEqual(json.loads(target['content'][13:-4])['pages'],captured[0]['deck']['pages'])
        self.assertEqual(state['actions'][0]['result']['audio_duration'],15)

if __name__=='__main__':unittest.main()

import base64
import io
import json
import tempfile
import threading
import unittest
import urllib.request
import wave
from pathlib import Path
from unittest.mock import patch
from app import Handler,ThreadingHTTPServer
from h3chat.service import Service
from h3chat.store import DEFAULTS
from h3chat.video_options import options,validate,validate_plan
from h3chat.video_routing import route,direct_plan
from h3chat.hardware import assess_model
from h3chat.downloads import Cancelled
from test_external_models import safetensors

ROOT=Path(__file__).resolve().parents[1]
class VideoTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.folder=Path(self.tmp.name).resolve()
        self.app=Service(ROOT,self.folder/'data',start_worker=False)
        self.files={role:str(safetensors(self.folder/'originali'/f'{role}.safetensors')) for role in ('diffusion','llm','vae','audio_vae')}
        self.model=self.app.external_model({'profile':'minimax-h3','name':'H3 fixture','files':self.files})
        self.app.save_settings({'video_model':self.model['id'],'music_model':'','ram_cache_gb':0})
    def tearDown(self):self.app.close();self.tmp.cleanup()
    def test_defaults_and_invalid_numbers(self):
        opts=options(self.model,DEFAULTS,False)
        self.assertEqual(opts['steps'],12)
        self.assertEqual((opts['duration'],opts['megapixels'],opts['frames'],opts['width'],opts['height']),(15,.7,360,1152,640))
        for bad in ({'duration':16},{'steps':True},{'megapixels':float('nan')},{'seed':False},{'offload':'yes'},{'sampler':'lcm'}):
            with self.subTest(bad=bad),self.assertRaises(ValueError):validate(bad)
    def test_routing_and_precedence(self):
        for prompt in ('crea un video musicale','anima questa immagine','Puoi generare un filmato con lip-sync?','make a video'):
            self.assertEqual(route([{'content':prompt}],DEFAULTS)['intent'],'video')
        for prompt in ('come creo un video?','non creare un video','scrivi codice per video','crea un prompt per video','genera una canzone','crea una copertina per il video','genera musica per il video'):
            self.assertIsNone(route([{'content':prompt}],DEFAULTS))
        self.assertIsNone(route([{'content':'crea un video'}],DEFAULTS|{'_music':True}))
        self.assertIsNone(route([{'content':'crea un video'}],DEFAULTS|{'video_auto':False}))
        self.assertEqual(route([{'content':'un tramonto'}],DEFAULTS|{'_video':True})['selection'],'explicit')
    def test_models_stay_at_original_paths_and_presets_are_separate(self):
        self.assertEqual(self.app.engine.model_files(self.model),self.files)
        self.assertEqual(self.model['capabilities'],['video'])
        self.app.save_settings({'video_overrides':{self.model['id']:{'steps':13},'other':{'steps':5}}})
        self.assertEqual(options(self.model,self.app.store.settings())['steps'],13)
        self.app.remove_external_model(self.model['id'])
        self.assertEqual(self.app.store.settings()['video_model'],'')
        self.assertTrue(all(Path(p).exists() for p in self.files.values()))

    def test_linked_model_available_after_restart_before_any_browser_state_request(self):
        self.app.close()
        self.app=Service(ROOT,self.folder/'data',start_worker=False)
        restored=self.app.engine.require_model(self.model['id'],'video')
        self.assertEqual(self.app.engine.model_files(restored),self.files)
    def test_hybrid_default_selection_remains_editable(self):
        from h3chat.external_models import PROFILES
        hybrid=dict(self.files,diffusion=str(safetensors(self.folder/PROFILES['minimax-h3']['default_files']['diffusion'])))
        self.app.save_settings({'video_model':''})
        model=self.app.external_model({'profile':'minimax-h3','files':hybrid,'name':'Hybrid'})
        self.assertEqual(self.app.store.settings()['video_model'],model['id'])
        self.assertEqual(options(model,self.app.store.settings())['steps'],12)
        self.app.save_settings({'video_model':self.model['id'],'video_overrides':{model['id']:{'steps':20}}})
        self.app.external_model({'id':model['id'],'profile':'minimax-h3','files':hybrid,'name':'Hybrid'})
        self.assertEqual(self.app.store.settings()['video_model'],self.model['id'])
        self.assertEqual(options(model,self.app.store.settings())['steps'],20)
    def test_role_validation_and_direct_keyframes(self):
        refs=[{'mime':'image/png'},{'mime':'image/png'},{'mime':'audio/wav'}]
        plan=direct_plan('immagine 1 a 0 secondi; immagine 2 a 7 secondi; audio con lip-sync',refs,15)
        self.assertEqual([x['seconds'] for x in plan['images']],[0,7]);self.assertEqual(plan['audios'][0]['role'],'lipsync')
        for altered in (plan|{'images':[]},plan|{'audios':[{'index':2,'role':'reference'}]},plan|{'images':[{'index':1,'role':'keyframe','seconds':16},{'index':2,'role':'reference'}]},plan|{'images':[{'index':1,'role':'keyframe','seconds':0},{'index':2,'role':'keyframe','seconds':0}]}):
            with self.assertRaises(ValueError):validate_plan(altered,refs,15)
        with self.assertRaises(ValueError):validate_plan(plan|{'prompt':'Use <Picture 10>'},refs,15)
        with self.assertRaises(ValueError):validate_plan(plan|{'prompt':'Use <Audio 0>'},refs,15)
    def test_audio_upload_and_limits(self):
        buffer=io.BytesIO()
        with wave.open(buffer,'wb') as f:f.setparams((1,2,32000,0,'NONE','NONE'));f.writeframes(b'\0\0'*32)
        media=self.app.upload({'name':'test.wav','data':base64.b64encode(buffer.getvalue()).decode()})
        self.assertEqual(media['mime'],'audio/wav');self.assertEqual(self.app.validate_media([media]),[media])
        with self.assertRaises(ValueError):self.app.validate_media([media]*2)
        with self.assertRaises(ValueError):self.app.upload({'data':base64.b64encode(b'<script>bad</script>').decode()})
    def test_video_job_snapshot_and_canvas_without_llm(self):
        for canvas in (False,True):
            chat=self.app.store.create_chat()
            job_id=self.app.send(chat['id'],{'prompt':'Crea un video di un tramonto','assistant':False,'video':True,'canvas':canvas})['job_id']
            job=self.app.store.one('SELECT * FROM jobs WHERE id=?',(job_id,))
            self.app.store.save_settings({'video_overrides':{self.model['id']:{'steps':13}}})
            media={'id':job_id,'name':'video.mp4','path':f'outputs/{job_id}/video.mp4','mime':'video/mp4','generation':{'duration':15}}
            with patch.object(self.app.engine,'start_llama') as llama,patch.object(self.app.engine,'generate_video',return_value=media) as generate:
                self.app.execute_job(job,threading.Event())
            llama.assert_not_called();self.assertTrue(json.loads(job['payload'])['settings']['_video'])
            self.assertEqual(generate.call_args.args[1],json.loads(job['payload'])['settings'])
            answer=self.app.store.chat(chat['id'])['messages'][-1]
            self.assertEqual(answer['status'],'done',answer['meta']);self.assertEqual(answer['media'],[] if canvas else [media])
            if canvas:self.assertEqual(answer['meta']['artifact']['media'],[media])
    def test_assistant_reuses_chat_and_vision_off_is_text_only(self):
        refs=[{'mime':'image/png','name':'frame.png'}]
        plan=direct_plan('start frame',refs,15)
        with patch.object(self.app.engine,'require_model',return_value={'id':'chat','name':'Chat','vision':{'enabled':False}}),patch.object(self.app.engine,'start_llama') as start,patch.object(self.app.engine,'completion',return_value=(json.dumps(plan),'stop')) as completion:
            output,info=self.app.engine.refine_video([], 'anima questa immagine',refs,self.model,DEFAULTS|{'vision_enabled':False},threading.Event(),self.folder/'log',lambda _:None)
        start.assert_called_once();self.assertEqual(output,plan);self.assertEqual(info['model'],'Chat')
        self.assertNotIn('image_url',json.dumps(completion.call_args.args[0]))
    def test_audio_only_assistant_plan_uses_real_inventory_without_picture_example(self):
        refs=[{'mime':'audio/mpeg','name':'song.mp3'}]
        plan={'prompt':'Original stage performance synchronized to <Audio 1>.','images':[],'audios':[{'index':1,'role':'lipsync','start':0}]}
        with patch.object(self.app.engine,'require_model',return_value={'id':'chat','name':'Chat','vision':{'enabled':False}}),patch.object(self.app.engine,'start_llama'),patch.object(self.app.engine,'completion',return_value=(json.dumps(plan),'stop')) as completion:
            output,info=self.app.engine.refine_video([], 'crea un video musicale con lip-sync',refs,self.model,DEFAULTS,threading.Event(),self.folder/'log',lambda _:None)
        self.assertEqual(output,plan)
        instructions=completion.call_args.args[0][0]['content']
        self.assertIn('Allowed Picture labels: NONE',instructions)
        self.assertIn('Allowed Audio labels: <Audio 1>',instructions)
        self.assertNotIn('<Picture 1>',instructions)
    def test_session_key_only_changes_for_loading_parameters(self):
        key=self.app.engine.session_key('video',self.model,DEFAULTS)
        self.assertEqual(key,self.app.engine.session_key('video',self.model,DEFAULTS|{'video_overrides':{self.model['id']:{'steps':13}}}))
        self.assertNotEqual(key,self.app.engine.session_key('video',self.model,DEFAULTS|{'video_overrides':{self.model['id']:{'offload':False}}}))
    def test_assistant_limit_is_saved_per_chat_llm(self):
        self.app.save_settings({'chat_model':'qwen3-06','video_prompt_max_tokens':1400})
        self.assertEqual(self.app.save_settings({'chat_model':'qwen3-4'})['video_prompt_max_tokens'],3000)
        self.app.save_settings({'video_prompt_max_tokens':4000})
        self.assertEqual(self.app.save_settings({'chat_model':'qwen3-06'})['video_prompt_max_tokens'],1400)
    def test_video_reuse_switch_and_cancellation(self):
        cancel=threading.Event();settings=self.app.store.settings()
        class Process:
            pid=123;ended=False;stdin=None;stdout=None
            def poll(self):return 0 if self.ended else None
            def terminate(self):self.ended=True
            def wait(self,timeout):return 0
        engine=self.app.engine
        session=engine._activate('video',self.model,settings,self.folder/'log',cancel)
        session.process=Process();session.ready=True
        self.assertIs(engine._activate('video',self.model,settings,self.folder/'log',cancel),session)
        engine.abort_active();self.assertFalse(session.alive());self.assertEqual(engine.sessions,{})
        cancel.set()
        with self.assertRaises(Cancelled):engine._activate('video',self.model,settings,self.folder/'log',cancel)
    def test_memory_estimate_reports_offload_and_cuda_requirement(self):
        hardware={'ram':{'free_mb':64000},'gpu':[{'name':'NVIDIA','vendor':'NVIDIA','free_mb':24000,'total_mb':24000}]}
        assessed=assess_model(self.model,DEFAULTS,hardware)
        self.assertEqual(assessed['status'],'offload');self.assertEqual(assessed['recommended_patch'],{})
        self.assertEqual(assess_model(self.model,DEFAULTS,hardware|{'gpu':[]})['title'],'NVIDIA CUDA richiesta')
    def test_video_http_range(self):
        folder=self.app.data/'outputs'/'test';folder.mkdir(parents=True);raw=b'\0\0\0\x18ftypisom'+bytes(range(200));(folder/'video.mp4').write_bytes(raw)
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler);server.app=self.app
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            url=f'http://127.0.0.1:{server.server_port}/media/outputs/test/video.mp4'
            with urllib.request.urlopen(urllib.request.Request(url,headers={'Range':'bytes=12-31'})) as response:
                self.assertEqual(response.status,206);self.assertEqual(response.headers['Content-Type'],'video/mp4');self.assertEqual(response.read(),raw[12:32])
        finally:server.shutdown();server.server_close()

if __name__=='__main__':unittest.main()

import json
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch
from h3chat.video_engine import VideoEngine
from h3chat.video_job_resume_render import render
from h3chat.video_resume import save
from h3chat.video_timeline import timeline


class VideoResumeExecutionTests(unittest.TestCase):
    def test_saved_plan_skips_completed_clips_and_does_not_start_assistant(self):
        with tempfile.TemporaryDirectory() as tmp:
            data=Path(tmp);origin='a'*32;target='b'*32
            audio={'id':'audio','name':'song.wav','mime':'audio/wav','path':'song.wav'}
            (data/'song.wav').write_bytes(b'original soundtrack')
            folder=data/'outputs'/origin;folder.mkdir(parents=True)
            first=folder/'first.mp4';first.write_bytes(b'\x00\x00\x00\x18ftypisom')
            relative=first.relative_to(data).as_posix()
            plan={'prompt':'Exact saved film','images':[],'audios':[{'index':1,'role':'reuse','start':0}]}
            save(folder,{'timeline':timeline(42),'prompts':['saved one','saved two','saved three'],
                'plan':plan,'model':'original','audio_start':3,'completed':1,'outputs':[relative],
                'parameters':[{'seed':734,'steps':12}],
                'request_context':{'references':[audio],'settings':{'_video_soundtrack':audio,
                    '_video_audio_source_duration':45,'_video_editing':'continuous'}}})
            engine=VideoEngine();engine.data=data;engine.require_model=Mock(return_value={'id':'original','name':'Original'})
            engine.start_llama=Mock(side_effect=AssertionError('No LLM must load'))
            calls=[]
            def generate(model,settings,local,refs,ident,*args,**kwargs):
                calls.append((ident,local,refs));path=data/'outputs'/ident/'video.mp4';path.parent.mkdir(parents=True)
                path.write_bytes(b'\x00\x00\x00\x18ftypisom')
                return {'path':path.relative_to(data).as_posix(),'generation':{'seed':734,'steps':12}}
            engine.generate_video=generate
            store=SimpleNamespace(messages=Mock(return_value=[]),update_answer=Mock(),execute=Mock())
            app=SimpleNamespace(data=data,engine=engine,store=store,save_artifact=Mock())
            job={'id':target,'chat_id':'chat'}
            settings={'video_model':'original','_video_resume':origin,'_assistant':False}
            payload={'prompt':'Do not reinterpret me','until':1,'media':[],'loras':[],'canvas':False}
            with patch('h3chat.soundtrack.compose',return_value={'duration':42}) as mux:
                render(app,job,payload,settings,threading.Event(),Mock(),data/'log')
            self.assertEqual([x[0] for x in calls],[target+'/scene-002',target+'/scene-003'])
            self.assertTrue(calls[0][1]['prompt'].startswith('saved two\n'))
            self.assertTrue(calls[1][1]['prompt'].startswith('saved three\n'))
            self.assertEqual([x[1]['audios'][0]['start'] for x in calls],[18,33])
            self.assertEqual(mux.call_args.args[1][0],first)
            self.assertEqual(mux.call_args.kwargs['audio_start'],3)
            self.assertEqual(first.read_bytes(),b'\x00\x00\x00\x18ftypisom')
            self.assertEqual(json.loads((data/'outputs'/target/'scenes.json').read_text())['completed'],3)
            self.assertEqual(settings,{'video_model':'original','_video_resume':origin,'_assistant':False})
            engine.start_llama.assert_not_called()


if __name__=='__main__':unittest.main()

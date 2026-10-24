import json
import threading
import unittest
from pathlib import Path
from unittest.mock import patch
import test_video_import as fixture
from h3chat.video_edit import describe,request


@unittest.skipUnless((Path(__file__).resolve().parents[1]/'runtime/remix/ffmpeg.exe').is_file(),'Optional FFmpeg media runtime is not installed.')
class OriginalAudioLipSyncTests(unittest.TestCase):
    setUp=fixture.ExternalVideoTests.setUp
    tearDown=fixture.ExternalVideoTests.tearDown
    original=fixture.ExternalVideoTests.original
    ff=fixture.ExternalVideoTests.ff

    def test_every_clip_receives_its_original_audio_interval_without_external_upload(self):
        chat,media=self.original(seconds=25)
        manifest=describe(self.app,chat,media['id'],10)
        patches=[{'clip':c['clip'],'mode':'video','prompt':'Preserve the performance','images':[],
                  'lip_sync':True,'audio_guide':True} for c in manifest['clips']]
        ident=request(self.app,chat,{'source':media['id'],'segment_seconds':10,'assistant':False,
                                    'remount':False,'patches':patches})['job_id']
        offsets=[]
        def generate(model,settings,plan,refs,job,cancel,stage,**kw):
            self.assertEqual(len(refs),1)
            self.assertTrue(refs[0]['path'].startswith('outputs/video-imports/'+media['id']+'/'))
            self.assertEqual(plan['audios'][0]['role'],'lipsync')
            offsets.append(plan['audios'][0]['start'])
            self.assertIn('<Audio 1>',plan['prompt'])
            target=self.app.data/'outputs'/job/'video.mp4';target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(b'\x00\x00\x00\x18ftypisomnew')
            canvas=kw['scene']['canvas']
            return {'path':target.relative_to(self.app.data).as_posix(),'generation':{'duration':kw['scene']['duration'],
                    'width':canvas['output_width'],'height':canvas['output_height'],'fps':24,'steps':12}}
        def mux(engine,clips,audio,target,*args,**kw):
            target.write_bytes(b'\x00\x00\x00\x18ftypisomnew');return {'duration':kw['audio_duration']}
        def fit(worker,body,*args,**kw):
            if body['op']=='fit_video':Path(body['output']).write_bytes(b'\x00\x00\x00\x18ftypisomnew')
            else:self.assertEqual(body['op'],'pad_import_audio')
            return {}
        with patch('h3chat.video_import.prepare'),patch.object(self.app.engine,'generate_video',side_effect=generate),patch.object(self.app.engine,'tool_call',side_effect=fit),patch('h3chat.soundtrack.probe',return_value={'duration':25}),patch('h3chat.soundtrack.compose',side_effect=mux):
            self.app.execute_job(self.app.store.one('SELECT * FROM jobs WHERE id=?',(ident,)),threading.Event())
        answer=self.app.store.chat(chat)['messages'][-1]
        self.assertEqual(answer['status'],'done',answer['meta'])
        self.assertEqual(offsets,[0,10,20])
        self.assertEqual([m['generation']['duration'] for m in answer['media']],[10,10,5])


if __name__=='__main__':unittest.main()

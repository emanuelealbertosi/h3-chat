import base64,json,subprocess,tempfile,threading,unittest
from pathlib import Path
from unittest.mock import patch
import test_video as fixture
from h3chat.video_edit import describe,request,source
from h3chat.video_import import prepare
from h3chat.video_recreate import load

ROOT=Path(__file__).resolve().parents[1]

@unittest.skipUnless((ROOT/'runtime/remix/ffmpeg.exe').is_file(),'Install Remix media for CPU integration tests')
class ExternalVideoTests(unittest.TestCase):
    setUp=fixture.VideoTests.setUp
    tearDown=fixture.VideoTests.tearDown

    def original(self,seconds=31):
        path=self.folder/'external.mp4'
        self.ff(['-f','lavfi','-i',f'testsrc2=size=128x72:rate=24:duration={seconds}',
            '-f','lavfi','-i',f'sine=frequency=220:sample_rate=48000:duration={seconds}',
            '-c:v','libx264','-pix_fmt','yuv420p','-c:a','aac','-shortest',path])
        media=self.app.upload({'name':'external.mp4','data':base64.b64encode(path.read_bytes()).decode()})
        return self.app.store.create_chat()['id'],media

    def ff(self,args):
        subprocess.run([str(ROOT/'runtime/remix/ffmpeg.exe'),'-y','-v','error','-nostdin',*map(str,args)],check=True,capture_output=True)

    def test_windows_cached_frames_gallery_and_scope(self):
        chat,media=self.original()
        first=describe(self.app,chat,media['id']);second=describe(self.app,chat,media['id'])
        self.assertTrue(first['imported']);self.assertEqual(first,second)
        self.assertEqual([(x['start'],x['end']) for x in first['clips']],[(0,15),(15,30),(30,31)])
        self.assertEqual([x['preview_start'] for x in first['clips']],[0,15,30])
        self.assertEqual([x['mode'] for x in first['clips']],['i2v']*3)
        value=source(self.app,chat,media['id'])
        for image in value['images']:
            self.assertEqual(self.app.store.gallery.get(image['id'])['path'],image['path'])
            self.assertEqual((self.app.data/image['path']).read_bytes()[:8],b'\x89PNG\r\n\x1a\n')
        p=value['record']['parameters'][0]
        self.assertGreaterEqual(p['canvas_width'],p['width']);self.assertGreaterEqual(p['canvas_height'],p['height'])
        self.assertNotEqual((p['width'],p['height']),(128,72))
        other=fixture.Service(ROOT,self.folder/'other-data',start_worker=False)
        try:
            with self.assertRaises(ValueError):describe(other,other.store.create_chat()['id'],media['id'])
        finally:other.close()

    def test_one_replacement_preserves_other_clips_audio_and_future_edits(self):
        chat,media=self.original();value=source(self.app,chat,media['id'])
        before=self.app.store.settings();calls=[]
        job_id=request(self.app,chat,{'source':media['id'],'assistant':False,'patches':[
            {'clip':2,'prompt':'Un sorriso e movimento della camera','mode':'i2v','start_image':2,'images':[2],'start':3,'end':4}]})['job_id']
        def generate(model,settings,plan,refs,job,cancel,stage,**kw):
            calls.append(kw['scene']);path=self.app.data/'outputs'/job/'video.mp4';path.parent.mkdir(parents=True,exist_ok=True)
            self.ff(['-f','lavfi','-i','color=c=red:s=256x144:r=24:d=1','-c:v','libx264','-pix_fmt','yuv420p',path])
            p=value['record']['parameters'][1]
            return {'path':path.relative_to(self.app.data).as_posix(),'generation':p|{'duration':1,'output_frames':24}}
        with patch.object(self.app.engine,'generate_video',side_effect=generate),patch.object(self.app.engine,'completion') as llm:
            self.app.execute_job(self.app.store.one('SELECT * FROM jobs WHERE id=?',(job_id,)),threading.Event())
        answer=self.app.store.chat(chat)['messages'][-1]
        self.assertEqual(answer['status'],'done',answer['meta']);self.assertEqual(len(calls),1);llm.assert_not_called()
        self.assertEqual((calls[0]['start'],calls[0]['duration']),(18,1))
        result=source(self.app,chat,job_id)
        self.assertEqual(result['source_size'],{'width':128,'height':72})
        self.assertEqual(result['record']['outputs'][0],value['record']['outputs'][0])
        self.assertEqual(result['record']['outputs'][2],value['record']['outputs'][2])
        self.assertEqual(result['audio']['id'],value['audio']['id'])
        self.assertEqual(result['duration'],31)
        self.assertEqual(result['record']['parameters'][1]['width'],value['record']['parameters'][1]['width'])
        self.assertEqual(self.app.store.settings(),before)
        with self.assertRaisesRegex(ValueError,'Modifica clip'):load(self.app,chat,job_id)

if __name__=='__main__':unittest.main()

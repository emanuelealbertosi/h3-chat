import base64,json,subprocess,tempfile,threading,unittest,wave
from pathlib import Path
from unittest.mock import patch
from h3chat.video_remix import validate,request
from h3chat import remix_runtime
from h3chat.residency import Session
import test_video as fixture

ROOT=Path(__file__).resolve().parents[1]

class RemixRequestTests(unittest.TestCase):
    setUp=fixture.VideoTests.setUp
    tearDown=fixture.VideoTests.tearDown
    def media(self):
        video=self.app.upload({'name':'test.mp4','data':base64.b64encode(b'\x00\x00\x00\x18ftypisom'+b'0'*24).decode()})
        audio=self.app.upload({'name':'test.wav','data':base64.b64encode(b'RIFF'+b'0'*4+b'WAVE'+b'0'*24).decode()})
        return video,audio
    def test_invalid_modes_and_numbers(self):
        for body in ({'mode':'bad'},{'start':True},{'end':float('nan')},{'reference_duration':0},{'gain_db':19},{'clone_voice':'yes'},{'mode':'voice'},{'mode':'clone','fit':'bad'},{'voice_fields':{'gender':'unknown'}}):
            with self.subTest(body=body),self.assertRaises(ValueError):validate(body)
    def test_request_is_owned_queued_and_captures_settings(self):
        chat=self.app.store.create_chat()['id'];video,audio=self.media();before=self.app.store.settings()
        with patch('h3chat.remix_runtime.ready',return_value={'media':True,'separation':True,'conversion':True,'score':True}),patch('h3chat.remix_runtime.settings',return_value=remix_runtime.DEFAULTS):
            ident=request(self.app,chat,{'mode':'audio','media':[video,audio],'audio':audio['id'],'start':1,'end':2})['job_id']
            payload=json.loads(self.app.store.one('SELECT payload FROM jobs WHERE id=?',(ident,))['payload'])
            self.assertEqual(payload['settings']['_video_remix']['video']['id'],video['id'])
            self.assertEqual(payload['settings']['_video_remix']['audio']['id'],audio['id'])
            with self.assertRaisesRegex(ValueError,'richiesta attiva'):request(self.app,chat,{'media':[video,audio],'audio':audio['id']})
        self.assertEqual(self.app.store.settings(),before)
        other=fixture.Service(ROOT,self.folder/'other-data',start_worker=False)
        try:
            with self.assertRaises(ValueError):request(other,other.store.create_chat()['id'],{'media':[video,audio],'audio':audio['id']})
        finally:other.close()
    def test_worker_runs_in_existing_service_queue_without_llm_or_video_generation(self):
        chat=self.app.store.create_chat()['id'];video,audio=self.media()
        with patch('h3chat.remix_runtime.ready',return_value={'media':True}):
            ident=request(self.app,chat,{'media':[video,audio],'audio':audio['id']})['job_id']
        def call(worker,body,*args,**kw):
            self.assertEqual(worker,'video-remix-worker.py')
            if body['op']=='probe':return {'duration':5,'has_audio':True}
            folder=Path(body['folder']);(folder/'remix.mp4').write_bytes(b'video');(folder/'audio.wav').write_bytes(b'audio')
            return {'duration':5}
        with patch.object(self.app.engine,'tool_call',side_effect=call),patch.object(self.app.engine,'completion') as llm,patch.object(self.app.engine,'generate_video') as gpu:
            self.app.execute_job(self.app.store.one('SELECT * FROM jobs WHERE id=?',(ident,)),threading.Event())
        answer=self.app.store.chat(chat)['messages'][-1]
        self.assertEqual(answer['status'],'done',answer['meta']);self.assertEqual(len(answer['media']),2)
        self.assertTrue(answer['meta']['remix']['video_stream_copied']);llm.assert_not_called();gpu.assert_not_called()

@unittest.skipUnless((ROOT/'runtime/remix/ffmpeg.exe').is_file(),'Install Remix media to run real CPU media tests')
class RemixMediaTests(unittest.TestCase):
    def setUp(self):
        (ROOT/'work').mkdir(exist_ok=True)
        self.tmp=tempfile.TemporaryDirectory(dir=ROOT/'work');self.folder=Path(self.tmp.name)
        self.source=self.folder/'source.mp4';self.new=self.folder/'new.wav';self.ff=ROOT/'runtime/remix/ffmpeg.exe'
        self.runff(['-f','lavfi','-i','testsrc2=size=128x72:rate=24:duration=3','-f','lavfi','-i','sine=frequency=220:sample_rate=48000:duration=3','-c:v','libx264','-pix_fmt','yuv420p','-c:a','aac','-shortest',self.source])
        self.runff(['-f','lavfi','-i','sine=frequency=880:sample_rate=48000:duration=1','-ac','2',self.new])
    def tearDown(self):self.tmp.cleanup()
    def runff(self,args):
        r=subprocess.run([str(self.ff),'-y','-v','error','-nostdin',*map(str,args)],capture_output=True)
        if r.returncode:raise RuntimeError(r.stderr.decode('utf-8','replace'))
        return r.stdout
    def call(self,op,**kw):
        session=Session(('remix',(),()),'tool',{}, {},{},self.folder/'worker.log')
        try:
            session.start([ROOT/'runtime/python/python.exe','-X','utf8',ROOT/'native/video-remix-worker.py'],ipc=True,cwd=ROOT)
            session.wait('hello',threading.Event(),30)
            session.send({'op':op,'runtime':remix_runtime.DEFAULTS|{'backend':'cpu'},'folder':str(self.folder),'source':str(self.source),**kw})
            return session.wait('result',threading.Event(),120)['result']
        finally:session.stop()
    def test_stream_copy_and_sample_exact_outer_audio(self):
        config=validate({'start':1,'end':2})
        result=self.call('render',replacement=str(self.new),config=config)
        self.assertAlmostEqual(result['duration'],3,places=2)
        first=self.runff(['-i',self.source,'-map','0:v:0','-c','copy','-f','h264','pipe:1'])
        second=self.runff(['-i',self.folder/'remix.mp4','-map','0:v:0','-c','copy','-f','h264','pipe:1'])
        self.assertEqual(first,second)
        with wave.open(str(self.folder/'remix-work/full-original.wav')) as a,wave.open(str(self.folder/'audio.wav')) as b:
            original=a.readframes(a.getnframes());patched=b.readframes(b.getnframes())
        self.assertEqual(patched[:48000*4],original[:48000*4]);self.assertEqual(patched[96000*4:],original[96000*4:])
        self.assertNotEqual(patched[50000*4:90000*4],original[50000*4:90000*4])
    def test_shorter_track_pads_and_longer_track_requires_explicit_fit(self):
        config=validate({'start':0,'end':.5})
        with self.assertRaisesRegex(RuntimeError,'non taglio le parole'):self.call('render',replacement=str(self.new),config=config)
        self.assertEqual(self.call('render',replacement=str(self.new),config=config|{'fit':'stretch'})['duration'],3)
        config=validate({'start':0,'end':2})
        self.call('render',replacement=str(self.new),config=config)
        with wave.open(str(self.folder/'audio.wav')) as a:
            a.setpos(60000);self.assertEqual(a.readframes(20000),b'\0'*(20000*4))
    def test_reference_is_an_exact_requested_excerpt(self):
        result=self.call('reference',reference=str(self.new),start=.2,duration=.5,separate=False)
        with wave.open(result['path']) as a:self.assertEqual(a.getnframes(),24000)
    def test_interrupted_external_import_replaces_incomplete_cache(self):
        cache=self.folder/'clip-001.mp4';cache.write_bytes(b'incomplete')
        result=self.call('import_clips',timeline=[{'index':0,'start':0,'duration':3,'frames':72}])
        self.assertEqual(result['clips'],1)
        before=cache.read_bytes();self.assertEqual(before[4:8],b'ftyp')
        self.call('import_clips',timeline=[{'index':0,'start':0,'duration':3,'frames':72}])
        self.assertEqual(cache.read_bytes(),before)
        self.assertFalse((self.folder/'clip-001.pending.mp4').exists())

if __name__=='__main__':unittest.main()

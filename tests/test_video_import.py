import base64,copy,json,subprocess,tempfile,threading,unittest
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

    def test_fractional_tail_can_be_selected_in_a_full_video_edit(self):
        chat,media=self.original(seconds=380/24)
        manifest=describe(self.app,chat,media['id'])
        self.assertEqual([(c['start'],c['end']) for c in manifest['clips']],[(0,356/24),(356/24,380/24)])
        self.assertEqual([c['preview_start'] for c in manifest['clips']],[0,356/24])
        value=source(self.app,chat,media['id'])
        from h3chat.video_edit import source_interval
        self.assertEqual(source_interval(value,{'clip':2})['frames'],24)
        self.assertEqual(source_interval(value,{'clip':2})['start'],356/24)
        ident=request(self.app,chat,{'source':media['id'],'assistant':False,
            'patches':[{'clip':n,'mode':'video','prompt':'Change only the outfit','images':[]} for n in (1,2)]})['job_id']
        payload=json.loads(self.app.store.one('SELECT payload FROM jobs WHERE id=?',(ident,))['payload'])
        self.assertEqual([p['clip'] for p in payload['settings']['_video_edit']['patches']],[1,2])
        self.assertEqual(value['duration'],380/24)
        cache,info=__import__('h3chat.video_import',fromlist=['metadata']).metadata(self.app,media)
        self.assertEqual(info['segmentation_version'],2)
        self.assertIn('layout-v2',cache.parts)

    def test_restart_recovers_only_missing_edits_with_original_import_boundaries(self):
        from h3chat.video_import import source as import_source
        from h3chat.downloads import Cancelled
        chat,media=self.original(seconds=740/24)
        legacy=import_source(self.app,media['id'],layout_version=1)
        legacy['record'].pop('import_layout_version') # checkpoint saved before layout versions existed
        with patch('h3chat.video_edit.source',return_value=copy.deepcopy(legacy)):
            ident=request(self.app,chat,{'source':media['id'],'assistant':False,'remount':False,
                'patches':[{'clip':n,'mode':'video','prompt':'Change only the outfit','images':[]} for n in (1,2)]})['job_id']
        seen=[]
        def generate(model,settings,plan,refs,job,cancel,stage,**kw):
            seen.append(kw['scene']['source_video']['start'])
            if len(seen)==2:raise Cancelled()
            path=self.app.data/'outputs'/job/'video.mp4';path.parent.mkdir(parents=True,exist_ok=True)
            self.ff(['-f','lavfi','-i','color=c=blue:s=128x72:r=24:d=15','-c:v','libx264','-pix_fmt','yuv420p',path])
            return {'path':path.relative_to(self.app.data).as_posix(),'generation':legacy['record']['parameters'][0]|{'duration':15,'width':128,'height':72,'output_frames':360}}
        with patch.object(self.app.engine,'generate_video',side_effect=generate),patch('h3chat.video_edit.source',return_value=copy.deepcopy(legacy)):
            self.app.execute_job(self.app.store.one('SELECT * FROM jobs WHERE id=?',(ident,)),threading.Event())
        checkpoint=json.loads((self.app.data/'outputs'/ident/'scenes.json').read_text())
        self.assertEqual(checkpoint['revision_completed'],[1]);first=checkpoint['outputs'][0]
        original_bytes=(self.app.data/first).read_bytes()
        # Normal startup marks the in-flight job interrupted; the newer importer
        # would otherwise move the last boundary and replace thumbnail identities.
        self.app.store.execute("UPDATE jobs SET status='interrupted' WHERE id=?",(ident,))
        self.app.store.execute("UPDATE messages SET status='interrupted' WHERE id=(SELECT message_id FROM jobs WHERE id=?)",(ident,))
        newer=import_source(self.app,media['id'])
        self.assertEqual(newer['record']['timeline'][2]['start'],716/24)
        retry=self.app.regenerate(chat)['job_id']
        payload=json.loads(self.app.store.one('SELECT payload FROM jobs WHERE id=?',(retry,))['payload'])
        self.assertEqual(payload['settings']['_video_resume'],ident)
        seen.clear()
        with patch.object(self.app.engine,'generate_video',side_effect=generate) as gpu:
            self.app.execute_job(self.app.store.one('SELECT * FROM jobs WHERE id=?',(retry,)),threading.Event())
        self.assertEqual(self.app.store.chat(chat)['messages'][-1]['status'],'done')
        gpu.assert_called_once();self.assertEqual(seen,[15])
        saved=json.loads((self.app.data/'outputs'/retry/'scenes.json').read_text())
        self.assertEqual(saved['outputs'][0],first);self.assertEqual((self.app.data/first).read_bytes(),original_bytes)
        self.assertEqual(saved['revision_completed'],[1,2]);self.assertEqual(saved['timeline'][2]['start'],30)
        self.assertEqual(saved['timeline'][2]['frames'],20)

    def test_ten_second_windows_have_separate_cache_and_exact_source_offsets(self):
        chat,media=self.original(seconds=31)
        fifteen=describe(self.app,chat,media['id'])
        ten=describe(self.app,chat,media['id'],10)
        self.assertEqual(ten['segment_seconds'],10)
        self.assertEqual([(c['start'],c['end']) for c in ten['clips']],[(0,10),(10,20),(20,30),(30,31)])
        self.assertEqual([c['preview_start'] for c in ten['clips']],[0,10,20,30])
        self.assertEqual(fifteen,describe(self.app,chat,media['id'],15))
        self.assertEqual(ten,describe(self.app,chat,media['id'],10))
        value=source(self.app,chat,media['id'],10)
        self.assertTrue(all('/segments-10/' in p for p in value['record']['outputs']))
        self.assertEqual(value['record']['timeline'][1]['frames'],240)
        from h3chat.video_edit import source_interval
        self.assertEqual(source_interval(value,{'clip':2,'start':2,'end':4})['start'],12)
        self.assertEqual(source_interval(value,{'clip':2,'start':2,'end':4})['frames'],48)
        for invalid in (True,8,12,'10'):
            with self.assertRaisesRegex(ValueError,'10 o 15'):describe(self.app,chat,media['id'],invalid)

    def test_ten_second_edit_retains_its_segmentation_when_reopened(self):
        chat,media=self.original(seconds=31)
        value=source(self.app,chat,media['id'],10)
        ident=request(self.app,chat,{'source':media['id'],'segment_seconds':10,'assistant':False,'remount':False,
            'patches':[{'clip':2,'mode':'video','prompt':'Change jacket','images':[]}]})['job_id']
        payload=json.loads(self.app.store.one('SELECT payload FROM jobs WHERE id=?',(ident,))['payload'])
        self.assertEqual(payload['settings']['_video_edit']['segment_seconds'],10)
        def generate(model,settings,plan,refs,job,cancel,stage,**kw):
            self.assertEqual(kw['scene']['source_video']['start'],10)
            self.assertEqual(kw['scene']['source_video']['frames'],240)
            path=self.app.data/'outputs'/job/'video.mp4';path.parent.mkdir(parents=True)
            self.ff(['-f','lavfi','-i','color=c=red:s=128x72:r=24:d=10','-c:v','libx264','-pix_fmt','yuv420p',path])
            return {'path':path.relative_to(self.app.data).as_posix(),'generation':value['record']['parameters'][1]|{'duration':10}}
        with patch.object(self.app.engine,'generate_video',side_effect=generate):
            self.app.execute_job(self.app.store.one('SELECT * FROM jobs WHERE id=?',(ident,)),threading.Event())
        self.assertEqual(self.app.store.chat(chat)['messages'][-1]['status'],'done')
        saved=describe(self.app,chat,ident)
        self.assertTrue(saved['working_timeline']);self.assertEqual(saved['segment_seconds'],10)
        self.assertEqual([(c['start'],c['end']) for c in saved['clips']],[(0,10),(10,20),(20,30),(30,31)])
        self.assertEqual(saved,describe(self.app,chat,ident,15))
        self.assertAlmostEqual(self.app.store.chat(chat)['messages'][-1]['media'][0]['generation']['audio_start'],10)

    def test_clip_only_keeps_external_working_timeline_without_full_assembly(self):
        chat,media=self.original(seconds=20);value=source(self.app,chat,media['id'])
        ident=request(self.app,chat,{'source':media['id'],'assistant':False,'remount':False,
            'patches':[{'clip':2,'prompt':'Slow camera movement','mode':'i2v','start_image':2,'start':1,'end':3}]})['job_id']
        def generate(model,settings,plan,refs,job,cancel,stage,**kw):
            self.assertEqual((kw['scene']['start'],kw['scene']['duration']),(16,2))
            path=self.app.data/'outputs'/job/'video.mp4';path.parent.mkdir(parents=True)
            self.ff(['-f','lavfi','-i','color=c=red:s=256x144:r=24:d=2','-c:v','libx264','-pix_fmt','yuv420p',path])
            return {'path':path.relative_to(self.app.data).as_posix(),'generation':value['record']['parameters'][1]|{'duration':2,'width':256,'height':144,'output_frames':48}}
        with patch.object(self.app.engine,'generate_video',side_effect=generate),patch.object(self.app.engine,'tool_call',wraps=self.app.engine.tool_call) as tools:
            self.app.execute_job(self.app.store.one('SELECT * FROM jobs WHERE id=?',(ident,)),threading.Event())
        self.assertTrue(any(c.args[0]=='video-splice-worker.py' for c in tools.call_args_list))
        self.assertTrue(any(c.args[1].get('op')=='fit_video' for c in tools.call_args_list))
        answer=self.app.store.chat(chat)['messages'][-1];self.assertEqual(answer['status'],'done',answer['meta'])
        clip=answer['media'][0];self.assertAlmostEqual(clip['generation']['duration'],2,places=2)
        self.assertEqual(clip['generation']['audio_start'],16)
        self.assertFalse((self.app.data/value['record']['outputs'][0]).is_file())
        self.assertTrue((self.app.data/value['record']['outputs'][1]).is_file())
        self.assertFalse((self.app.data/'outputs'/ident/'video.mp4').exists())
        saved=describe(self.app,chat,ident)
        self.assertTrue(saved['working_timeline']);self.assertEqual(saved['duration'],20)
        self.assertEqual(saved['edited_clips'],[2]);self.assertTrue(saved['clips'][1]['edited'])
        self.assertEqual(saved['clips'][1]['preview_start'],0)
        self.assertIn('edited.mp4',saved['clips'][1]['url'])
        self.assertEqual(saved['clips'][0]['url'],'/media/'+media['path'])
        self.assertTrue(saved['clips'][0]['source_interval'])
        imports=[c.args[1] for c in tools.call_args_list if c.args[1].get('op')=='import_clips']
        self.assertEqual([[s['index'] for s in c['timeline']] for c in imports],[[1]])
        # The delivered MP4 itself can be reopened in the clip editor via gallery.
        manifest=describe(self.app,chat,clip['id']);self.assertEqual(len(manifest['clips']),1)
        self.assertAlmostEqual(manifest['duration'],2,places=2)
        from h3chat.video_assemble import request as assemble
        from h3chat.video_import import invoke
        final=assemble(self.app,chat,{'source':ident})['job_id']
        with patch.object(self.app.engine,'generate_video') as gpu,patch.object(self.app.engine,'completion') as llm:
            self.app.execute_job(self.app.store.one('SELECT * FROM jobs WHERE id=?',(final,)),threading.Event())
        gpu.assert_not_called();llm.assert_not_called()
        answer=self.app.store.chat(chat)['messages'][-1];self.assertEqual(answer['status'],'done',answer['meta'])
        result=invoke(self.app,{'op':'probe','runtime':{'backend':'cpu','threads':4},'folder':str(self.folder),
            'source':str(self.app.data/answer['media'][0]['path'])})
        self.assertAlmostEqual(result['duration'],20,places=2)
        self.assertEqual((result['width'],result['height']),(128,72));self.assertTrue(result['has_audio'])

    def test_whole_clip_only_edit_does_not_extract_other_intervals(self):
        chat,media=self.original(seconds=31);value=source(self.app,chat,media['id'])
        ident=request(self.app,chat,{'source':media['id'],'assistant':False,'remount':False,
            'patches':[{'clip':2,'mode':'video','prompt':'Change the costume','images':[]}]})['job_id']
        def generate(model,settings,plan,refs,job,cancel,stage,**kw):
            self.assertEqual(kw['scene']['source_video']['path'],media['path'])
            self.assertEqual(kw['scene']['source_video']['start'],15)
            path=self.app.data/'outputs'/job/'video.mp4';path.parent.mkdir(parents=True)
            self.ff(['-f','lavfi','-i','color=c=red:s=128x72:r=24:d=15','-c:v','libx264','-pix_fmt','yuv420p',path])
            return {'path':path.relative_to(self.app.data).as_posix(),'generation':value['record']['parameters'][1]|{'duration':15}}
        with patch.object(self.app.engine,'generate_video',side_effect=generate) as gpu,patch.object(self.app.engine,'tool_call',wraps=self.app.engine.tool_call) as tools:
            self.app.execute_job(self.app.store.one('SELECT * FROM jobs WHERE id=?',(ident,)),threading.Event())
        self.assertEqual(self.app.store.chat(chat)['messages'][-1]['status'],'done')
        gpu.assert_called_once()
        self.assertFalse(any(c.args[1].get('op')=='import_clips' for c in tools.call_args_list))
        self.assertFalse(any((self.app.data/p).is_file() for p in value['record']['outputs']))
        saved=source(self.app,chat,ident)
        self.assertIsNotNone(saved['record']['clip_sources'][0]);self.assertIsNone(saved['record']['clip_sources'][1])
        self.assertIsNotNone(saved['record']['clip_sources'][2])
        from h3chat.video_edit import source_interval
        self.assertEqual(source_interval(saved,{'clip':3})['start'],30)
        self.assertEqual(source_interval(saved,{'clip':3})['path'],media['path'])

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

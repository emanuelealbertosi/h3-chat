import importlib.util
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
from fractions import Fraction
import av
import numpy as np
from h3chat import upscale,upscale_runtime
from h3chat.workspaces import guest_allowed

spec=importlib.util.spec_from_file_location('upscale_worker',Path(__file__).resolve().parents[1]/'native/upscale-worker.py')
worker=importlib.util.module_from_spec(spec);spec.loader.exec_module(worker)

class UpscaleTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
    def tearDown(self):self.tmp.cleanup()

    def make(self,path,vfr=False,audio=True,rotation=0,video_offset=0):
        stamps=[Fraction(i,24)+(Fraction(1,24) if vfr and i>=20 else 0) for i in range(48)]
        with av.open(str(path),'w') as output:
            video=output.add_stream('libx264',rate=24);video.width=64;video.height=48;video.pix_fmt='yuv420p';video.options={'bf':'0'}
            video.time_base=Fraction(1,90000);video.codec_context.time_base=Fraction(1,90000)
            if rotation:video.set_display_rotation(rotation)
            sound=output.add_stream('aac',rate=48000) if audio else None
            if sound:sound.layout='stereo'
            for i,stamp in enumerate(stamps):
                array=np.full((48,64,3),40+i,np.uint8);frame=av.VideoFrame.from_ndarray(array,format='rgb24');frame.pts=round((stamp+video_offset)*90000);frame.time_base=Fraction(1,90000)
                for packet in video.encode(frame):output.mux(packet)
            for packet in video.encode(None):output.mux(packet)
            if sound:
                for i in range(100):
                    values=np.sin((np.arange(1024)+i*1024)*2*np.pi*440/48000).astype('float32')*.15
                    frame=av.AudioFrame.from_ndarray(np.stack([values,values]),format='fltp',layout='stereo');frame.sample_rate=48000;frame.pts=i*1024;frame.time_base=Fraction(1,48000)
                    for packet in sound.encode(frame):output.mux(packet)
                for packet in sound.encode(None):output.mux(packet)
        return stamps

    def request(self,source,**extra):
        config=upscale_runtime.DEFAULTS|{'engine':'rtx','preview':False,'start':0,'duration':None}|extra
        result={'source':str(source),'output':str(self.root/'new.mp4'),'cache':str(self.root/'cache'),'config':config}
        return result

    @staticmethod
    def processor(config,width,height):
        return lambda arrays,overlap:[np.repeat(np.repeat(a,2,axis=0),2,axis=1) for a in arrays[overlap:]],lambda:None

    def timestamps(self,path):
        with av.open(str(path)) as source:return [float(f.pts*f.time_base) for f in source.decode(video=0)]

    def audio_packets(self,path):
        with av.open(str(path)) as source:return [(p.pts,p.dts,bytes(p)) for p in source.demux(source.streams.audio[0]) if p.dts is not None]

    def test_vfr_aspect_frame_count_and_audio_are_preserved(self):
        source=self.root/'source.mp4';self.make(source,vfr=True);before=source.read_bytes()
        result=worker.upscale(self.request(source),self.processor)
        self.assertEqual((result['width'],result['height'],result['frames']),(128,96,48))
        self.assertTrue(result['audio_preserved'])
        self.assertTrue(np.allclose(self.timestamps(source),self.timestamps(self.root/'new.mp4'),atol=1/90000))
        old=self.audio_packets(source);new=self.audio_packets(self.root/'new.mp4')
        self.assertEqual([p[2] for p in old],[p[2] for p in new])
        self.assertEqual(source.read_bytes(),before)

    def test_resume_reuses_completed_blocks_and_rejects_changed_source(self):
        source=self.root/'source.mp4';self.make(source);request=self.request(source)
        calls=[]
        def broken(config,width,height):
            def run(arrays,overlap):
                calls.append(len(arrays))
                if len(calls)==2:raise RuntimeError('interrupted')
                return self.processor(config,width,height)[0](arrays,overlap)
            return run,lambda:None
        with self.assertRaisesRegex(RuntimeError,'interrupted'):worker.upscale(request,broken)
        self.assertFalse((self.root/'new.mp4').exists())
        saved=json.loads((self.root/'cache/checkpoint.json').read_text());self.assertEqual(len(saved['chunks']),1)
        counts=[]
        def resumed(config,w,h):
            def run(arrays,overlap):counts.append(len(arrays));return self.processor(config,w,h)[0](arrays,overlap)
            return run,lambda:None
        worker.upscale(request,resumed);self.assertEqual(counts,[16])
        source.touch()
        with self.assertRaisesRegex(ValueError,'cambiati'):worker.upscale(request,self.processor)

    def test_preview_audio_does_not_repeat_frames(self):
        source=self.root/'source.mp4';self.make(source)
        request=self.request(source,preview=True,start=.5,duration=1.5)
        calls=[]
        def processor(config,w,h):
            def run(arrays,overlap):calls.append((len(arrays),overlap));return self.processor(config,w,h)[0](arrays,overlap)
            return run,lambda:None
        result=worker.upscale(request,processor)
        self.assertEqual(result['frames'],36);self.assertEqual(calls,[(32,0),(4,0)])
        with av.open(str(self.root/'new.mp4')) as output:
            frames=list(output.decode(video=0));self.assertAlmostEqual(float(frames[0].pts*frames[0].time_base),0,places=4)
        with av.open(str(self.root/'new.mp4')) as output:
            sound=list(output.decode(audio=0));self.assertGreater(len(sound),20)
            self.assertGreater(np.abs(sound[10].to_ndarray()).max(),.05)
        self.assertAlmostEqual(result['duration'],1.5,places=4)

    def test_no_audio_stays_silent_and_invalid_target_keeps_original(self):
        source=self.root/'source.mp4';self.make(source,audio=False);request=self.request(source)
        result=worker.upscale(request,self.processor);self.assertFalse(result['audio_preserved'])
        with self.assertRaises(ValueError):worker.dimensions(1920,1080,'1080p')
        with self.assertRaises(ValueError):worker.dimensions(3840,2160,'4x')

    def test_resume_detects_corruption_even_when_the_size_is_unchanged(self):
        source=self.root/'source.mp4';self.make(source);request=self.request(source)
        worker.upscale(request,self.processor)
        chunk=self.root/'cache/chunk-000001.mp4';original=chunk.read_bytes();chunk.write_bytes(original[:-1]+bytes([original[-1]^1]))
        with self.assertRaisesRegex(ValueError,'blocco salvato'):worker.upscale(request,self.processor)

    def test_phone_video_display_rotation_is_preserved(self):
        source=self.root/'source.mp4';self.make(source,audio=False,rotation=90)
        worker.upscale(self.request(source),self.processor)
        with av.open(str(source)) as before, av.open(str(self.root/'new.mp4')) as after:
            self.assertEqual(next(before.decode(video=0)).rotation,next(after.decode(video=0)).rotation)

    def test_audio_that_starts_before_video_keeps_its_lead(self):
        source=self.root/'source.mp4';self.make(source,video_offset=1)
        result=worker.upscale(self.request(source),self.processor)
        self.assertEqual(result['frames'],48);self.assertAlmostEqual(result['duration'],3,places=4)
        self.assertTrue(np.allclose(self.timestamps(source),self.timestamps(self.root/'new.mp4'),atol=1/90000))
        self.assertEqual(self.audio_packets(source),self.audio_packets(self.root/'new.mp4'))

    def test_options_admin_paths_and_guest_permissions(self):
        with self.assertRaises(ValueError):upscale.options(self.root,{'options':{'seed_model':'private.safetensors'}})
        for body in ({'start':float('nan')},{'preview':'yes'},{'options':{'crf':13}}):
            with self.assertRaises(ValueError):upscale.options(self.root,body)
        self.assertTrue(guest_allowed('/api/chats/123/upscale','POST'))
        self.assertFalse(guest_allowed('/api/upscale/settings','GET'))
        self.assertEqual(upscale_runtime.describe(self.root)['settings'],upscale_runtime.DEFAULTS)

    def test_old_defaults_migrate_but_removed_engine_requests_are_rejected(self):
        folder=self.root/'data';folder.mkdir()
        (folder/'upscale.json').write_text(json.dumps({'engine':'seed','target':'1440p','seed_model':'old.safetensors','seed_batch':9,'rtx_quality':'ultra','crf':20}))
        self.assertEqual(upscale_runtime.settings(self.root),{'engine':'rtx','target':'1440p','rtx_quality':'ultra','crf':20})
        with self.assertRaisesRegex(ValueError,'rimosso'):upscale.options(self.root,{'options':{'engine':'seed'}})
        with self.assertRaisesRegex(ValueError,'disponibile'):worker.upscale({'config':{'engine':'seed'}})
        self.assertFalse(upscale_runtime.ready(self.root,'upscale_seed'))

    def test_queue_uses_resolved_media_and_disables_assistant_rag(self):
        from types import SimpleNamespace
        calls=[];media={'id':'a'*32,'mime':'video/mp4','path':'outputs/v.mp4','name':'v.mp4'}
        store=SimpleNamespace(settings=lambda:{'chat_model':'unused'},chat=lambda ident:calls.append(('chat',ident)),enqueue=lambda *args:calls.append(('enqueue',args)) or 'job')
        app=SimpleNamespace(root=self.root,store=store,wake=threading.Event(),validate_media=lambda items,canvas:media and [media],validate_settings=lambda value:{'chat_model':'unused'})
        with patch.object(upscale_runtime,'ready',return_value=True),patch.object(upscale_runtime,'describe',return_value={'ready':{'base':True}}):result=upscale.request(app,'chat',{'media':[{'id':media['id']}]})
        settings=calls[-1][1][3];self.assertFalse(settings['_assistant']);self.assertFalse(settings['_rag']);self.assertEqual(result['job_id'],'job');self.assertTrue(app.wake.is_set())
        self.assertEqual(calls[-1][1][2],[media])

if __name__=='__main__':unittest.main()

"""Duration validation is independent of the GPU generation clip limits."""
import tempfile,unittest,json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock,patch
from h3chat.video_import import validate_metadata,import_timeout,metadata,source

class VideoImportLimitTests(unittest.TestCase):
    def test_ready_import_opens_even_while_another_conversion_holds_lock(self):
        from h3chat.video_import import LOCK
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);source=root/'uploads/video.mp4';source.parent.mkdir();source.write_bytes(b'video')
            cache=root/'outputs/video-imports'/('a'*32)/'layout-v2';cache.mkdir(parents=True)
            frame=cache/'frame.png';frame.write_bytes(b'image');(cache/'audio.wav').write_bytes(b'audio')
            stat=source.stat();manifest={'fingerprint':[stat.st_size,stat.st_mtime_ns],'segment_seconds':15,'segmentation_version':2,'images':[{'path':str(frame)}]}
            (cache/'import.json').write_text(json.dumps(manifest));app=SimpleNamespace(root=root,data=root)
            class BusyLock:
                def __enter__(self):raise AssertionError('A cached restore must not wait for conversion')
                def __exit__(self,*args):pass
            with patch('h3chat.remix_runtime.ready',return_value={'media':True}),patch('h3chat.video_import.LOCK',BusyLock()),patch('h3chat.video_import.invoke') as worker:
                self.assertEqual(metadata(app,{'id':'a'*32,'path':'uploads/video.mp4'})[1],manifest);worker.assert_not_called()
    def info(self,duration):return {'duration':duration,'width':1920,'height':1080}

    def test_long_external_footage_has_no_ten_minute_duration_ceiling(self):
        for duration in (601,1800,3600,7200,86400):
            with self.subTest(duration=duration):
                value=self.info(duration)
                self.assertIs(validate_metadata(value),value)

    def test_invalid_probe_duration_and_audio_only_are_rejected(self):
        for duration in (True,None,'900',0,.5,-1,float('nan'),float('inf'),1e308):
            with self.subTest(duration=duration),self.assertRaisesRegex(ValueError,'durata leggibile'):
                validate_metadata(self.info(duration))
        with self.assertRaisesRegex(ValueError,'traccia video'):
            validate_metadata(self.info(1800)|{'width':0})

    def test_preparation_deadline_scales_for_longer_and_more_segmented_footage(self):
        self.assertEqual(import_timeout(self.info(15)),120)
        self.assertGreater(import_timeout(self.info(3600)),120)
        self.assertGreater(import_timeout(self.info(7200)),import_timeout(self.info(3600)))
        self.assertGreater(import_timeout(self.info(3600),10),import_timeout(self.info(3600),15))
        with self.assertRaisesRegex(ValueError,'10 o 15'):import_timeout(self.info(3600),12)

    def test_long_import_controller_passes_a_scaled_deadline_to_cpu_preparation(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);(root/'data/uploads').mkdir(parents=True)
            (root/'data/uploads/video.mp4').write_bytes(b'fixture')
            app=SimpleNamespace(root=root,data=root/'data');item={'id':'a'*32,'path':'uploads/video.mp4'}
            info=self.info(3600)|{'has_audio':True}
            with patch('h3chat.remix_runtime.ready',return_value={'media':True}),patch('h3chat.video_import.invoke',side_effect=[info,info]) as worker:
                _,result=metadata(app,item,10)
            self.assertEqual(result['duration'],3600)
            self.assertEqual(worker.call_args_list[0].args[1]['op'],'probe')
            self.assertEqual(worker.call_args_list[1].args[1]['segment_seconds'],10)
            self.assertEqual(worker.call_args_list[1].kwargs['timeout'],1080)

    def test_hour_long_timeline_and_late_source_interval_preserve_full_duration(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);app=SimpleNamespace(root=root,data=root/'data',store=Mock(),engine=Mock())
            item={'id':'b'*32,'path':'uploads/long.mp4','mime':'video/mp4'}
            app.store.gallery.get.return_value=item
            app.store.settings.return_value={'video_model':'h3'}
            app.engine.require_model.return_value={'id':'h3'}
            info=self.info(3601)|{'audio_id':'audio','images':[{'id':str(i),'path':str(app.data/f'frame-{i}.png')} for i in range(361)]}
            with patch('h3chat.video_import.metadata',return_value=(app.data/'import-cache',info)):
                value=source(app,item['id'],10)
            self.assertEqual(value['duration'],3601)
            self.assertEqual(len(value['record']['timeline']),361)
            self.assertEqual(sum(s['frames'] for s in value['record']['timeline']),3601*24)
            self.assertEqual(value['record']['timeline'][-1]['duration'],1)
            from h3chat.video_edit import source_interval
            interval=source_interval(value,{'clip':200,'start':1,'end':4})
            self.assertEqual(interval['path'],item['path'])
            self.assertEqual(interval['start'],1991)
            self.assertEqual(interval['frames'],72)

if __name__=='__main__':unittest.main()

import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest
import wave

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'runtime/tools/documents'))


def module(name,file):
    spec=importlib.util.spec_from_file_location(name,ROOT/'native'/file)
    result=importlib.util.module_from_spec(spec);spec.loader.exec_module(result);return result


@unittest.skipUnless((ROOT/'runtime/remix/ffmpeg.exe').is_file(),'Optional FFmpeg media runtime is not installed.')
class ExtensionWorkerTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.folder=Path(self.tmp.name)
        self.worker=module('extension_worker','video-extension-worker.py')
    def tearDown(self):self.tmp.cleanup()

    def test_audio_insert_preserves_exact_original_offsets_before_and_after(self):
        import numpy as np
        def write(name,samples):
            path=self.folder/name
            with wave.open(str(path),'wb') as out:
                out.setnchannels(1);out.setsampwidth(2);out.setframerate(48000);out.writeframes(samples.astype('<i2').tobytes())
            return path
        original=write('original.wav',np.repeat(np.arange(1,9)*1000,48000));new=write('new.wav',np.full(5*48000,12000))
        for cut in (0,2,6):
            output=self.folder/f'joined-{cut}.wav'
            result=self.worker.audio({'original':str(original),'new':str(new),'output':str(output),'audio_start':1,'total':6,'cut':cut,'duration':5})
            self.assertAlmostEqual(result['duration'],11)
            with wave.open(str(output),'rb') as out:
                samples=np.frombuffer(out.readframes(out.getnframes()),dtype='<i2').reshape(-1,2)[:,0]
            expected=[*(np.arange(2,2+cut)*1000),*([12000]*5),*(np.arange(2+cut,8)*1000)]
            # Mono -> stereo gains are deterministic; compare ratios, not loudness.
            actual=[float(samples[int((i+.5)*48000)]) for i in range(11)]
            gain=actual[cut]/12000
            for a,b in zip(actual,expected):self.assertAlmostEqual(a,b*gain,delta=2)

    def test_mov_is_readable_and_browser_preview_keeps_original(self):
        import av
        import numpy as np
        source=self.folder/'source.mov'
        with av.open(str(source),'w',format='mov') as out:
            stream=out.add_stream('mpeg4',rate=24);stream.width=160;stream.height=96;stream.pix_fmt='yuv420p'
            sound=out.add_stream('pcm_s16le',rate=48000);sound.layout='mono'
            for i in range(48):
                pixels=np.empty((96,160,3),dtype='uint8');pixels[:]=[20,30,240] if i<24 else [240,20,30]
                for packet in stream.encode(av.VideoFrame.from_ndarray(pixels,format='rgb24')):out.mux(packet)
            for packet in stream.encode(None):out.mux(packet)
            frame=av.AudioFrame.from_ndarray(np.full((1,96000),5000,dtype='<i2'),format='s16',layout='mono');frame.sample_rate=48000
            for packet in sound.encode(frame):out.mux(packet)
            for packet in sound.encode(None):out.mux(packet)
        before=source.read_bytes()
        paths=self.worker.frames({'source':str(source),'start':24/24,'frames':5,'folder':str(self.folder/'frames')})['paths']
        from PIL import Image
        self.assertEqual(len(paths),5)
        for path in paths:self.assertEqual(np.argmax(np.asarray(Image.open(path))[48,80]),0)
        preview=self.folder/'preview.mp4';browser=module('browser_worker','video-browser-worker.py')
        browser.render({'source':str(source),'output':str(preview)})
        with av.open(str(preview)) as video:
            self.assertEqual(video.streams.video[0].codec_context.name,'h264')
            self.assertEqual(len(list(video.decode(video=0))),48)
        with av.open(str(preview)) as video:
            self.assertEqual(video.streams.audio[0].codec_context.name,'aac')
            self.assertGreater(max(float(np.max(np.abs(frame.to_ndarray()))) for frame in video.decode(audio=0)),.05)
        self.assertEqual(source.read_bytes(),before)


if __name__=='__main__':unittest.main()

"""Real media checks: source offsets, exact frames, audio and fitting without GPU."""
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
import wave

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'runtime/tools/documents'))


@unittest.skipUnless((ROOT/'runtime/remix/ffmpeg.exe').is_file(),'FFmpeg runtime unavailable')
class ClipWorkerTests(unittest.TestCase):
    def setUp(self):
        import av
        import numpy as np
        self.tmp=tempfile.TemporaryDirectory();self.folder=Path(self.tmp.name)
        spec=importlib.util.spec_from_file_location('clip_worker',ROOT/'native/video-clip-worker.py')
        self.worker=importlib.util.module_from_spec(spec);spec.loader.exec_module(self.worker)
        self.source=self.folder/'source.mp4';self.audio=self.folder/'audio.wav'
        with av.open(str(self.source),'w') as out:
            stream=out.add_stream('libx264',rate=24);stream.width=320;stream.height=180;stream.pix_fmt='yuv420p'
            for i in range(96):
                color=[(240,20,20),(20,240,20),(20,20,240),(240,240,20)][i//24]
                pixels=np.empty((180,320,3),dtype='uint8');pixels[:]=color
                frame=av.VideoFrame.from_ndarray(pixels,format='rgb24')
                for packet in stream.encode(frame):out.mux(packet)
            for packet in stream.encode(None):out.mux(packet)
        samples=np.concatenate([np.sin(2*np.pi*f*np.arange(48000)/48000)*12000 for f in (440,660,880,1100)]).astype('<i2')
        with wave.open(str(self.audio),'wb') as out:
            out.setnchannels(1);out.setsampwidth(2);out.setframerate(48000);out.writeframes(samples.tobytes())

    def tearDown(self):self.tmp.cleanup()

    def test_exact_interval_and_original_soundtrack_offset(self):
        import av
        import numpy as np
        output=self.folder/'excerpt.mp4'
        result=self.worker.render({'source':str(self.source),'start':1,'frames':48,'width':320,'height':180,
            'audio':str(self.audio),'audio_start':1,'output':str(output)})
        self.assertEqual((result['frames'],result['fps'],result['duration']),(48,24,2))
        with av.open(str(output)) as media:
            frames=list(media.decode(video=0))
            self.assertEqual(np.argmax(frames[0].to_ndarray(format='rgb24')[90,160]),1)
            self.assertEqual(np.argmax(frames[-1].to_ndarray(format='rgb24')[90,160]),2)
        with av.open(str(output)) as media:
            samples=np.concatenate([frame.to_ndarray()[0] for frame in media.decode(audio=0)])
        self.assertGreater(float(np.sqrt(np.mean(samples*samples))),.05)
        segment=samples[12000:24000];peak=np.argmax(abs(np.fft.rfft(segment))) * 48000/len(segment)
        self.assertAlmostEqual(peak,660,delta=8)

    def test_fitting_preserves_duration_and_aspect_and_rejects_short_input(self):
        import av
        import numpy as np
        output=self.folder/'fitted.mp4'
        result=self.worker.render({'source':str(self.source),'frames':24,'width':320,'height':240,'output':str(output)})
        self.assertEqual((result['frames'],result['width'],result['height']),(24,320,240))
        with av.open(str(output)) as media:
            frame=next(media.decode(video=0)).to_ndarray(format='rgb24')
        self.assertLess(float(frame[5].mean()),3)
        self.assertGreater(float(frame[120,:,0].mean()),200)
        with self.assertRaisesRegex(ValueError,'troppo corto'):
            self.worker.render({'source':str(self.source),'start':3,'frames':48,'width':320,'height':180,'output':str(self.folder/'short.mp4')})
        self.assertFalse((self.folder/'short.mp4').exists())
        self.assertFalse(output.with_suffix('.pending.mp4').exists())


if __name__=='__main__':unittest.main()

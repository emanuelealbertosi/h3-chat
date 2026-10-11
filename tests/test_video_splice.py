import importlib.util
from fractions import Fraction
from pathlib import Path
import tempfile
import unittest
import av
import numpy as np

spec=importlib.util.spec_from_file_location('video_splice',Path(__file__).resolve().parents[1]/'native/video-splice-worker.py')
worker=importlib.util.module_from_spec(spec);spec.loader.exec_module(worker)


class VideoSpliceTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.original=self.root/'original.mp4';self.new=self.root/'new.mp4';self.output=self.root/'edited.mp4'
        self.make(self.original,96,False);self.make(self.new,24,True)

    def tearDown(self):self.tmp.cleanup()

    def make(self,path,frames,blue,width=64,fps=24):
        with av.open(str(path),'w') as out:
            stream=out.add_stream('libx264',rate=fps);stream.width=width;stream.height=64;stream.pix_fmt='yuv420p';stream.options={'crf':'0','preset':'ultrafast'}
            for i in range(frames):
                pixels=np.zeros((64,width,3),dtype=np.uint8)
                pixels[:,:,2 if blue else 0]=180 if blue else 80+i
                frame=av.VideoFrame.from_ndarray(pixels,format='rgb24');frame.pts=i;frame.time_base=Fraction(1,fps)
                for packet in stream.encode(frame):out.mux(packet)
            for packet in stream.encode(None):out.mux(packet)

    def pixels(self,path):
        with av.open(str(path)) as src:return np.array([frame.to_ndarray(format='rgb24').mean(axis=(0,1)) for frame in src.decode(video=0)])

    def test_middle_prefix_and_suffix_are_kept_without_retiming(self):
        before=self.original.read_bytes()
        for first,last in ((24,48),(0,24),(72,96)):
            with self.subTest(first=first):
                result=worker.splice(str(self.original),str(self.new),str(self.output),first,last,96)
                values=self.pixels(self.output);old=self.pixels(self.original)
                self.assertEqual(len(values),96);self.assertEqual(result['duration'],4)
                self.assertTrue(np.all(values[first:last,2]>160))
                self.assertTrue(np.all(values[first:last,0]<10))
                self.assertTrue(np.allclose(values[:first],old[:first],atol=5))
                self.assertTrue(np.allclose(values[last:],old[last:],atol=5))
                with av.open(str(self.output)) as output:self.assertFalse(output.streams.audio)
        self.assertEqual(self.original.read_bytes(),before)

    def test_wrong_length_format_and_original_length_fail_atomically(self):
        for frames,width,fps,total in ((23,64,24,96),(25,64,24,96),(24,96,24,96),(24,64,30,96),(24,64,24,95),(24,64,24,97)):
            with self.subTest(frames=frames,width=width,fps=fps,total=total):
                self.make(self.new,frames,True,width,fps)
                with self.assertRaises(ValueError):worker.splice(str(self.original),str(self.new),str(self.output),24,48,total)
                self.assertFalse(self.output.exists());self.assertFalse(self.output.with_suffix('.partial.mp4').exists())

    def test_invalid_interval_and_overwriting_source_rejected(self):
        for first,last,total in ((-1,24,96),(0,97,96),(24,24,96),(True,24,96),(0,24,361)):
            with self.assertRaises(ValueError):worker.splice(str(self.original),str(self.new),str(self.output),first,last,total)
        with self.assertRaises(ValueError):worker.splice(str(self.original),str(self.new),str(self.original),24,48,96)


if __name__=='__main__':unittest.main()

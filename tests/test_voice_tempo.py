import importlib.util
from pathlib import Path
import sys
import unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'runtime/tools/documents'))
try:import numpy as np,av
except ImportError:np=av=None

@unittest.skipUnless(np is not None and av is not None,'Install the private documents runtime for the audio check')
class TempoTests(unittest.TestCase):
    def test_tempo_changes_length_without_changing_pitch(self):
        spec=importlib.util.spec_from_file_location('tempo',ROOT/'native/h3_voice_tempo.py');tempo=importlib.util.module_from_spec(spec);spec.loader.exec_module(tempo)
        rate=24000;t=np.arange(rate*2)/rate;original=np.sin(2*np.pi*220*t).astype(np.float32)
        changed=tempo.adjust(original,rate,1.12)
        self.assertTrue(np.isfinite(changed).all());self.assertLess(abs(len(changed)/len(original)-1/1.12),.02)
        freq=np.fft.rfftfreq(len(changed),1/rate)[np.argmax(np.abs(np.fft.rfft(changed*np.hanning(len(changed)))))]
        self.assertLess(abs(freq-220),1)
        with self.assertRaises(ValueError):tempo.adjust(original,rate,2)

"""Actual CPU soundtrack fitting with private PyAV and generated test tones."""
import math
import struct
import threading
import unittest
import wave
import test_visual_models as fixture

class AgentAudioTests(unittest.TestCase):
    setUp=fixture.VisualModelsTests.setUp
    tearDown=fixture.VisualModelsTests.tearDown
    def test_short_soundtrack_is_fitted_to_exact_duration_without_touching_source(self):
        folder=self.app.data/'outputs'/'audio-test';folder.mkdir(parents=True,exist_ok=True);source=folder/'source.wav';target=folder/'fitted.wav'
        rate=24000
        with wave.open(str(source),'wb') as out:
            out.setnchannels(1);out.setsampwidth(2);out.setframerate(rate)
            out.writeframes(b''.join(struct.pack('<h',round(12000*math.sin(2*math.pi*440*i/rate))) for i in range(rate//5)))
        before=source.read_bytes()
        result=self.app.engine.tool_call('agent-audio-worker.py',{'data':str(self.app.data),'source':source.relative_to(self.app.data).as_posix(),
            'output':target.relative_to(self.app.data).as_posix(),'duration':1,'loop':True},threading.Event(),lambda s:None,self.base/'fit.log',timeout=30)
        self.assertTrue(result['looped']);self.assertFalse(result['pitch_changed']);self.assertEqual(source.read_bytes(),before)
        with wave.open(str(target),'rb') as audio:
            self.assertEqual(audio.getframerate(),48000);self.assertEqual(audio.getnframes(),48000);self.assertEqual(audio.getnchannels(),2)
            raw=audio.readframes(48000)
            self.assertNotEqual(set(raw[:4000]),{0});self.assertEqual(raw[-4:],b'\0\0\0\0')

if __name__=='__main__':unittest.main()

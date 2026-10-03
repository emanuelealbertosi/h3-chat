import base64
import io
import math
from pathlib import Path
import struct
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import wave
from h3chat.audio_export import export_audio
from h3chat.service import Service

ROOT=Path(__file__).resolve().parents[1]


def sine(rate=44100,channels=2):
    out=io.BytesIO()
    with wave.open(out,'wb') as audio:
        audio.setnchannels(channels);audio.setsampwidth(2);audio.setframerate(rate)
        audio.writeframes(b''.join(struct.pack('<h',round(8000*math.sin(2*math.pi*440*i/rate)))*channels for i in range(rate)))
    return out.getvalue()


class AudioExportTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.data=Path(self.tmp.name)
        self.app=Service(ROOT,self.data,start_worker=False)
        self.original=sine();self.item=self.app.upload({'name':'Brano sintetico.wav','data':base64.b64encode(self.original).decode()})
    def tearDown(self):self.app.close();self.tmp.cleanup()
    def test_real_mp3_roundtrip_cache_and_unchanged_original(self):
        result=export_audio(ROOT,self.data,self.item,'mp3');self.assertEqual(result['name'],'Brano sintetico.mp3')
        mp3=self.data/result['url'].lstrip('/');self.assertTrue(mp3.is_file());self.assertLess(mp3.stat().st_size,len(self.original))
        with patch('h3chat.audio_export.subprocess.run',side_effect=AssertionError('Cache must avoid encoding')):
            self.assertEqual(export_audio(ROOT,self.data,self.item,'mp3'),result)
        # Decode the MP3 back to PCM using the same packaged encoder. No GPU.
        converted=self.data/'roundtrip.wav'
        process=subprocess.run([str(ROOT/'runtime/python/python.exe'),'-X','utf8',str(ROOT/'native/audio-export-worker.py'),str(mp3),str(converted),'wav'],capture_output=True)
        self.assertEqual(process.returncode,0,process.stderr)
        with wave.open(str(converted)) as audio:
            self.assertEqual(audio.getnchannels(),2);self.assertEqual(audio.getframerate(),44100)
            self.assertAlmostEqual(audio.getnframes()/audio.getframerate(),1,delta=.04)
            samples=struct.unpack('<'+str(audio.getnframes()*2)+'h',audio.readframes(audio.getnframes()))
            self.assertGreater(max(samples),5000)
        self.assertEqual((self.data/self.item['path']).read_bytes(),self.original)
        self.assertEqual(export_audio(ROOT,self.data,self.item,'wav')['url'],'/media/'+self.item['path'])
    def test_converts_uploaded_mp3_back_to_wav(self):
        result=export_audio(ROOT,self.data,self.item,'mp3');raw=(self.data/result['url'].lstrip('/')).read_bytes()
        item=self.app.upload({'name':'Brano.mp3','data':base64.b64encode(raw).decode()})
        wav=export_audio(ROOT,self.data,item,'wav');self.assertEqual(wav['mime'],'audio/wav')
        with wave.open(str(self.data/wav['url'].lstrip('/'))) as audio:self.assertGreater(audio.getnframes(),40000)
        self.assertEqual(export_audio(ROOT,self.data,item,'mp3')['url'],'/media/'+item['path'])
    def test_rejects_invalid_format_non_audio_and_traversal(self):
        for format in ('aac',None,True):
            with self.assertRaises(ValueError):export_audio(ROOT,self.data,self.item,format)
        for item in (self.item|{'path':'outputs/../../private.wav'},self.item|{'path':'C:/private.wav'},self.item|{'mime':'video/mp4'},self.item|{'path':'outputs/missing.wav'}):
            with self.assertRaises((ValueError,PermissionError)):export_audio(ROOT,self.data,item,'mp3')
    def test_invalid_audio_does_not_leave_partial_or_publish_result(self):
        (self.data/self.item['path']).write_bytes(b'RIFF0000WAVEbroken')
        with self.assertRaisesRegex(ValueError,'convertire'):export_audio(ROOT,self.data,self.item,'mp3')
        self.assertFalse(list((self.data/'exports').rglob('*.partial')))
        self.assertFalse(list((self.data/'exports').rglob('*.mp3')))


if __name__=='__main__':unittest.main()

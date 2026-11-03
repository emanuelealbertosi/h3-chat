import json,subprocess,sys,tempfile,unittest,wave
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

class MossWorkerTests(unittest.TestCase):
    def test_real_worker_protocol_preserves_stereo_and_pause_timing_without_models(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);native=root/'native';native.mkdir();out=root/'output';out.mkdir()
            for name in ('voice-worker.py','h3_voice_tempo.py'):(native/name).write_bytes((ROOT/'native'/name).read_bytes())
            (native/'moss-voice-backend.py').write_text('''import numpy as np
class Engine:
 sample_rate=48000
 channels=2
 precision='bf16'
 load_seconds=0
 last_timings={}
 def __init__(self,*args):pass
 def generate(self,*args):
  t=np.arange(9600)/48000
  return np.stack((np.sin(t*2*np.pi*220)*.2,np.sin(t*2*np.pi*440)*.1),axis=1).astype(np.float32)
''')
            request={'config':{'engine':'moss','temperature':1.7,'seed':734,'pause_ms':100,'speed_factor':1},'segments':[{'text':s,'spoken':s,'voice':{'id':'fixture','reference':''}} for s in ('Ciao.','Ancora.')],'output':str(out)}
            code='import sys,runpy;sys.path[:0]='+repr([str(ROOT),str(ROOT/'runtime/tools/documents')])+';runpy.run_path('+repr(str(native/'voice-worker.py'))+',run_name="__main__")'
            run=subprocess.run([sys.executable,'-X','utf8','-c',code],input=json.dumps(request)+'\n',text=True,encoding='utf-8',capture_output=True,timeout=30)
            events=[json.loads(line) for line in run.stdout.splitlines()];result=next((e['result'] for e in events if e['event']=='result'),None);self.assertIsNotNone(result,run.stdout+run.stderr)
            self.assertEqual(result['channels'],2);self.assertAlmostEqual(result['duration'],.5);self.assertAlmostEqual(result['timeline'][1]['start'],.3)
            with wave.open(str(out/'voce.wav')) as audio:self.assertEqual((audio.getnchannels(),audio.getframerate(),audio.getnframes()),(2,48000,24000))

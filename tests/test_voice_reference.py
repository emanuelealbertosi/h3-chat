"""Voice identity and waveform preparation must match the reference TTS engine."""
import ast,hashlib,json,subprocess,tempfile,unittest
from pathlib import Path
from h3chat.voice import reference_identity

ROOT=Path(__file__).resolve().parents[1]

class VoiceReferenceTests(unittest.TestCase):
    def test_speaker_identity_and_seed_survive_installation_path_changes(self):
        for filename,identity in [('English_Female.wav','aurora'),('French_Female.wav','luna'),('Spanish_Male.wav','leo')]:
            self.assertEqual(reference_identity('/first/'+filename,'female'),identity)
            self.assertEqual(reference_identity('/another/'+filename,'female'),identity)
        self.assertEqual(reference_identity('/models/MyVoice.wav','female'),reference_identity('/external/MyVoice.wav','female'))
        tree=ast.parse((ROOT/'native/voice-backend.py').read_text())
        node=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='stable_seed')
        scope={'hashlib':hashlib};exec(compile(ast.Module(body=[node],type_ignores=[]),'voice-backend.py','exec'),scope)
        for identity in ('aurora','luna','leo','female:myvoice'):
            self.assertEqual(scope['stable_seed'](identity),int(hashlib.sha256(identity.encode()).hexdigest()[:8],16)%(2**31))

    @unittest.skipUnless((ROOT/'runtime/python/python.exe').is_file() and (ROOT/'runtime/vision/packages/torch/__init__.py').is_file(),'Portable voice base not installed')
    def test_real_stereo_downmix_sinc_and_reference_duration_limits(self):
        code=r'''
import ast,json,os,sys,wave
from pathlib import Path
root=Path(sys.argv[1]);folder=Path(sys.argv[2]);sys.path[:0]=[str(root/'native'),str(root/'runtime/vision/packages')]
dll=os.add_dll_directory(str(root/'runtime/vision/dlls')) if os.name=='nt' else None
import torch,numpy as np
torch.set_num_threads(2)
from h3_voice_resample import resample
tree=ast.parse((root/'native/voice-backend.py').read_text());node=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='reference_waveform')
scope={};exec(compile(ast.Module(body=[node],type_ignores=[]),'voice-backend.py','exec'),scope);read=scope['reference_waveform']
sr=44100;t=np.arange(sr)/sr
left=(np.sin(2*np.pi*233*t)*10000).astype('<i2');right=(np.sin(2*np.pi*233*t)*20000).astype('<i2')
def write(name,signal,channels=1):
 p=folder/name
 with wave.open(str(p),'wb') as out:out.setnchannels(channels);out.setsampwidth(2);out.setframerate(sr);out.writeframes(signal.tobytes())
 return p
path=write('stereo.wav',np.column_stack((left,right)),2)
got=read(path,24000,torch)
expected=resample(torch.from_numpy(((left.astype('float32')+right.astype('float32'))/65536))[None,None,:],sr,24000)
assert got.shape==(1,1,24000)
assert torch.allclose(got,expected,atol=1e-6,rtol=0),(got-expected).abs().max()
cancel=read(write('opposite.wav',np.column_stack((left,-left)),2),24000,torch)
assert cancel.abs().max()==0,'Stereo reference must average channels, not change gain'
short=read(write('short.wav',left[:sr//2]),24000,torch)
assert short.shape[-1]==24000 and short[...,-100:].abs().max()==0
for name,signal in [('long.wav',np.zeros(sr*30+1,dtype='<i2')),('empty.wav',np.zeros(0,dtype='<i2'))]:
 try:read(write(name,signal),24000,torch)
 except ValueError:pass
 else:raise AssertionError(name+' accepted')
print(json.dumps({'sinc_matches':True,'stereo_average':True,'limits_checked':True}))
'''
        with tempfile.TemporaryDirectory() as tmp:
            result=subprocess.run([str(ROOT/'runtime/python/python.exe'),'-X','utf8','-c',code,str(ROOT),tmp],capture_output=True,text=True,encoding='utf-8',timeout=120)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertTrue(json.loads(result.stdout)['sinc_matches'])

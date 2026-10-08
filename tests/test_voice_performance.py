"""Keep complete, identical token sequences without per-frame host copies."""
import subprocess,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

class VoicePerformanceTests(unittest.TestCase):
    @unittest.skipUnless((ROOT/'runtime/vision/packages/torch/__init__.py').is_file(),'Portable torch not installed')
    def test_sampler_keeps_tokens_and_rejects_incomplete_speech(self):
        code=r'''
import importlib.util,os,sys,types
from pathlib import Path
from unittest.mock import patch
root=Path(sys.argv[1]);sys.path[:0]=[str(root),str(root/'native'),str(root/'runtime/vision/packages')]
dll=os.add_dll_directory(str(root/'runtime/vision/dlls')) if os.name=='nt' else None
import torch
spec=importlib.util.spec_from_file_location('fixture_backend',root/'native/voice-backend.py');backend=importlib.util.module_from_spec(spec);spec.loader.exec_module(backend)
mod=types.ModuleType('fixture_higgs');sys.modules[mod.__name__]=mod
mod.apply_delay_pattern=lambda codes:codes
mod.reverse_delay_pattern=lambda rows:rows
class State:
 def __init__(self,num_codebooks):self.generation_done=False;self.index=0
mod._SamplerState=State
def sample(logits,state,**kwargs):
 assert kwargs=={'temperature':.7,'top_p':.95,'top_k':50}
 state.index+=1;state.generation_done=state.index==4
 return torch.tensor([state.index,state.index+10])
mod._sampler_step=sample
class Model:
 __module__='fixture_higgs'
 device=torch.device('cpu');num_codebooks=2
 def __init__(self):self.cache_positions=[]
 def _build_prompt_ids(self,tokenizer,text,**kw):return [1,2,3]
 def _prefill_embeds(self,ids,delayed):return torch.zeros(1,3,4)
 def model(self,inputs_embeds,**kw):
  if 'cache_position' in kw:self.cache_positions.append(kw['cache_position'].item())
  return types.SimpleNamespace(last_hidden_state=torch.zeros(1,inputs_embeds.shape[1],4),past_key_values=())
 def audio_head(self,hidden):return torch.zeros(1,2,5)
 def audio_embedding(self,row):return torch.zeros(1,4)
 def _decode_codes(self,rows):self.decoded=rows.clone();return torch.zeros(240)
def engine():
 e=backend.Engine.__new__(backend.Engine);e.torch=torch;e.model=Model();e.seed=734;e.temperature=.7;e.sample_rate=24000;e.precision='8bit';e.progress=lambda **kw:None;e.tokenizer=None;e.reference=lambda voice:torch.ones(2,2,dtype=torch.long)
 return e
e=engine()
with patch.object(torch.Tensor,'cpu',side_effect=AssertionError('Per-frame CPU copy')):wave=e.generate('Una frase.',{'id':'fixture'},max_frames=10)
assert e.model.decoded.tolist()==[[1,11],[2,12],[3,13]]
assert e.model.cache_positions==[3,4,5]
assert len(wave)==240 and e.last_timings['frames']==3
assert e.last_timings['audio_seconds']==.01
assert e.last_timings['precision']=='8bit'
try:engine().generate('Una frase.',{'id':'fixture'},max_frames=2)
except backend.IncompleteAudio:pass
else:raise AssertionError('Token-limited speech published')
print('Tokens, positions, end-of-speech and timings verified')
'''
        result=subprocess.run([str(ROOT/'runtime/python/python.exe'),'-X','utf8','-c',code,str(ROOT)],capture_output=True,text=True,encoding='utf-8',timeout=120)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertIn('verified',result.stdout)

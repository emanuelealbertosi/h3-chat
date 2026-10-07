"""Local Qwen and Chatterbox adapters; each worker owns one model and exits."""
import json
from pathlib import Path

class Engine:
 def __init__(self,config,progress):
  import torch
  self.config=config;self.torch=torch;self.progress=progress;self.cached_reference=None
  device=config['device']
  if device=='cuda' and not torch.cuda.is_available():raise ValueError('GPU NVIDIA non disponibile per il TTS selezionato. Scegli CPU nelle impostazioni.')
  threads=config.get('cpu_threads',8)
  if type(threads) is not int or not 1<=threads<=32:raise ValueError('Numero thread Voice non valido.')
  torch.set_num_threads(min(threads,max(1,__import__('os').cpu_count() or 1)))
  if device=='cuda':torch.backends.cuda.matmul.allow_tf32=True
  progress(message='caricamento '+config['engine'])
  if config['engine']=='qwen':
   from qwen_tts import Qwen3TTSModel
   kwargs={'device_map':device,'dtype':torch.bfloat16 if device=='cuda' else torch.float32,'attn_implementation':'sdpa','local_files_only':True}
   if device=='cuda' and config.get('precision') in ('4bit','8bit'):
    from transformers import BitsAndBytesConfig
    kwargs['quantization_config']=BitsAndBytesConfig(load_in_4bit=config['precision']=='4bit',load_in_8bit=config['precision']=='8bit',bnb_4bit_compute_dtype=torch.bfloat16,bnb_4bit_quant_type='nf4')
   self.model=Qwen3TTSModel.from_pretrained(config['model_path'],**kwargs);self.sample_rate=24000
  else:
   from chatterbox.mtl_tts import ChatterboxMultilingualTTS
   from chatterbox.models.tokenizers import tokenizer
   # The upstream tokenizer initializes Chinese resources even for Italian.
   # Only the explicitly requested Chinese path needs them; stay offline.
   if config['language']!='zh':tokenizer.ChineseCangjieConverter=lambda *args,**kwargs:None
   else:
    tokenizer.hf_hub_download=lambda **kwargs:str(Path(config['model_path'])/'Cangjie5_TC.json')
    tokenizer.ChineseCangjieConverter._init_segmenter=lambda self:None
   self.model=ChatterboxMultilingualTTS.from_local(config['model_path'],device=device,t3_model='v3');self.sample_rate=self.model.sr
  progress(message='modello pronto · '+config['engine'])

 def generate(self,text,voice):
  import numpy as np
  c=self.config
  with self.torch.inference_mode():
   if c['engine']=='qwen':
    generation={k:c[k] for k in ('temperature','top_p','top_k','repetition_penalty','max_new_tokens')}
    kind=c.get('model_kind','custom_voice')
    if kind=='custom_voice':audio,rate=self.model.generate_custom_voice(text=text,language=c['language'],speaker=c['speaker'],instruct=c['instruction'],**generation)
    elif kind=='voice_design':audio,rate=self.model.generate_voice_design(text=text,language=c['language'],instruct=c['instruction'],**generation)
    else:
     identity=(voice['reference'],voice.get('transcript',''))
     if self.cached_reference!=identity:
      self.clone_prompt=self.model.create_voice_clone_prompt(ref_audio=voice['reference'],ref_text=voice.get('transcript') or None,x_vector_only_mode=not bool(voice.get('transcript')));self.cached_reference=identity
     audio,rate=self.model.generate_voice_clone(text=text,language=c['language'],voice_clone_prompt=self.clone_prompt,**generation)
    if int(rate)!=self.sample_rate:raise ValueError('Frequenza Qwen TTS inattesa.')
    return np.asarray(audio[0],dtype=np.float32).reshape(-1)
   identity=(voice['reference'],c['exaggeration'])
   if self.cached_reference!=identity:
    self.model.prepare_conditionals(voice['reference'],exaggeration=c['exaggeration']);self.cached_reference=identity
   wav=self.model.generate(text,language_id=c['language'],**{k:c[k] for k in ('temperature','exaggeration','cfg_weight','repetition_penalty','min_p','top_p')})
   return wav.detach().float().cpu().numpy().reshape(-1)

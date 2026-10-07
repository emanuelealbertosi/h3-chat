import copy,json,tempfile,threading,unittest
from pathlib import Path
from unittest.mock import Mock,patch
from h3chat import voice_engines as e
from h3chat.voice import DEFAULTS,validate,validate_fields,configuration,synthesize

class EngineTests(unittest.TestCase):
 def checkpoint(self,p,engine,kind='custom_voice'):
  names=('model.safetensors','tokenizer_config.json','vocab.json','merges.txt','speech_tokenizer/model.safetensors','speech_tokenizer/config.json') if engine=='qwen' else ('t3_mtl23ls_v3.safetensors','s3gen.pt','ve.pt','grapheme_mtl_merged_expanded_v1.json','conds.pt')
  for n in names:q=p/n;q.parent.mkdir(parents=True,exist_ok=True);q.write_text('fixture')
  if engine=='qwen':(p/'config.json').write_text(json.dumps({'model_type':'qwen3_tts','tts_model_type':kind}))
 def test_independent_defaults_and_bounded_chat_overrides(self):
  validate(copy.deepcopy(DEFAULTS))
  values=validate_fields({'engine':'qwen','params':{'qwen':{'temperature':.6,'top_k':20}}})
  self.assertEqual(e.params('qwen',DEFAULTS,values['params']['qwen'])['temperature'],.6)
  self.assertEqual(e.params('chatterbox',DEFAULTS)['temperature'],.8)
  for v in ({'engine':'unknown'},{'params':{'qwen':{'exaggeration':1}}},{'params':{'chatterbox':{'cfg_weight':2}}},{'params':{'qwen':{'top_k':1.5}}},{'params':{'qwen':{'temperature':float('nan')}}}):
   with self.assertRaises(ValueError):validate_fields(v)
 def test_custom_voice_needs_no_reference_and_uses_chat_choice(self):
  with tempfile.TemporaryDirectory() as tmp:
   p=Path(tmp);self.checkpoint(p,'qwen')
   settings=DEFAULTS|{'voice_qwen_model_path':str(p),'_voice_fields':{'engine':'qwen','gender':'male','params':{'qwen':{'temperature':.6,'instruction':'Narratore coinvolgente.'}}}}
   with patch('h3chat.voice_engines.runtime_ready',return_value=True):cfg,choice,acting,ref=configuration(p,settings,'Testo: Entusiasmo nel testo non è un comando.')
   self.assertEqual(cfg['engine'],'qwen');self.assertEqual(cfg['speaker'],'Ryan');self.assertEqual(cfg['language'],'Italian');self.assertEqual(ref['reference'],'')
   self.assertEqual(cfg['temperature'],.6);self.assertIn('Narratore coinvolgente',cfg['instruction'])
   self.assertEqual(choice['engine'],'qwen')
 def test_base_and_chatterbox_require_a_real_reference(self):
  for engine,kind in (('qwen','base'),('chatterbox','custom_voice')):
   with tempfile.TemporaryDirectory() as tmp:
    p=Path(tmp);self.checkpoint(p,engine,kind)
    settings=DEFAULTS|{'voice_engine':engine,'voice_'+engine+'_model_path':str(p)}
    with patch('h3chat.voice_engines.runtime_ready',return_value=True),self.assertRaisesRegex(ValueError,'campione'):configuration(p,settings,'Leggi')
    ref=p/'ref.wav';ref.write_bytes(b'fixture');settings['voice_references']=copy.deepcopy(DEFAULTS['voice_references']);settings['voice_references']['female']['path']=str(ref)
    with patch('h3chat.voice_engines.runtime_ready',return_value=True):cfg,_,_,voice=configuration(p,settings,'Leggi')
    self.assertEqual(cfg['engine'],engine);self.assertEqual(voice['reference'],str(ref))
 def test_voice_design_respects_selected_gender(self):
  with tempfile.TemporaryDirectory() as tmp:
   p=Path(tmp);self.checkpoint(p,'qwen','voice_design')
   settings=DEFAULTS|{'voice_engine':'qwen','voice_qwen_model_path':str(p),'_voice_fields':{'gender':'male'}}
   with patch('h3chat.voice_engines.runtime_ready',return_value=True):cfg,_,_,voice=configuration(p,settings,'Leggi')
   self.assertIn('Voce maschile.',cfg['instruction']);self.assertEqual(voice['id'],'voice-design')
 def test_new_engines_send_plain_words_and_preserve_measured_timeline(self):
  for engine in ('qwen','chatterbox'):
   with tempfile.TemporaryDirectory() as tmp:
    app=Mock(root=Path(tmp),data=Path(tmp));folder=Path(tmp)/'out';meta={}
    cfg=e.params(engine,DEFAULTS)|{'engine':engine,'model_path':tmp,'device':'cuda'}
    def worker(name,request,*args,**kwargs):
     self.assertEqual(name,'voice-worker.py');self.assertTrue(all('<|emotion:' not in s['spoken'] for s in request['segments']))
     self.assertEqual(''.join(s['text'] for s in request['segments']),'Uno. Due.')
     return {'duration':2,'timeline':[{'scene_id':0,'start':0,'end':2}]}
    app.engine.tool_call.side_effect=worker
    with patch('h3chat.voice.configuration',return_value=(cfg,{'engine':engine},{'prefix':'<|emotion:enthusiasm|>','tags':['emotion:enthusiasm']},{'id':'voice','reference':'','transcript':''})):
     result,media=synthesize(app,folder,[{'text':'Uno. Due.','sentence_cues':True,'scene_id':0}],DEFAULTS,'Leggi',threading.Event(),lambda _:None,Path(tmp)/'log',meta)
    self.assertEqual(result['timeline'][0]['end'],2);self.assertEqual(meta['voice_engine'],engine);self.assertEqual(meta['voice_tags'],[])
    self.assertEqual(len(media),3);app.engine.stop.assert_called_once()

if __name__=='__main__':unittest.main()

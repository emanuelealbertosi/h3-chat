import base64,json,struct,threading,wave
from pathlib import Path
from unittest.mock import patch
import test_music as fixture
from h3chat import minimax_music
from h3chat.music_options import options
from h3chat.music_resing import generate as resing
import unittest

class AlternativeMusicTests(unittest.TestCase):
 setUp=fixture.MusicTests.setUp
 tearDown=fixture.MusicTests.tearDown

 def mini(self):
  files={}
  for role,key in [('diffusion','cond_layer_logits'),('llm','model.audio_decoder.projection.weight'),('vae','dec_in_proj.weight')]:
   p=self.data/(role+'.safetensors');h=json.dumps({key:{'dtype':'F32','shape':[1],'data_offsets':[0,4]}}).encode();p.write_bytes(struct.pack('<Q',len(h))+h+b'\0'*4);files[role]=str(p)
  return self.app.external_model({'profile':'minimax-music','name':'MiniMax Music fixture','files':files})

 def audio(self):
  p=self.data/'source.wav'
  with wave.open(str(p),'wb') as f:f.setparams((1,2,8000,0,'NONE','not compressed'));f.writeframes(b'\x01\0'*24000)
  return self.app.upload({'name':'Originale.wav','data':base64.b64encode(p.read_bytes()).decode()})

 def test_minimax_profile_validation_and_chat_snapshot_are_independent(self):
  model=self.mini();self.assertTrue(model['ready']);before=self.app.store.settings()
  chat=self.app.store.create_chat()['id'];ident=self.app.send(chat,{'prompt':'Crea il brano','music':True,'assistant':False,'music_model':model['id'],
      'music_fields':{'lyrics':'[Verse]\nIl sole','style':'Italian pop'},'music_parameters':{'seed':12,'top_k':30,'num_inference_steps':8},'music_max_duration':12})['job_id']
  payload=json.loads(self.app.store.one('SELECT payload FROM jobs WHERE id=?',(ident,))['payload']);s=payload['settings']
  self.assertEqual(s['music_model'],model['id']);self.assertEqual(options(model,s)['top_k'],30);self.assertEqual(options(model,s)['max_duration'],12)
  self.assertEqual(self.app.store.settings(),before)
  with patch.object(self.app.engine,'generate_minimax_music',return_value={'fixture':True}) as generate,patch.object(self.app.engine,'start_music') as native:
   self.assertEqual(self.app.engine.generate_music(model,s,{},ident,threading.Event(),lambda _:None),{'fixture':True})
  generate.assert_called_once();native.assert_not_called()

 def test_minimax_rejects_yue_controls_and_invalid_duration(self):
  for bad in ({'cot':'full'},{'top_k':0},{'max_duration':361},{'seed':True},{'cfg_scale':float('nan')},{'sampler':'invented'}):
   with self.subTest(bad=bad),self.assertRaises(ValueError):minimax_music.validate(bad)
  self.assertEqual(minimax_music.options({'id':'m'},{'music_overrides':{'m':{'max_duration':None}}})['max_duration'],120)

 def test_resing_requires_audio_and_yue_before_enqueue(self):
  chat=self.app.store.create_chat()['id'];body={'prompt':'Nuovo testo','assistant':False,'music':True,'music_resing':True}
  with patch('h3chat.remix_runtime.ready',return_value={'media':True,'separation':True,'score':True}):
   with self.assertRaisesRegex(ValueError,'canzone audio'):self.app.send(chat,body)
   mini=self.mini()
   with self.assertRaisesRegex(ValueError,'YuE2'):self.app.send(chat,body|{'music_model':mini['id'],'media':[self.audio()]})
  self.assertEqual(self.app.store.all('SELECT id FROM jobs'),[])

 def test_resing_captures_source_and_writes_lyrics_even_with_assistant_off(self):
  audio=self.audio();chat=self.app.store.create_chat()['id']
  with patch('h3chat.remix_runtime.ready',return_value={'media':True,'separation':True,'score':True}):
   ident=self.app.send(chat,{'prompt':'[Verse]\nTesto nuovo','assistant':False,'music':True,'music_resing':True,'media':[audio]})['job_id']
  s=json.loads(self.app.store.one('SELECT payload FROM jobs WHERE id=?',(ident,))['payload'])['settings']
  self.assertEqual(s['_music_resing']['source']['id'],audio['id'])
  composed={'title':'Viaggio','style':'Italian pop','lyrics':'[Verse]\nPartiamo verso il mare','abc':'','instrumental':False}
  engine=self.app.engine
  with patch.object(engine,'require_model',return_value={'name':'Chat fixture'}),patch.object(engine,'start_llama') as start,patch.object(engine,'completion',return_value=(json.dumps(composed),'stop')) as completion:
   song,assistant=engine.refine_music([],'Inventala su un viaggio al mare',{},s,threading.Event(),self.data/'log',lambda _:None)
  self.assertEqual(song,composed);self.assertEqual(assistant['model'],'Chat fixture');start.assert_called_once()
  messages=completion.call_args.args[0];self.assertIn('write original lyrics',messages[0]['content']);self.assertIn('Inventala su un viaggio al mare',messages[1]['content'])
  with patch.object(engine,'start_llama') as start,patch.object(engine,'completion') as completion:
   explicit,_=engine.refine_music([],'Istruzioni non cantate',{'lyrics':'Parole esatte'},s,threading.Event(),self.data/'log',lambda _:None)
  start.assert_not_called();completion.assert_not_called()
  self.assertEqual(explicit['lyrics'],'Parole esatte')

 def test_resing_uses_shared_checked_pipeline_and_keeps_source_untouched(self):
  audio=self.audio();source=self.app.data/audio['path'];before=source.read_bytes();ident='c'*32;folder=self.app.data/'outputs'/ident
  def call(worker,request,*args,**kwargs):
   self.assertEqual(worker,'video-remix-worker.py')
   if request['op']=='probe':return {'has_audio':True,'duration':300}
   self.assertEqual(request['op'],'vocal');self.assertEqual(request['config']['mode'],'singing');self.assertEqual(request['config']['text'],'Testo nuovo')
   self.assertEqual(request['config']['end'],300)
   self.assertEqual(request['config']['abc'],'')
   self.assertEqual(request['source'],str(source));out=folder/'remix-work/audio.wav';out.parent.mkdir();out.write_bytes(b'fixture');return {'path':str(out)}
  settings=self.app.store.settings()|{'_music_resing':{'source':audio,'runtime':{}}}
  with patch.object(self.app.engine,'tool_call',side_effect=call),patch.object(self.app.engine,'stop'):
   media=resing(self.app.engine,self.model,settings,{'title':'Nuova voce','style':'pop','lyrics':'Testo nuovo','abc':'X:1\nK:C\nC D E F'},ident,threading.Event(),lambda _:None)
  self.assertTrue(media['generation']['original_preserved']);self.assertEqual(source.read_bytes(),before)

 def test_resing_rejects_longer_audio_without_starting_synthesis(self):
  audio=self.audio();settings=self.app.store.settings()|{'_music_resing':{'source':audio,'runtime':{}}}
  with patch.object(self.app.engine,'tool_call',return_value={'has_audio':True,'duration':301}) as call,patch.object(self.app.engine,'stop'):
   with self.assertRaisesRegex(ValueError,'5 minuti'):resing(self.app.engine,self.model,settings,{},'d'*32,threading.Event(),lambda _:None)
  self.assertEqual(call.call_count,1);self.assertEqual(call.call_args.args[1]['op'],'probe')

if __name__=='__main__':unittest.main()

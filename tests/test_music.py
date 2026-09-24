import json, tempfile, threading, unittest, urllib.request, urllib.error, wave, zipfile
from pathlib import Path
from unittest.mock import patch
from app import Handler, ThreadingHTTPServer
from h3chat.service import Service
from h3chat.store import DEFAULTS
from h3chat.downloads import extract_members, Cancelled
from h3chat.music_options import DEFAULTS as PRESET, validate, options
from h3chat.music_routing import route, direct_composition
from h3chat.music_models import SIDECARS
from h3chat.hardware import assess_model, assess_selection
from test_mtp import mtp_gguf

ROOT=Path(__file__).resolve().parents[1]

class MusicTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.data=Path(self.tmp.name)
  self.app=Service(ROOT,self.data/'data',start_worker=False)
  folder=self.data/'pesi già scaricati'
  main=mtp_gguf(folder/'music.gguf','audiocpp',heads=0,names=['model_weights/model.embed_tokens.weight','model_weights/vae2llm.weight','model_weights/llm2vae.weight'])
  vae=mtp_gguf(self.data/'altro disco/decoder.gguf','audiocpp',heads=0,names=['vae_weights/decoder.layers.0.weight'])
  for role,name in SIDECARS.items():
   p=folder/'sidecars'/name;p.parent.mkdir(exist_ok=True);p.write_text('YQ== 0\n' if role=='tokenizer' else '{"fixture":true}')
  self.config={'profile':'yue2','name':'Music fixture','files':{'model':str(main),'vae':str(vae)}}
  self.model=self.app.external_model(self.config)
  self.app.save_settings({'music_model':self.model['id'],'chat_model':'','music_backend':'cpu','ram_cache_gb':0})
 def tearDown(self):self.app.close();self.tmp.cleanup()
 def test_default_preset_and_strict_options(self):
  self.assertEqual((PRESET['cot'],PRESET['seed'],PRESET['num_inference_steps'],PRESET['cfg_scale']),('full',831001,32,1))
  self.assertEqual((PRESET['abc_max_tokens'],PRESET['semantic_max_tokens']),(4096,9000))
  for bad in ({'cot':'auto'},{'num_inference_steps':True},{'cfg_scale':float('nan')},{'seed':2**53},{'semantic_min_tokens':800,'semantic_max_tokens':200},{'scheduler':'euler'}):
   with self.subTest(bad=bad),self.assertRaises(ValueError):validate(bad)
  v=options(self.model,{'music_overrides':{self.model['id']:{'seed':-1}}});self.assertGreaterEqual(v['seed'],0)
 def test_explicit_automatic_and_negative_routing(self):
  for prompt in ('crea una canzone rock','puoi generare musica ambient','Componi un brano strumentale','generate a song'):
   self.assertEqual(route([{'content':prompt}],DEFAULTS)['intent'],'music')
  for prompt in ('non creare una canzone','spiegami come creare una canzone','crea solo il testo di una canzone','genera una copertina per il brano','scrivi codice per generare musica'):
   self.assertIsNone(route([{'content':prompt}],DEFAULTS))
  self.assertIsNone(route([{'content':'genera musica'}],DEFAULTS|{'music_auto':False}))
  self.assertIsNone(route([{'content':'genera musica'}],DEFAULTS|{'_image_model':'explicit'}))
  self.assertEqual(route([{'content':'un jingle breve'}],DEFAULTS|{'_music':True,'music_auto':False})['selection'],'explicit')
 def test_original_model_paths_and_required_sidecars(self):
  self.assertTrue(self.model['ready'])
  files=self.app.engine.model_files(self.model)
  self.assertTrue(Path(files['vae']).samefile(self.config['files']['vae']))
  self.assertTrue(Path(files['model']).samefile(self.config['files']['model']))
  self.assertFalse((self.data/'data/models').exists())
  Path(files['tokenizer']).unlink()
  with self.assertRaisesRegex(ValueError,'Tokenizer'):self.app.external_model(self.config)
 def test_incompatible_audio_weights_are_rejected(self):
  wrong=mtp_gguf(self.data/'wrong.gguf')
  with self.assertRaisesRegex(ValueError,'non riconosciuti'):
   self.app.external_model(self.config|{'files':self.config['files']|{'model':str(wrong)}})
 def test_direct_lyrics_and_instrumental(self):
  song=direct_composition('Titolo: Alba\nStile: acoustic pop\nTesto:\n[Verse]\nCiao sole',{})
  self.assertEqual(song['lyrics'],'[Verse]\nCiao sole');self.assertEqual(song['title'],'Alba')
  self.assertEqual(direct_composition('genera musica strumentale jazz',{})['lyrics'],'[Instrumental]')
  with self.assertRaisesRegex(ValueError,'Assistant Off'):direct_composition('crea una canzone',{})
 def test_assistant_off_does_not_load_llm(self):
  engine=self.app.engine
  with patch.object(engine,'start_llama') as start,patch.object(engine,'completion') as completion:
   result,info=engine.refine_music([],'crea una canzone',{'style':'pop','lyrics':'[Verse]\nAlba'},DEFAULTS|{'_assistant':False},threading.Event(),self.data/'log',lambda _:None)
  self.assertIsNone(info);self.assertEqual(result['lyrics'],'[Verse]\nAlba');start.assert_not_called();completion.assert_not_called()
 def test_music_job_canvas_and_snapshot_without_chat_model(self):
  for canvas in (False,True):
   chat=self.app.store.create_chat();job_id=self.app.send(chat['id'],{'prompt':'genera una canzone','assistant':False,'music':True,'music_fields':{'title':'Alba','style':'pop','lyrics':'[Verse]\nSorge il sole'},'canvas':canvas})['job_id']
   job=self.app.store.one('SELECT * FROM jobs WHERE id=?',(job_id,))
   self.app.store.save_settings({'music_overrides':{self.model['id']:{'num_inference_steps':8}}})
   captured=json.loads(job['payload'])['settings'];self.assertFalse(captured['_assistant']);self.assertTrue(captured['_music'])
   media={'id':job_id,'name':'Alba.wav','path':f'outputs/{job_id}/audio.wav','mime':'audio/wav','generation':{'duration':10}}
   with patch.object(self.app.engine,'start_llama') as llm,patch.object(self.app.engine,'generate_music',return_value=media):
    self.app.execute_job(job,threading.Event())
   llm.assert_not_called();answer=self.app.store.chat(chat['id'])['messages'][-1]
   self.assertEqual(answer['status'],'done',answer['meta']);self.assertNotIn('Sorge il sole',answer['content'])
   self.assertEqual(answer['media'],[] if canvas else [media])
   self.assertEqual(self.app.validate_media([{'id':job_id}],canvas=True),[media])
   with self.assertRaisesRegex(ValueError,'audio'):self.app.validate_media([{'id':job_id}])
   if canvas:self.assertIn('Sorge il sole',answer['meta']['artifact']['content'])
 def test_assistant_on_uses_shared_chat_engine(self):
  engine=self.app.engine;result={'title':'Alba','style':'pop','lyrics':'[Verse]\nSorge il sole','abc':'','instrumental':False}
  with patch.object(engine,'require_model',return_value={'name':'Current chat'}),patch.object(engine,'start_llama') as start,patch.object(engine,'completion',return_value=(json.dumps(result),'stop')) as completion:
   composed,info=engine.refine_music([],'crea una canzone',{},DEFAULTS|{'_assistant':True},threading.Event(),self.data/'log',lambda _:None)
  self.assertEqual(composed,result);self.assertEqual(info['model'],'Current chat');start.assert_called_once()
  self.assertEqual(completion.call_args.args[1]['think_level'],'off');self.assertIn('schema',completion.call_args.kwargs)
 def test_music_memory_uses_independent_backend(self):
  model=self.model|{'files':[{'role':'model','path':'model.gguf','size':4*1024**3}]}
  hardware={'ram':{'free_mb':40000},'gpu':[{'vendor':'NVIDIA','name':'Small GPU','total_mb':4096,'free_mb':3000}]}
  settings=DEFAULTS|{'profile':'cpu','music_backend':'cuda'}
  result=assess_model(model,settings,hardware)
  self.assertEqual(result['status'],'oom');self.assertEqual(result['recommended_patch'],{'music_backend':'cpu'})
  self.assertEqual(assess_selection([model],settings,hardware)['status'],'oom')
  self.assertEqual(assess_model(model,settings|{'music_backend':'cpu'},hardware)['vram_gb'],0)
  a=self.app.engine.session_key('music',self.model,settings)
  b=self.app.engine.session_key('music',self.model,settings|{'music_threads':4})
  self.assertNotEqual(a,b)
 def test_chat_after_song_uses_composition_without_treating_audio_as_vision(self):
  self.app.save_settings({'chat_model':'qwen3-06'})
  chat=self.app.store.create_chat();first=self.app.store.enqueue(chat['id'],'crea una canzone',[],self.app.store.settings())
  job=self.app.store.one('SELECT * FROM jobs WHERE id=?',(first,))
  self.app.store.update_answer(job,'Ecco il brano.','done',[{'id':first,'path':'outputs/absent.wav','mime':'audio/wav','name':'Song.wav'}],{'music_composition':{'title':'Alba','style':'pop','lyrics':'Il sole sorge'}})
  self.app.store.execute("UPDATE jobs SET status='done' WHERE id=?",(first,))
  model={'id':'qwen3-06','name':'Chat fixture','files':[],'capabilities':['chat'],'vision':{'enabled':False}}
  with patch.object(self.app.engine,'require_model',return_value=model),patch.object(self.app.engine,'start_llama'),patch.object(self.app.engine,'route',return_value={'intent':'chat','prompt':''}),patch.object(self.app.engine,'completion',return_value=('Il testo parla del sole.','stop')) as completion:
   second=self.app.send(chat['id'],{'prompt':'Di cosa parla il testo?'})['job_id']
   self.app.execute_job(self.app.store.one('SELECT * FROM jobs WHERE id=?',(second,)),threading.Event())
  answer=self.app.store.chat(chat['id'])['messages'][-1];self.assertEqual(answer['status'],'done',answer['meta'])
  sent=json.dumps(completion.call_args.args[0]);self.assertNotIn('image_url',sent);self.assertIn('Il sole sorge',sent)
 def test_verified_zip_allowlist_prevalidation_and_cancel(self):
  bundle=self.data/'bundle.zip';dest=self.data/'extract'
  with zipfile.ZipFile(bundle,'w') as z:z.writestr('package/bin/a.dll',b'dll');z.writestr('package/unneeded.lib',b'large')
  with self.assertRaises(ValueError):extract_members(bundle,dest,{'package/bin/a.dll':'../outside'})
  self.assertFalse(dest.exists())
  extract_members(bundle,dest,{'package/bin/a.dll':'a.dll'})
  self.assertEqual([p.name for p in dest.iterdir()],['a.dll']);self.assertEqual((dest/'a.dll').read_bytes(),b'dll')
  cancel=threading.Event();cancel.set()
  with self.assertRaises(Cancelled):extract_members(bundle,dest,{'package/bin/a.dll':'b.dll'},cancel)
  self.assertFalse((dest/'b.dll').exists());self.assertFalse((dest/'b.dll.extracting').exists())
 def test_wav_player_range_and_media_guards(self):
  folder=self.app.data/'outputs/audio'
  folder.mkdir(parents=True);p=folder/'audio.wav'
  with wave.open(str(p),'wb') as f:f.setparams((2,2,48000,0,'NONE','not compressed'));f.writeframes(b'\x01\x00'*4800)
  raw=p.read_bytes();server=ThreadingHTTPServer(('127.0.0.1',0),Handler);server.app=self.app
  thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start();url=f'http://127.0.0.1:{server.server_port}/media/outputs/audio/audio.wav'
  try:
   for header,expected in (('bytes=0-43',raw[:44]),('bytes=-20',raw[-20:]),('bytes=44-',raw[44:])):
    with urllib.request.urlopen(urllib.request.Request(url,headers={'Range':header})) as r:
     self.assertEqual(r.status,206);self.assertEqual(r.read(),expected);self.assertEqual(r.headers['Accept-Ranges'],'bytes')
   for header in ('bytes=999999-','bytes=-0','bytes=0-1,5-7'):
    with self.assertRaises(urllib.error.HTTPError) as exc:urllib.request.urlopen(urllib.request.Request(url,headers={'Range':header}))
    self.assertEqual(exc.exception.code,416)
  finally:server.shutdown();server.server_close()

if __name__=='__main__':unittest.main()

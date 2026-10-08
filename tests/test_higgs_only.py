import copy,json,tempfile,threading,unittest
from pathlib import Path
from unittest.mock import Mock,patch
from h3chat import voice_engines as e
from h3chat.voice import DEFAULTS,validate,validate_fields,configuration,synthesize
from h3chat.store import Store

class HiggsOnlyTests(unittest.TestCase):
 def test_regenerate_uses_current_precision_and_preserves_radio_controls(self):
  with tempfile.TemporaryDirectory() as tmp:
   store=Store(tmp);chat=store.create_chat()['id']
   original=store.settings()|{'voice_precision':'8bit','voice_seed':734,'_voice_fields':{'delivery':'radio'}}
   ident=store.enqueue(chat,'Leggi il testo.',[],original,True)
   store.execute("UPDATE jobs SET status='done' WHERE id=?",(ident,));store.execute("UPDATE messages SET status='done'")
   current=store.settings()|{'voice_precision':'bf16'}
   fresh=store.regenerate(chat,current);payload=json.loads(store.one('SELECT payload FROM jobs WHERE id=?',(fresh,))['payload'])
   self.assertEqual(payload['settings']['voice_precision'],'bf16')
   self.assertEqual(payload['settings']['voice_seed'],734)
   self.assertEqual(payload['settings']['_voice_fields']['delivery'],'radio')
 def test_only_higgs_and_legacy_chat_controls_preserved(self):
  self.assertEqual(list(e.ENGINES),['higgs']);validate(copy.deepcopy(DEFAULTS))
  for old in e.RETIRED:
   value=validate_fields({'engine':old,'gender':'female','emotion':'enthusiasm','pitch':'high','delivery':'radio','params':{old:{'temperature':.8}}})
   self.assertEqual(value,{'engine':'higgs','gender':'female','emotion':'enthusiasm','pitch':'high','delivery':'radio'})
  with self.assertRaises(ValueError):validate_fields({'engine':'unknown'})
 def test_old_defaults_do_not_validate_retired_paths(self):
  settings=DEFAULTS|{'voice_engine':'qwen','voice_qwen_model_path':'Z:/missing','voice_chatterbox_model_path':'Z:/missing','_voice_fields':{'engine':'chatterbox','delivery':'radio'}}
  new=e.normalize(settings);self.assertEqual(new['voice_engine'],'higgs');self.assertFalse(any(k.startswith(('voice_qwen_','voice_chatterbox_')) for k in new))
  validate(new);self.assertEqual(settings['_voice_fields']['engine'],'chatterbox')
 def test_regenerate_legacy_snapshot_uses_higgs_preserving_controls(self):
  with tempfile.TemporaryDirectory() as tmp:
   store=Store(tmp);chat=store.create_chat()['id']
   old=DEFAULTS|{'voice_engine':'chatterbox','voice_chatterbox_temperature':.8,'_voice_fields':{'engine':'chatterbox','emotion':'enthusiasm','pitch':'high'},'_infographic':{'voice_style':'radio'},'voice_temperature':.6}
   ident=store.enqueue(chat,'Crea uno short.',[],old,True)
   store.execute("UPDATE jobs SET status='done' WHERE id=?",(ident,));store.execute("UPDATE messages SET status='done'")
   fresh=store.regenerate(chat);payload=json.loads(store.one('SELECT payload FROM jobs WHERE id=?',(fresh,))['payload'])
   self.assertEqual(payload['settings']['voice_engine'],'higgs');self.assertEqual(payload['settings']['_voice_fields'],{'engine':'higgs','emotion':'enthusiasm','pitch':'high'})
   self.assertEqual(payload['settings']['_infographic']['voice_style'],'radio');self.assertEqual(payload['settings']['voice_temperature'],.6)
   self.assertNotIn('voice_chatterbox_temperature',payload['settings'])
 def test_retired_voice_cannot_resume_cached_audio(self):
  old={'voice_engine':'higgs','_voice_fields':{'engine':'chatterbox'},'_manim_voice_resume':'old'}
  self.assertNotIn('_manim_voice_resume',e.normalize(old))
 def test_historical_radio_request_uses_higgs_and_radio_parameters(self):
  with tempfile.TemporaryDirectory() as tmp:
   app=Mock(root=Path(tmp),data=Path(tmp));ref=Path(tmp)/'Italian.wav';ref.write_bytes(b'fixture')
   settings=copy.deepcopy(DEFAULTS);settings.update(voice_model_path='model',voice_codec_path='codec',voice_engine='chatterbox',_voice_fields={'engine':'chatterbox','delivery':'radio','emotion':'enthusiasm','pitch':'high'})
   settings['voice_references']['female']['path']=str(ref)
   with patch('h3chat.voice.runtime_ready',return_value=True),patch('h3chat.voice.resolve_model',side_effect=lambda path,kind='tts':path):
    cfg,choice,_,_=configuration(app.root,settings,'')
    self.assertEqual(cfg['engine'],'higgs');self.assertEqual(choice['pitch'],'high');self.assertEqual(cfg['seed'],734);self.assertEqual(cfg['temperature'],.7)
    app.engine.tool_call.return_value={'duration':2,'timeline':[]};meta={}
    synthesize(app,Path(tmp)/'out',[{'text':'Prima frase. Seconda frase.','scene_id':0}],settings,'',threading.Event(),lambda _:None,Path(tmp)/'log',meta)
    request=app.engine.tool_call.call_args.args[1];self.assertEqual(request['config']['engine'],'higgs')
    self.assertEqual([s['speed_factor'] for s in request['segments']],[1.08,1.12]);self.assertEqual(meta['voice_engine'],'higgs')

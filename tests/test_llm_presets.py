import json
import tempfile
import unittest
from pathlib import Path
from h3chat.service import Service
from h3chat.store import Store
from h3chat.llm_options import KEYS

ROOT=Path(__file__).resolve().parents[1]

class LlmPresetsTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.app=Service(ROOT,Path(self.tmp.name),start_worker=False)
 def tearDown(self):self.app.close();self.tmp.cleanup()
 def test_switch_restores_each_model_and_chat_toggle_updates_only_active_preset(self):
  a=self.app.save_settings({'chat_model':'qwen3-06','context':65536,'max_tokens':6000,'temperature':.8,'mtp_enabled':True})
  b=self.app.save_settings({'chat_model':'qwen3-4'})
  self.assertEqual(b['context'],4096);self.assertEqual(b['max_tokens'],1024)
  self.app.save_settings({'context':131072,'temperature':.2,'think_level':'high'})
  restored=self.app.save_settings({'chat_model':'qwen3-06'})
  self.assertEqual((restored['context'],restored['max_tokens'],restored['temperature'],restored['mtp_enabled']),(65536,6000,.8,True))
  self.app.save_settings({'think_level':'low'})
  restored=self.app.save_settings({'chat_model':'qwen3-4'})
  self.assertEqual((restored['context'],restored['temperature'],restored['think_level']),(131072,.2,'high'))
  self.assertEqual(restored['llm_overrides']['qwen3-06']['think_level'],'low')
 def test_edit_inactive_preset_and_job_snapshots_are_independent(self):
  initial=self.app.save_settings({'chat_model':'qwen3-06','context':65536,'max_tokens':6000})
  presets=initial['llm_overrides']|{'qwen3-4':{'context':131072,'max_tokens':4000,'temperature':.3}}
  saved=self.app.save_settings(initial|{'llm_overrides':presets})
  self.assertEqual(saved['chat_model'],'qwen3-06');self.assertEqual(saved['context'],65536)
  chat=self.app.store.create_chat();job=self.app.store.enqueue(chat['id'],'ciao',[],saved)
  switched=self.app.save_settings({'chat_model':'qwen3-4'})
  self.assertEqual((switched['context'],switched['max_tokens']),(131072,4000))
  snapshot=json.loads(self.app.store.one('SELECT payload FROM jobs WHERE id=?',(job,))['payload'])['settings']
  self.assertEqual((snapshot['chat_model'],snapshot['context']),('qwen3-06',65536))
 def test_preset_edit_wins_over_unchanged_flat_aliases_from_full_ui_draft(self):
  saved=self.app.save_settings({'chat_model':'qwen3-06','context':65536})
  preset=saved['llm_overrides']['qwen3-06']|{'context':131072}
  result=self.app.save_settings(saved|{'llm_overrides':{'qwen3-06':preset}})
  self.assertEqual(result['context'],131072)
 def test_old_settings_are_migrated_without_changing_the_active_values(self):
  expected=self.app.save_settings({'chat_model':'qwen3-06','context':64000,'max_tokens':6000,'temperature':.4})
  self.app.store.execute("DELETE FROM settings WHERE key='llm_overrides'")
  migrated=Store(self.app.data).settings()
  self.assertEqual({k:migrated[k] for k in KEYS},{k:expected[k] for k in KEYS})
  self.assertEqual(migrated['llm_overrides']['qwen3-06'],{k:expected[k] for k in KEYS})
 def test_inactive_presets_are_validated_too(self):
  for value in ([],{'x':{'temperature':float('nan')}},{'x':{'context':1024,'max_tokens':8192}},{'x':{'oops':1}},{'x':{'mtp_enabled':'yes'}}):
   with self.assertRaises(ValueError):self.app.validate_settings({'llm_overrides':value})
 def test_output_ceiling_preserves_values_and_large_api_budget_roundtrips(self):
  from h3chat.remote_llm import request_body
  before=self.app.store.settings()
  self.assertEqual(self.app.validate_settings({})['max_tokens'],before['max_tokens'])
  saved=self.app.save_settings({'chat_model':'qwen3-06','context':262144,'max_tokens':100000})
  self.app.save_settings({'chat_model':'qwen3-4'})
  restored=self.app.save_settings({'chat_model':'qwen3-06'})
  self.assertEqual(restored['max_tokens'],100000)
  cfg={'model':'fixture','thinking':'none','format':'json_object'}
  self.assertEqual(request_body(cfg,[{'role':'user','content':'Synthetic request'}],saved,True,None)['max_tokens'],100000)
  for patch in ({'context':262144,'max_tokens':100001},{'context':262144,'max_tokens':True}):
   with self.assertRaises(ValueError):self.app.validate_settings(patch)

 def test_regenerate_uses_current_vision_device_without_changing_original_request(self):
  chat=self.app.store.create_chat();original=self.app.store.enqueue(chat['id'],'Descrivi la figura',[],self.app.store.settings())
  self.app.cancel(original);self.app.save_settings({'vision_device':'gpu'})
  replay=self.app.regenerate(chat['id'])['job_id']
  value=json.loads(self.app.store.one('SELECT payload FROM jobs WHERE id=?',(replay,))['payload'])
  self.assertEqual(value['settings']['vision_device'],'gpu');self.assertEqual(value['prompt'],'Descrivi la figura')
  self.assertEqual(len(self.app.store.chat(chat['id'])['messages']),2)

 def test_video_assistant_large_budget_presets_retry_and_validation(self):
  initial=self.app.store.settings()
  self.assertEqual(self.app.validate_settings({})['video_prompt_max_tokens'],initial['video_prompt_max_tokens'])
  saved=self.app.save_settings({'chat_model':'qwen3-06','context':80000,'video_prompt_max_tokens':24000})
  chat=self.app.store.create_chat();original=self.app.store.enqueue(chat['id'],'Synthetic video',[],saved)
  self.app.cancel(original)
  self.assertEqual(self.app.save_settings({'chat_model':'qwen3-4'})['video_prompt_max_tokens'],3000)
  self.app.save_settings({'video_prompt_max_tokens':100000})
  self.assertEqual(self.app.save_settings({'chat_model':'qwen3-06'})['video_prompt_max_tokens'],24000)
  self.app.save_settings({'video_prompt_max_tokens':16000})
  replay=self.app.regenerate(chat['id'])['job_id']
  snapshot=json.loads(self.app.store.one('SELECT payload FROM jobs WHERE id=?',(replay,))['payload'])['settings']
  self.assertEqual(snapshot['video_prompt_max_tokens'],16000)
  self.assertEqual(snapshot['context'],80000)
  for value in (255,100001,True,16384.5,'16000'):
   with self.assertRaises(ValueError):self.app.validate_settings({'video_prompt_max_tokens':value})
   with self.assertRaises(ValueError):self.app.validate_settings({'llm_overrides':{'qwen3-06':{'video_prompt_max_tokens':value}}})

 def test_vision_reference_limit_defaults_presets_validation_and_retry_snapshot(self):
  self.assertEqual(self.app.store.settings()['vision_max_refs'],4)
  first=self.app.save_settings({'chat_model':'qwen3-06','vision_max_refs':8})
  chat=self.app.store.create_chat();original=self.app.store.enqueue(chat['id'],'Synthetic',[],first)
  self.app.cancel(original)
  self.assertEqual(self.app.save_settings({'chat_model':'qwen3-4'})['vision_max_refs'],4)
  self.app.save_settings({'vision_max_refs':2})
  restored=self.app.save_settings({'chat_model':'qwen3-06'})
  self.assertEqual(restored['vision_max_refs'],8)
  self.assertEqual(restored['llm_overrides']['qwen3-4']['vision_max_refs'],2)
  self.app.save_settings({'vision_max_refs':6})
  replay=self.app.regenerate(chat['id'])['job_id']
  value=json.loads(self.app.store.one('SELECT payload FROM jobs WHERE id=?',(replay,))['payload'])
  self.assertEqual(value['settings']['vision_max_refs'],6)
  for value in (0,13,True,2.5,'4'):
   with self.assertRaises(ValueError):self.app.validate_settings({'vision_max_refs':value})
   with self.assertRaises(ValueError):self.app.validate_settings({'llm_overrides':{'qwen3-06':{'vision_max_refs':value}}})

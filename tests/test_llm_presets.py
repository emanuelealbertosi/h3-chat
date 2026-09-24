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

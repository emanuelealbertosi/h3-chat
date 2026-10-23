import json
import sqlite3
import unittest
from h3chat.retired_features import migrate
from h3chat.video_options import validate,options,capture_request
from h3chat.external_models import PROFILES


class RetirementTests(unittest.TestCase):
    def test_migration_preserves_history_other_models_and_memory_settings(self):
        db=sqlite3.connect(':memory:');db.row_factory=sqlite3.Row
        self.addCleanup(db.close)
        db.executescript('CREATE TABLE external_models(id TEXT,config TEXT); CREATE TABLE settings(key TEXT,value TEXT); CREATE TABLE jobs(payload TEXT);')
        for ident,profile in [('f','fibo2-int8'),('b','fibo2'),('q','qwen21')]:
            db.execute('INSERT INTO external_models VALUES (?,?)',(ident,json.dumps({'profile':profile})))
        settings={'create_model':'f','edit_model':'q','video_model':'h3','image_overrides':{'f':{'fibo_offload':'full'},'q':{'seed':42}},
                  'video_overrides':{'h3':{'longtake_enabled':True,'seed':71,'attention_chunks':56}}}
        for k,v in settings.items():db.execute('INSERT INTO settings VALUES (?,?)',(k,json.dumps(v)))
        original=json.dumps({'model':'f','longtake_enabled':True,'output':'saved.png'})
        db.execute('INSERT INTO jobs VALUES (?)',(original,))
        migrate(db);migrate(db)
        result={r['key']:json.loads(r['value']) for r in db.execute('SELECT * FROM settings')}
        self.assertEqual([r[0] for r in db.execute('SELECT id FROM external_models')],['q'])
        self.assertEqual(result,settings|{'create_model':'','image_overrides':{'q':{'seed':42}},'video_overrides':{'h3':{'seed':71,'attention_chunks':56}}})
        self.assertEqual(db.execute('SELECT payload FROM jobs').fetchone()[0],original)

    def test_saved_legacy_toggle_cannot_enable_extra_video_passes(self):
        old={'longtake_enabled':True,'seed':71}
        cleaned=validate(old)
        self.assertNotIn('longtake_enabled',cleaned)
        self.assertEqual(cleaned['seed'],71)
        self.assertTrue(old['longtake_enabled'])
        self.assertNotIn('longtake_enabled',options({'id':'h3'},{'video_overrides':{'h3':old}},False))
        captured=capture_request({'video_model':'h3'},{'video':True,'video_parameters':old},lambda *_:{'id':'h3'})
        self.assertNotIn('longtake_enabled',captured['_video_request']['parameters'])
        self.assertFalse(any(k.startswith('fibo') for k in PROFILES))


if __name__=='__main__':unittest.main()

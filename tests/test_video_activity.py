import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
from h3chat.video_activity import snapshot,describe


class VideoActivityTests(unittest.TestCase):
    def job(self):
        return {'id':'a'*32,'status':'running','stage':'Riutilizzo modello · Qwen','error':'','created':100,
                'payload':json.dumps({'settings':{'_video_edit':{'patches':[{'clip':n} for n in range(1,65)]}}})}

    def test_planning_clip_survives_generic_engine_stage_and_other_jobs_are_ignored(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/'server.log';p.write_text('21:00:00 [INFO] Lavoro aaaaaaaa · Post-produzione · istruzioni clip 49 · 64 selezionati\n21:00:01 [INFO] Lavoro aaaaaaaa · Riutilizzo modello · Qwen\n21:00:02 [INFO] Lavoro bbbbbbbb · Post-produzione · istruzioni clip 63 · 64 selezionati\nraw user prompt must not be exposed\n',encoding='utf-8')
            value=snapshot(folder,self.job(),server_log=p)
            self.assertEqual(value['stage'],'Preparazione istruzioni · clip 49 di 64')
            self.assertEqual(value['clips_completed'],0)
            self.assertNotIn('raw user prompt',json.dumps(value))
            self.assertNotIn('clip 63',json.dumps(value))

    def test_generation_and_completed_clips_are_separate_from_plans(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);p=root/'server.log';p.write_text('21:00:00 [INFO] Lavoro aaaaaaaa · Post-produzione · istruzioni clip 64 · 64 selezionati\n21:00:01 [INFO] Lavoro aaaaaaaa · Post-produzione · clip 2 · modifica 2/64 · Generazione video · 3/12 passi\n',encoding='utf-8')
            out=root/'outputs'/('a'*32);out.mkdir(parents=True);(out/'scenes.json').write_text(json.dumps({'revision_request':[],'revision_completed':[1],'revision_plans':{'1':{},'2':{}}}))
            value=snapshot(root,self.job(),server_log=p)
            self.assertEqual(value['phase'],'generation');self.assertEqual(value['active_clip'],2)
            self.assertEqual(value['clips_completed'],1);self.assertEqual(value['instructions_saved'],2)

    def test_endpoint_is_scoped_to_current_chat(self):
        store=SimpleNamespace(chat=Mock(),one=Mock(return_value=None));app=SimpleNamespace(store=store)
        with self.assertRaises(ValueError):describe(app,'chat','a'*32)
        self.assertEqual(store.one.call_args.args[1],('a'*32,'chat'))


if __name__=='__main__':unittest.main()

import json,tempfile,unittest
from pathlib import Path
from h3chat.poster_plan_progress import Progress,FieldLimit

class ProgressTests(unittest.TestCase):
    def test_decoded_bounds_follow_nested_fields_and_unicode_escapes(self):
        schema={'type':'object','properties':{'variants':{'type':'array','items':{'type':'object','properties':{'copy':{'type':'string','maxLength':3}}}}}}
        with tempfile.TemporaryDirectory() as d:
            progress=Progress(schema,Path(d),1,lambda value:None)
            text=json.dumps({'variants':[{'copy':'aé😀'}]},ensure_ascii=True)
            for n in range(1,len(text)+1):progress(text[:n])
            progress.finish()
            self.assertEqual(json.loads((Path(d)/'poster-plan-1.partial-state.json').read_text())['status'],'completed')
            bad=Progress(schema,Path(d),2,lambda value:None)
            with self.assertRaises(FieldLimit) as error:bad(json.dumps({'variants':[{'copy':'aé😀x'}]},ensure_ascii=True))
            self.assertEqual(error.exception.path,'$.variants[0].copy')
            self.assertEqual(error.exception.count,4)
            self.assertTrue((Path(d)/'poster-plan-2.partial.json').is_file())
    def test_copy_is_not_cut_when_another_field_exceeds_its_own_limit(self):
        schema={'type':'object','properties':{'copy':{'type':'string','maxLength':100},'image_prompt':{'type':'string','maxLength':4}}}
        with tempfile.TemporaryDirectory() as d:
            p=Progress(schema,Path(d),1,lambda value:None)
            with self.assertRaises(FieldLimit) as error:p(json.dumps({'copy':'Contenuto obbligatorio','image_prompt':'12345'}))
            self.assertEqual(error.exception.path,'$.image_prompt')
            self.assertIn('Contenuto obbligatorio',p.raw)

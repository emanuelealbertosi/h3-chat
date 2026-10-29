"""New spatial plans select immutable source blocks instead of copying public text."""
import copy,json,tempfile,threading,unittest
from pathlib import Path
from types import SimpleNamespace
from h3chat import poster_visual as visual
from h3chat.posters import options
from h3chat.slides import FORMATS
from test_poster_visual import layout,referenced

ROOT=Path(__file__).resolve().parents[1]

class PosterContentIdTests(unittest.TestCase):
    def test_schema_contains_only_catalog_ids_and_no_generated_text_field(self):
        blocks=visual.content_blocks('# Officina Delta\n\n**12 ore**\nDettagli con apostrofi, 8 € e simboli.');schema=visual.schema(blocks)
        fields=schema['properties']['zones']['items']['properties'];self.assertNotIn('text',fields);self.assertIn('content_ids',schema['properties']['zones']['items']['required'])
        self.assertEqual(fields['content_ids']['items']['enum'],['B1','B2','B3']);self.assertFalse(schema['properties']['zones']['items']['additionalProperties'])
        self.assertEqual(fields['content_ids']['maxItems'],len(blocks))
        from h3chat.native_json_schema import grammar_schema
        self.assertEqual(grammar_schema(schema)['properties']['zones']['items']['properties']['content_ids'],fields['content_ids'])
        self.assertEqual([b['text'] for b in blocks],['Officina Delta','12 ore','Dettagli con apostrofi, 8 € e simboli.'])
    def test_server_reconstructs_exact_original_lines_once_with_free_zone_order(self):
        original='# Occhiello Delta\nTitolo già pronto\n\n12 novembre · ore 17\nTesto con “virgolette”, emoji 🌟 e numeri 123.';blocks=visual.content_blocks(original)
        value=layout();value['zones'][0].pop('text');value['zones'][0]['content_ids']=['B2'];value['zones'][1].pop('text');value['zones'][1]['content_ids']=['B1','B3','B4']
        result=visual.resolve_content(value,blocks)
        self.assertEqual(result['zones'][0]['text'],blocks[1]['text']);self.assertEqual(result['zones'][1]['text'],'\n'.join(blocks[n]['text'] for n in (0,2,3)));self.assertEqual(result['content_blocks'],blocks);self.assertNotIn('text',value['zones'][0])
    def test_unknown_duplicate_missing_or_reordered_ids_cannot_change_copy(self):
        blocks=visual.content_blocks('Prima frase\nSeconda frase\nTerza frase');base=referenced(layout());base['zones'][0]['content_ids']=['B1'];base['zones'][1]['content_ids']=['B2','B3']
        variants=[]
        unknown=copy.deepcopy(base);unknown['zones'][1]['content_ids']=['B2','B999'];variants.append(unknown)
        duplicate=copy.deepcopy(base);duplicate['zones'][1]['content_ids']=['B1','B2','B3'];variants.append(duplicate)
        missing=copy.deepcopy(base);missing['zones'][1]['content_ids']=['B3'];variants.append(missing)
        repeated=copy.deepcopy(base);repeated['zones'][1]['content_ids']=['B2','B2','B3'];variants.append(repeated)
        reordered=copy.deepcopy(base);reordered['zones'][1]['content_ids']=['B3','B2'];variants.append(reordered)
        injected=copy.deepcopy(base);injected['zones'][1]['text']='Parole aggiunte';variants.append(injected)
        for value in variants:
            with self.subTest(value=value),self.assertRaises(ValueError):visual.resolve_content(value,blocks)
    def test_saved_legacy_text_layout_still_validates_without_catalog(self):
        value=layout();fitted=visual.validate(value,*FORMATS['9:16'],5,ROOT)
        self.assertEqual([z['text'] for z in fitted['zones']],[z['text'] for z in value['zones']]);self.assertNotIn('content_blocks',fitted)
    def test_footer_overlap_remains_invalid_and_feedback_has_both_reserved_rectangles(self):
        value=layout();footer=copy.deepcopy(value['zones'][1]);footer.update(id='footer',role='footer',text='Contatti di esempio',bbox=[60,800,940,900]);value['zones'].append(footer)
        feedback=visual.collision_feedback(value);self.assertIn('other_text_area',feedback);self.assertIn('footer',feedback);self.assertIn('banda esclusiva',feedback)
        with self.assertRaisesRegex(ValueError,'sovrappongono'):visual.validate(value,*FORMATS['9:16'],5,ROOT)
    def test_planner_uses_new_schema_and_server_text_then_checks_real_collisions(self):
        value=referenced(layout());bad=copy.deepcopy(value);bad['zones'][1]['content_ids']=['B1','B2'];bad['objects'][0]['bbox']=[650,700,950,800];calls=[]
        def complete(messages,*args,**kwargs):
            calls.append((copy.deepcopy(messages),kwargs['schema']));return json.dumps(bad if len(calls)==1 else value),'stop'
        opts=options()|{'_settings':{'context':32768,'max_tokens':8000}};row={'copy':'OPEN LAB\n12 novembre · ore 17 · Aula Blu','visual_plan':'A fictional exhibition'}
        with tempfile.TemporaryDirectory() as folder:result=visual.plan(SimpleNamespace(completion=complete),[{'role':'system','content':'Poster'}],row,opts,*FORMATS['9:16'],ROOT,threading.Event(),lambda _:None,Path(folder),0)
        self.assertEqual(len(calls),2);self.assertIn('content_blocks',calls[0][0][-1]['content']);self.assertIn('più di una volta',calls[1][0][-1]['content']);self.assertIn('CONFLITTI DA CORREGGERE',calls[1][0][-1]['content'])
        self.assertEqual([z['text'] for z in result['zones']],row['copy'].splitlines());self.assertTrue(all(z['renderer']=='html' for z in result['zones']))
        self.assertNotIn('text',calls[0][1]['properties']['zones']['items']['properties'])
    def test_planner_does_not_accept_legacy_text_even_if_all_words_are_correct(self):
        opts=options()|{'_settings':{'context':32768,'max_tokens':8000}};value=layout();row={'copy':'\n'.join(z['text'] for z in value['zones']),'visual_plan':'A fictional exhibition'}
        with tempfile.TemporaryDirectory() as folder,self.assertRaisesRegex(ValueError,'soltanto content_ids'):visual.plan(SimpleNamespace(completion=lambda *a,**kw:(json.dumps(value),'stop')),[{'role':'system','content':'Poster'}],row,opts,*FORMATS['9:16'],ROOT,threading.Event(),lambda _:None,Path(folder),0)

if __name__=='__main__':unittest.main()

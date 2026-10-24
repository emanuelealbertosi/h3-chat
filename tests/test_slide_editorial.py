import json
import threading
import unittest
from unittest.mock import Mock
from h3chat.slide_editorial import prepare,validate,SCHEMA,schema_for,recover_drafts
from h3chat.downloads import Cancelled


class EditorialTests(unittest.TestCase):
    def test_local_grammar_is_structural_but_application_still_rejects_oversized_text(self):
        # The production parser rejected char{0,12000} before inference. Do not
        # send large repetitions; retain the same size checks after parsing.
        for field in ('content','visual_plan','notes'):
            self.assertEqual(SCHEMA['properties'][field],{'type':'string'})
        for field,size in (('content',8001),('visual_plan',2001),('notes',12001)):
            with self.subTest(field=field),self.assertRaisesRegex(ValueError,'Testi'):
                validate(self.plan|{field:'x'*size},{'R1'})

    def setUp(self):
        self.plan={'content':'Spiegazione con esempio [R1].','visual_plan':'Confronto prima/dopo.',
            'notes':'Approfondimento del relatore [R1].','sources':['R1']}
        self.settings={'max_tokens':40000,'think_level':'high','llm_timeout':1800}
        self.outline={'slides':[{'title':'A','purpose':'Spiegare A'},{'title':'B','purpose':'Spiegare B'}]}

    def test_per_page_bounded_plan_respects_explicit_density_and_preserves_sources(self):
        seen=[];saved=[]
        def complete(messages,settings,cancel,**kw):
            seen.append((messages,settings));return json.dumps(self.plan),'stop'
        engine=Mock();engine.completion.side_effect=complete
        prepare(engine,[{'role':'user','content':'Massimo 35 parole, note 100–160 parole.'}],self.outline,
                self.settings,threading.Event(),lambda _:None,{'R1'},lambda i,v:saved.append((i,v)))
        self.assertEqual(len(saved),2)
        for messages,settings in seen:
            self.assertIn('Massimo 35 parole',messages[0]['content'])
            self.assertIn('limiti espliciti',messages[-1]['content'])
            self.assertEqual(settings['think_level'],'off');self.assertEqual(settings['max_tokens'],3500)
            self.assertEqual(settings['llm_timeout'],1800)
        self.assertEqual(self.outline['slides'][1]['editorial'],self.plan)
        self.assertNotIn('editorial',seen[1][0][-1]['content'])

    def test_long_timeout_reaches_editorial_without_a_five_minute_cap(self):
        engine=Mock();engine.completion.return_value=(json.dumps(self.plan),'stop')
        prepare(engine,[],self.outline,self.settings|{'llm_timeout':6000},threading.Event(),lambda _:None,{'R1'},lambda i,v:None)
        self.assertEqual([c.args[1]['llm_timeout'] for c in engine.completion.call_args_list],[6000,6000])

    def test_unknown_source_and_truncated_plan_never_reach_composition(self):
        with self.assertRaisesRegex(ValueError,'fonti'):validate(self.plan|{'sources':['inventata']},{'R1'})
        engine=Mock();engine.completion.return_value=(json.dumps(self.plan),'length');saved=Mock()
        with self.assertRaisesRegex(ValueError,'slide 1'):
            prepare(engine,[],self.outline,self.settings,threading.Event(),lambda _:None,{'R1'},saved)
        saved.assert_not_called();self.assertNotIn('editorial',self.outline['slides'][0])

    def test_source_schema_is_catalog_bound_and_no_catalog_forces_empty_list(self):
        self.assertEqual(schema_for({'R3','I2'})['properties']['sources']['items']['enum'],['I2','R3'])
        self.assertEqual(schema_for(set())['properties']['sources']['maxItems'],0)
        self.assertNotIn('enum',SCHEMA['properties']['sources']['items'])

    def test_bad_reference_gets_one_targeted_repair_without_losing_content_or_notes(self):
        engine=Mock();bad=self.plan|{'sources':['S1']};engine.completion.side_effect=[(json.dumps(bad),'stop'),(json.dumps(self.plan),'stop')]
        saved=Mock();invalid=Mock();stages=[]
        prepare(engine,[],{'slides':[self.outline['slides'][0]]},self.settings,threading.Event(),stages.append,{'R1'},saved,invalid)
        self.assertEqual(engine.completion.call_count,2);invalid.assert_called_once()
        saved.assert_called_once_with(0,self.plan)
        repair=engine.completion.call_args.args[0]
        self.assertEqual(json.loads(repair[-2]['content']),bad)
        self.assertIn('Non rinumerare S1 in R1',repair[-1]['content'])
        self.assertIn('[DA VERIFICARE]',repair[-1]['content'])
        self.assertTrue(any('correzione dei riferimenti' in s for s in stages))

    def test_second_bad_reference_stops_and_preserves_candidate_instead_of_deleting_sources(self):
        engine=Mock();bad=self.plan|{'sources':['inventata']};engine.completion.return_value=(json.dumps(bad),'stop');saved=Mock();invalid=Mock()
        with self.assertRaisesRegex(ValueError,'bozza conservata'):
            prepare(engine,[],self.outline,self.settings,threading.Event(),lambda _:None,{'R1'},saved,invalid)
        self.assertEqual(engine.completion.call_count,2);self.assertEqual(invalid.call_count,2);saved.assert_not_called()
        self.assertEqual(json.loads(invalid.call_args.args[1]),bad)

    def test_inline_unknown_reference_is_rejected_even_if_sources_list_is_valid(self):
        with self.assertRaisesRegex(ValueError,'R99'):
            validate(self.plan|{'notes':'Dati attribuiti a [R99].'},{'R1'})

    def test_failed_plans_recovered_only_for_same_request_and_rechecked_against_current_sources(self):
        app=Mock();opts={'count':2,'engine':'llm'};payload={'prompt':'Crea 2 slide\n1. A\n2. B','project_id':'project','media':[],'settings':{'_slides':opts}}
        old=self.plan|{'slide':1,'sources':['R99'],'content':'Bozza precedente con [R99].'}
        app.store.one.return_value={'id':'previous','payload':json.dumps(payload),'meta':json.dumps({'slide_editorial_plan':[old]})}
        ident,drafts=recover_drafts(app,{'id':'current','chat_id':'chat'},payload,opts)
        self.assertEqual(ident,'previous');self.assertEqual(len(drafts),1)
        engine=Mock();engine.completion.return_value=(json.dumps(self.plan),'stop');saved=Mock()
        prepare(engine,[],{'slides':[self.outline['slides'][0]]},self.settings,threading.Event(),lambda _:None,{'R1'},saved,previous=drafts)
        instruction=engine.completion.call_args.args[0][-1]['content']
        self.assertIn('Bozza precedente con [R99]',instruction);self.assertIn('NON una fonte',instruction)
        self.assertEqual(engine.completion.call_args.kwargs['schema']['properties']['sources']['items']['enum'],['R1'])
        saved.assert_called_once_with(0,self.plan)
        self.assertEqual(recover_drafts(app,{'id':'new','chat_id':'chat'},payload|{'project_id':'other'},opts),(None,{}))

    def test_cancel_does_not_plan_next_page(self):
        cancel=threading.Event();saved=[]
        engine=Mock();engine.completion.return_value=(json.dumps(self.plan),'stop')
        def save(i,v):saved.append(i);cancel.set()
        with self.assertRaises(Cancelled):prepare(engine,[],self.outline,self.settings,cancel,lambda _:None,{'R1'},save)
        self.assertEqual(saved,[0]);self.assertEqual(engine.completion.call_count,1)


if __name__=='__main__':unittest.main()

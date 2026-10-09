import copy,json,re,threading,unittest
from unittest.mock import Mock
from h3chat.downloads import Cancelled
from h3chat.infographic_animation import ensure,playable
from h3chat.infographic_choreography import targets,apply_plan,repair

HTML='''<!doctype html><html><head><style>body{background:#f7f3e8}.col{display:grid;grid-template-columns:1fr 1fr}</style></head>
<body><main class="col"><section id="example"><h1>1101 × 1011</h1><p>Riporti: 1 + 1 = 10 [D1]</p>
<img data-asset-id="picture1" alt="Figura originale"/></section><div data-video-asset-id="clip1"></div></main></body></html>'''


def plan_for(html=HTML):
    rows=targets(html);heading=next(row for row in rows if row['tag']=='h1');image=next(row for row in rows if row['tag']=='img')
    return {'animations':[{'target':heading['id'],'motion':'slide','start':.4,'duration':.8,'out':-1,'ease':'smooth'},
                          {'target':image['id'],'motion':'pan','start':1.5,'duration':2,'out':-1,'ease':'linear'}]}


class ChoreographyTests(unittest.TestCase):
    def test_targets_skip_metadata_hidden_nodes_and_keep_exact_offsets(self):
        html=HTML.replace('</body>','<template><h1>Nascosto</h1></template><div hidden>Nascosto</div><p style="display:none">Nascosto</p></body>')
        for row in targets(html):
            self.assertEqual(html[row['offset']:row['offset']+len(row['raw'])],row['raw'])
            self.assertNotIn('Nascosto',row['text']);self.assertNotIn('background:#',row['text'])
        self.assertTrue(any(row['asset_id']=='picture1' for row in targets(html)))

    def test_plan_changes_only_attributes_preserving_content_css_and_assets(self):
        plan=plan_for();result=apply_plan(HTML,targets(HTML),plan,9.3)
        self.assertTrue(playable(result,9.3))
        stripped=re.sub(r' data-(?:motion|start|duration|out|ease)="[^"]*"','',result)
        self.assertEqual(stripped,HTML)
        self.assertIn('data-asset-id="picture1"',result);self.assertIn('data-video-asset-id="clip1"',result)

    def test_existing_invalid_animation_attributes_are_replaced(self):
        html=HTML.replace('<h1>','<h1 data-motion="fade" data-start="99" data-out="99" data-duration="0">')
        result=apply_plan(html,targets(html),plan_for(html),9.3)
        heading=re.search(r'<h1[^>]*>',result)[0]
        self.assertEqual(heading.count('data-motion='),1);self.assertNotIn('99',heading);self.assertNotIn('data-out',heading)
        self.assertTrue(playable(result,9.3))

    def test_invalid_plans_are_rejected_without_partial_output(self):
        for key,value in (('target','unknown'),('target',[]),('motion','javascript'),('start',float('nan')),
                          ('start',10),('duration',0),('duration',True),('duration',100),('out',.1),('ease','invalid')):
            plan=copy.deepcopy(plan_for());plan['animations'][0][key]=value
            with self.subTest(key=key,value=value),self.assertRaises(ValueError):apply_plan(HTML,targets(HTML),plan,9.3)
        plan=plan_for();plan['animations'].append(plan['animations'][0])
        with self.assertRaises(ValueError):apply_plan(HTML,targets(HTML),plan,9.3)

    def test_static_rewrite_uses_original_scene_for_llm_directed_choreography(self):
        engine=Mock();engine.completion.side_effect=[('<main><h1>Altra slide sbagliata</h1></main>','stop'),(json.dumps(plan_for()),'stop')]
        updates=[];stages=[];settings={'max_tokens':40000,'temperature':.7}
        result=ensure(engine,[{'role':'user','content':'SCENA 8: spiegare i riporti'}],settings,threading.Event(),HTML,9.3,updates.append,stages.append)
        self.assertTrue(playable(result,9.3));self.assertIn('1101 × 1011',result);self.assertNotIn('Altra slide',result)
        self.assertEqual(updates[-1],result);self.assertEqual(settings['max_tokens'],40000)
        call=engine.completion.call_args;self.assertIn('SCENA 8',str(call.args[0]));self.assertIn('1101 × 1011',str(call.args[0]))
        self.assertIn('animations',call.kwargs['schema']['properties']);self.assertTrue(stages)

    def test_bad_target_retries_once_then_reports_and_never_streams_json_to_canvas(self):
        good=plan_for();bad=copy.deepcopy(good);bad['animations'][0]['target']='not-in-catalog'
        engine=Mock();engine.completion.side_effect=[(json.dumps(bad),'stop'),(json.dumps(good),'stop')];updates=[]
        result=repair(engine,[],{'max_tokens':40000},threading.Event(),HTML,9.3,updates.append)
        self.assertTrue(playable(result,9.3));self.assertEqual(engine.completion.call_count,2);self.assertEqual(updates,[result])
        engine=Mock();engine.completion.return_value=('<h1>Statico</h1>','stop')
        with self.assertRaisesRegex(ValueError,'due tentativi'):repair(engine,[],{},threading.Event(),HTML,9.3,lambda _:None)
        self.assertEqual(engine.completion.call_count,2)

    def test_cancellation_and_provider_failure_are_not_retried(self):
        cancel=threading.Event();cancel.set();engine=Mock()
        with self.assertRaises(Cancelled):repair(engine,[],{},cancel,HTML,9.3,lambda _:None)
        engine.completion.assert_not_called()
        engine.completion.side_effect=RuntimeError('Provider unavailable')
        with self.assertRaises(RuntimeError):repair(engine,[],{},threading.Event(),HTML,9.3,lambda _:None)
        self.assertEqual(engine.completion.call_count,1)

    def test_playable_scene_never_calls_repair(self):
        html='<h1 data-motion="fade">Pronto</h1>';engine=Mock()
        self.assertEqual(ensure(engine,[],{},threading.Event(),html,8,lambda _:None),html)
        engine.completion.assert_not_called()

    def test_empty_or_truncated_rewrite_can_repair_existing_layout(self):
        for first in [('<style>body{color:red}</style>','stop'),('<h1>Troncato','length')]:
            with self.subTest(first=first):
                engine=Mock();engine.completion.side_effect=[first,(json.dumps(plan_for()),'stop')]
                html=ensure(engine,[],{},threading.Event(),HTML,9.3,lambda _:None)
                self.assertTrue(playable(html,9.3));self.assertIn('1101 × 1011',html)


if __name__=='__main__':unittest.main()

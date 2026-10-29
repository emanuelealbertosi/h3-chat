import base64,copy,json,tempfile,threading,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from test_image_batch import PNG
from test_poster_visual import layout
from test_posters import plan as content_plan
from test_poster_typography import PosterTypographyTests
from h3chat import poster_overlay as overlay,poster_visual as visual
from h3chat.poster_typography import enqueue_creative,run_creative,revise
from h3chat.posters import options,build
from h3chat.slides import PREFIX,FORMATS

ROOT=Path(__file__).resolve().parents[1]
def prepared():
    value=layout()
    for zone in value['zones']:zone['renderer']='html'
    return visual.validate(value,*FORMATS['A3'],5,ROOT,options())
def fragments(value):return {z['id']:'<p style="margin:0;font-size:32px">'+z['text']+'</p>' for z in value['zones'] if z['renderer']=='html'}
def response(value):return {'zones':[{'id':key,'html':text} for key,text in value.items()]}
PROOF={'pages':[{'issue':False,'out_of_bounds':[],'poster_overflow':[]}],'renderer':'CPU offline','visual_review':False}

class OverlayTests(unittest.TestCase):
    def test_measure_accepts_every_poster_format_without_assuming_a3(self):
        value=prepared();parts=fragments(value);calls=[]
        app=SimpleNamespace(data=ROOT/'work'/'measure-test',engine=SimpleNamespace(tool_call=lambda *a,**kw:calls.append(a[1]) or PROOF))
        from h3chat.posters import FORMATS_POSTER
        for format in FORMATS_POSTER:
            overlay.measure(app,value,parts,format,*FORMATS[format],app.data/'outputs'/format,threading.Event(),lambda _:None,ROOT/'work'/'measure.log')
        self.assertEqual([c['deck']['poster']['format'] for c in calls],list(FORMATS_POSTER))
    def test_expressive_default_keeps_background_unlettered_and_accepts_local_svg_gradients(self):
        self.assertEqual(options()['typography_engine'],'expressive');self.assertEqual(options()['text_renderer'],'html')
        value=prepared();parts=fragments(value)
        parts['title']='''<svg viewBox="0 0 900 150" style="width:100%;height:150px"><defs><linearGradient id="ink"><stop offset="0" stop-color="#ffe49a"/><stop offset="1" stop-color="#f37855"/></linearGradient></defs><text x="10" y="110" style="font-family:BebasNeue;font-size:120px;fill:url('#ink');paint-order:stroke;stroke:#14202d;stroke-width:2">OPEN LAB</text></svg>'''
        valid=overlay.validate_fragments(response(parts),value);markup=overlay.compose(value,'f'*32,*FORMATS['A3'],valid)
        self.assertIn('id="title-ink"',markup);self.assertIn('url(#title-ink)',markup);self.assertEqual(markup.count('data-asset-id='),1)
        moss=json.loads(visual.moss_prompt(value,1280,1810));self.assertNotIn('"label": "text"',json.dumps(moss));self.assertNotIn('OPEN LAB',json.dumps(moss['items']));self.assertIn('Unlettered background',moss['summary']['caption'])
    def test_html_list_bullets_are_formatting_and_words_remain_exact(self):
        value=prepared();parts=fragments(value);zone=next(z for z in value['zones'] if z['id']=='facts')
        zone['text']='Cosa impari\n• Primo elemento\n• Secondo elemento'
        parts['facts']='<h3>Cosa impari</h3><ul><li>Primo elemento</li><li>Secondo elemento</li></ul>'
        self.assertEqual(overlay.validate_fragments(response(parts),value),parts)
        parts['facts']=parts['facts'].replace('Secondo','Altro')
        with self.assertRaisesRegex(ValueError,'Mancanti'):overlay.validate_fragments(response(parts),value)

    def test_rejects_script_external_resources_escape_tricks_duplicate_ids_and_changed_copy(self):
        value=prepared();base=fragments(value)
        bad=['<script>OPEN LAB</script>','<p onclick="alert(1)">OPEN LAB</p>','<img src="https://example.test/a.png"><p>OPEN LAB</p>',
             '<svg><text fill="url(https://example.test/x)">OPEN LAB</text></svg>',
             '<p style="background:u\\72l(https://example.test/x)">OPEN LAB</p>',
             '<p style="position:fixed">OPEN LAB</p>','<p id="x">OPEN LAB</p><svg id="x"></svg>',
             '<style>p{color:red}</style><p>OPEN LAB</p>','<p>OPEN LAB EXTRA</p>','<p>OPEN</p>',
             '<svg><use href="#x"/><text>OPEN LAB</text></svg>']
        for markup in bad:
            with self.subTest(markup=markup),self.assertRaises(ValueError):overlay.validate_fragments(response(base|{'title':markup}),value)
        with self.assertRaises(ValueError):overlay.validate_fragments({'zones':response(base)['zones']*2},value)
    def test_svg_ids_are_independent_between_zones_and_split_letters_preserve_exact_copy(self):
        value=prepared();parts=fragments(value)
        for zone in value['zones']:
            parts[zone['id']]='<svg><defs><linearGradient id=ink></linearGradient></defs><text fill="url(&quot;#ink&quot;)">'+''.join('<tspan>'+c+'</tspan>' for c in zone['text'])+'</text></svg>'
        markup=overlay.compose(value,'f'*32,*FORMATS['A3'],parts)
        for ident in parts:self.assertIn('id="'+ident+'-ink"',markup);self.assertIn('url(#'+ident+'-ink)',markup)
    def test_real_background_ink_correction_keeps_accent_gradients_and_exact_copy(self):
        value=prepared();value['zones'][1].update(color='#17242d',original_color='#ffffff',contrast_adjusted=True);parts=fragments(value)
        parts['facts']='<p style="color:#fff;background:linear-gradient(90deg,#ffeeaa,#f37855)">'+value['zones'][1]['text']+'</p>'
        markup=overlay.compose(value,'f'*32,*FORMATS['A3'],parts)
        self.assertIn('color:#17242d;background:linear-gradient(90deg,#ffeeaa,#f37855)',markup)
    def test_validation_and_cpu_overflow_get_one_repair_then_fail_without_silent_fallback(self):
        value=prepared();parts=fragments(value);calls=[];checks=[]
        def complete(messages,*a,**kw):calls.append(copy.deepcopy(messages));return json.dumps(response(parts)),'stop'
        def verify(data,attempt):
            checks.append(attempt)
            if attempt==0:raise ValueError('title: testo tagliato dal riquadro')
        result=overlay.plan(SimpleNamespace(completion=complete),[],value,options()|{'_settings':{'max_tokens':20000,'context':32000}},*FORMATS['A3'],threading.Event(),lambda _:None,verify)
        self.assertEqual(result,parts);self.assertEqual(checks,[0,1]);self.assertIn('testo tagliato',calls[1][-1]['content'])
        with self.assertRaisesRegex(ValueError,'dopo la correzione'):overlay.plan(SimpleNamespace(completion=lambda *a,**kw:('{}','stop')),[],value,options()|{'_settings':{'max_tokens':8000,'context':16000}},*FORMATS['A3'],threading.Event(),lambda _:None)
    def test_content_and_measured_fit_have_separate_bounded_repairs(self):
        value=prepared();parts=fragments(value);calls=[];checks=[]
        def complete(*args,**kw):
            calls.append(1)
            if len(calls)==1:return '{}','stop'
            return json.dumps(response(parts)),'stop'
        def verify(data,attempt):
            checks.append(attempt)
            if len(checks)==1:raise overlay.TypographyOverflow({'poster_overflow':[{'id':'title','reason':'testo tagliato dal riquadro'}]})
        result=overlay.plan(SimpleNamespace(completion=complete),[],value,options()|{'_settings':{'max_tokens':8000,'context':16000}},*FORMATS['A3'],threading.Event(),lambda _:None,verify)
        self.assertEqual(result,parts);self.assertEqual(len(calls),3);self.assertEqual(checks,[1,2])

    def test_plan_copy_is_verified_before_images(self):
        value=prepared();value['zones'][1]['text']='Testo perso';opts=options()|{'_settings':{'max_tokens':8000,'context':16000}}
        with tempfile.TemporaryDirectory() as folder,self.assertRaisesRegex(ValueError,'tutti i contenuti'):
            visual.plan(SimpleNamespace(completion=lambda *a,**kw:(json.dumps(value),'stop')),[{'role':'system','content':'Poster'}],{'copy':'OPEN LAB\n12 novembre · ore 17 · Aula Blu','visual_plan':'Robot'},opts,*FORMATS['A3'],ROOT,threading.Event(),lambda _:None,Path(folder),0)

class CreativeRevisionTests(PosterTypographyTests):
    def test_queue_worker_creates_new_expressive_revision_without_touching_image_or_settings(self):
        chat,value=self.artifact();before=self.app.store.settings();ticket=enqueue_creative(self.app,chat,{'artifact_id':value['id'],'page':1,'typography':{'lettering':'comic','text_effect':'outline'},'prompt':'Usa colori caldi e titoletti dinamici'})
        job=self.app.store.one('SELECT * FROM jobs WHERE id=?',(ticket['job_id'],));payload=json.loads(job['payload']);spec=payload['settings']['_poster_creative'];self.assertEqual(spec['page'],1)
        self.assertFalse(payload['settings']['vision_enabled']);self.assertNotIn('_posters',payload['settings'])
        with patch.object(self.app.engine,'configure'),patch.object(self.app.engine,'start_llama'),patch.object(self.app.engine,'completion',return_value=(json.dumps(response({'facts':'<p>INCONTRO 1 — IDEE</p><p>Una descrizione da conservare.</p>'})),'stop')) as complete,patch.object(self.app.engine,'tool_call',return_value=PROOF),patch.object(self.app.engine,'generate') as generate:
            run_creative(self.app,job,payload,payload['settings'],threading.Event(),lambda _:None,self.base/'revision.log')
        generate.assert_not_called();new=self.app.store.canvas_history.get(chat);deck=json.loads(new['content'][len(PREFIX):-4]);page=deck['pages'][0]
        self.assertNotEqual(value['id'],new['id']);self.assertEqual(new['media'],value['media']);self.assertEqual(self.app.store.settings(),before)
        self.assertEqual(self.app.store.canvas_history.get(chat,value['id'])['content'],value['content']);self.assertIn('poster_fragments',page)
        self.assertEqual(page['poster_layout']['zones'][0]['renderer'],'moss');self.assertNotIn('OPEN LAB',page['html'])
        self.assertEqual(json.loads(complete.call_args.args[0][-1]['content'])['typography_request'],spec['prompt']);self.assertNotIn(spec['prompt'],new['content'])
        preset=revise(self.app,chat,{'artifact_id':new['id'],'page':1,'typography':{'lettering':'neon'}});preset_deck=json.loads(preset['content'][len(PREFIX):-4])
        self.assertEqual(preset_deck['poster']['typography_engine'],'preset');self.assertNotIn('poster_fragments',preset_deck['pages'][0]);self.assertNotEqual(preset['id'],new['id']);self.assertEqual(preset['media'],new['media'])
        self.assertIn('poster_fragments',json.loads(self.app.store.canvas_history.get(chat,new['id'])['content'][len(PREFIX):-4])['pages'][0])
    def test_changed_source_after_queue_is_refused_before_llm(self):
        chat,value=self.artifact();ticket=enqueue_creative(self.app,chat,{'artifact_id':value['id'],'page':1});job=self.app.store.one('SELECT * FROM jobs WHERE id=?',(ticket['job_id'],));payload=json.loads(job['payload'])
        self.app.store.canvas_history.save(chat,value|{'title':'Cambiato','content':value['content'].replace('Prova','Prova modificata')},edit_id=value['id'])
        with patch.object(self.app.engine,'start_llama') as llama,self.assertRaisesRegex(ValueError,'cambiata dopo'):run_creative(self.app,job,payload,payload['settings'],threading.Event(),lambda _:None,self.base/'revision.log')
        llama.assert_not_called()

if __name__=='__main__':unittest.main()

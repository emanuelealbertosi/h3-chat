import copy,json,threading,unittest
from pathlib import Path
from unittest.mock import patch
from h3chat import poster_type,poster_visual
from h3chat.posters import options
from test_poster_visual import layout
from test_agent_media import AgentMediaTests as _AgentBase
from test_agent_runtime import decision
from h3chat.agent_state import load

class LetteringTests(unittest.TestCase):
    def test_body_section_headings_get_display_font_and_effect_without_styling_long_copy(self):
        value=layout();value['zones'][1].update(role='body',text='INCONTRO 1 — IDEE\nUna descrizione più lunga che deve restare leggibile e senza bagliore.',bbox=[60,700,940,950])
        opts=options(value={'text_effect':'neon'});fitted=poster_visual.validate(value,1280,2275,5,Path(__file__).resolve().parents[1],opts);blocks=fitted['zones'][1]['blocks']
        self.assertTrue(blocks[0]['heading']);self.assertEqual((blocks[0]['font_family'],blocks[0]['effect']),('BebasNeue','neon'));self.assertEqual((blocks[1]['font_family'],blocks[1]['effect']),('Manrope','plain'))
        html=poster_visual.compose(fitted,'x'*32,1280,2275);self.assertIn('data-poster-heading="true"',html);self.assertIn('0 0 9px',html)

    def test_short_slogan_role_mismatch_is_normalized_without_changing_copy(self):
        value=layout();value['zones'][0].update(role='body',renderer='moss',text='Impari, giochi, crei: il computer non ha più segreti!')
        fixed=poster_visual.normalize_renderers(value)
        self.assertEqual(fixed['zones'][0]['role'],'facts');self.assertEqual(fixed['zones'][0]['text'],value['zones'][0]['text']);self.assertEqual(value['zones'][0]['role'],'body')
        value['zones'][1].update(role='program',renderer='moss')
        self.assertEqual(poster_visual.normalize_renderers(value)['zones'][1]['renderer'],'html')

    def test_slogan_normalization_allows_repair_feedback_to_reach_geometry(self):
        import tempfile
        from types import SimpleNamespace
        initial=layout();initial['zones'][0]['role']='body';initial['objects'][0]['bbox']=[650,750,950,850]
        corrected=copy.deepcopy(initial);corrected['objects'][0]['bbox']=[650,250,950,550];calls=[]
        def complete(messages,*a,**kw):calls.append(copy.deepcopy(messages));return json.dumps(initial if len(calls)==1 else corrected),'stop'
        opts=options(value={'text_renderer':'moss_short','typography_engine':'preset'})|{'_settings':{'max_tokens':8000,'context':32768}}
        with tempfile.TemporaryDirectory() as d:result=poster_visual.plan(SimpleNamespace(completion=complete),[{'role':'system','content':'Poster'}],{'copy':'\n'.join(z['text'] for z in initial['zones']),'visual_plan':'Robot'},opts,1280,2275,Path(__file__).resolve().parents[1],threading.Event(),lambda _:None,Path(d),0)
        self.assertEqual(len(calls),2);self.assertIn('interseca',calls[1][-1]['content']);self.assertEqual(result['zones'][0]['role'],'facts')

    def test_explicit_prompt_overrides_saved_lettering_and_effect(self):
        out=options('Voglio scritte cinematografiche con effetto metallizzato',{'lettering':'comic','text_effect':'outline'})
        self.assertEqual(out['lettering'],'cinematic');self.assertEqual(out['text_effect'],'metallic')
        self.assertEqual(options('Scritte giocose senza effetti')['text_effect'],'plain')
        custom=options('Titoli in Bebas Neue, corpo in Cormorant',{'heading_font':'Caveat','body_font':'Manrope'})
        self.assertEqual((custom['heading_font'],custom['body_font']),('BebasNeue','Cormorant'))

    def test_all_styles_use_real_bundled_fonts_and_safe_css(self):
        root=Path(__file__).resolve().parents[1]
        for style in poster_type.PRESETS:
            zone=layout()['zones'][0]|{'renderer':'html'}
            z=poster_type.prepare(zone,{'lettering':style});font=poster_visual.font(str(root),40,700,z['font_family'])
            self.assertGreater(font.getlength('Stile professionale'),0)
            self.assertIn('font-family:',poster_type.css(z));self.assertNotIn('url(',poster_type.css(z))
        with self.assertRaises(ValueError):poster_type.prepare(zone|{'font_family':'../../outside'}, {})
        with self.assertRaises(ValueError):poster_type.prepare(zone|{'tracking':float('nan')}, {})

    def test_tracking_and_effect_space_are_measured_and_body_remains_readable(self):
        root=Path(__file__).resolve().parents[1];value=layout();value['zones'][0].update(renderer='html',font_family='Bangers',effect='extruded',tracking=1.3,italic=False)
        result=poster_visual.validate(value,1280,2275,5,root)
        html=poster_visual.compose(result,'x'*32,1280,2275)
        self.assertIn('font-family:Bangers',html);self.assertIn('text-shadow:1px',html)
        self.assertGreater(result['zones'][0]['effect_padding'],0)
        body=poster_type.prepare(value['zones'][1]|{'role':'program','effect':'neon'},{});self.assertEqual(body['effect'],'plain')


class PhotoPosterAgentTests(unittest.TestCase):
    setUp=_AgentBase.setUp
    tearDown=_AgentBase.tearDown

    def test_agent_edits_then_uses_exact_result_without_second_image_generation(self):
        import base64
        from test_image_batch import PNG
        from test_posters import plan,HTML
        original=self.app.upload({'name':'originale.png','data':base64.b64encode(PNG).decode()})
        self.app.save_settings({'context':32768,'max_tokens':3000,'vision_enabled':False})
        chat=self.app.store.create_chat()['id'];ticket=self.app.send(chat,{'prompt':'agent: Cambia la foto in stile cinema e crea una locandina','media':[original],'rag':False,'agent':{'allow_images':True,'confirm_writes':False}})
        job=self.app.store.one('SELECT * FROM jobs WHERE id=?',(ticket['job_id'],));steps=[0];edited={}
        def generate(model,settings,prompt,refs,ident,*args):
            self.assertEqual([r['id'] for r in refs],[original['id']]);folder=self.app.data/'outputs'/ident;folder.mkdir(parents=True,exist_ok=True);(folder/'image.png').write_bytes(PNG)
            edited.update(id=ident,name='ritoccata.png',mime='image/png',path=f'outputs/{ident}/image.png',generation={'seed':432})
            return dict(edited)
        def complete(messages,settings,cancel,**kw):
            if 'action' in (kw.get('schema') or {}).get('properties',{}):
                steps[0]+=1;data=json.loads(messages[-1]['content'])
                if steps[0]==1:return decision('edit_image',{'number':1,'prompt':'Trasforma in stile cinema, preserva la persona.','model_id':self.qwen['id']})
                if steps[0]==2:return decision('create_posters',{'prompt':'Crea una locandina usando la foto ritoccata, scritte cinematografiche','images':'existing','composition':'html','hero_asset_id':edited['id'],'source_artifact_ids':[data['artifacts'][0]['id']],'lettering':'cinematic'})
                return decision('finish',message='Locandina pronta.')
            if kw.get('schema'):return json.dumps(plan()),'stop'
            return HTML+f'<img data-asset-id="{edited["id"]}">','stop'
        with patch.object(self.app.engine,'prepare'),patch.object(self.app.engine,'start_llama'),patch.object(self.app.engine,'completion',side_effect=complete),patch.object(self.app.engine,'generate',side_effect=generate) as images:
            self.app.execute_job(job,threading.Event())
        state=load(self.app,chat,job['id']);self.assertEqual(state['status'],'done',state)
        self.assertEqual(images.call_count,1);self.assertEqual(state['usage']['images_started'],1)
        final=self.app.store.canvas_history.get(chat,state['artifacts'][-1]['id']);self.assertEqual([m['id'] for m in final['media']],[edited['id']])
        self.assertIn(edited['id'],final['content']);self.assertNotIn(original['id'],final['content'])

if __name__=='__main__':unittest.main()

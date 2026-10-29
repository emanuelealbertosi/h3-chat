import copy,json,threading,unittest
from unittest.mock import patch
from test_posters import PosterTests,plan
from test_image_batch import PNG
from h3chat import poster_visual as visual
from h3chat.posters import options,image_model
from h3chat.slides import PREFIX,validate_content


def layout():
    return {'art_caption':'A dynamic neon robot illustration in a luminous laboratory, integrated expressive OPEN LAB lettering.',
      'objects':[{'caption':'A playful robot leaning into a perspective scene','bbox':[650,250,950,550]}],
      'zones':[
       {'id':'title','role':'title','renderer':'moss','text':'OPEN LAB','bbox':[60,60,940,200],'font_size':110,'weight':800,'color':'#ffffff','align':'left','surface':'dark'},
       {'id':'facts','role':'facts','renderer':'html','text':'12 novembre · ore 17 · Aula Blu','bbox':[60,700,940,820],'font_size':40,'weight':600,'color':'#ffffff','align':'left','surface':'dark'}]}

def referenced(value):
    """Test-only mock response for the new reference schema, never a runtime fallback."""
    value=copy.deepcopy(value);index=0
    for zone in value['zones']:
        rows=[row for row in zone.pop('text').splitlines() if row.strip()]
        zone['content_ids']=['B'+str(index+i+1) for i in range(len(rows))];index+=len(rows)
    return value


class SharedLayoutTests(unittest.TestCase):
    def test_contrast_changes_only_html_ink_and_keeps_source_image_and_boxes(self):
        import tempfile,hashlib
        from pathlib import Path
        from PIL import Image
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'background.png';Image.new('RGB',(80,100),'#faf1df').save(path)
            before=hashlib.sha256(path.read_bytes()).hexdigest();value=layout();value['zones'][1]['color']='#8b9990'
            changed=visual.contrast(value,path)
            self.assertNotEqual(changed['zones'][1]['color'],value['zones'][1]['color']);self.assertTrue(changed['zones'][1]['contrast_adjusted'])
            self.assertEqual(changed['zones'][0],value['zones'][0]);self.assertEqual(changed['zones'][1]['bbox'],value['zones'][1]['bbox'])
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),before)

    def test_single_landscape_lead_is_not_mistaken_for_a_section_heading(self):
        from pathlib import Path
        zone=layout()['zones'][1]|dict(role='body',text='Una serata tra stelle, pianeti e galassie',font_size=28,weight=700)
        blocks,height=visual.typeset(zone,Path(__file__).resolve().parents[1],24,386*.97)
        self.assertFalse(blocks[0]['heading']);self.assertLessEqual(height,55.2)

    def test_copy_headings_get_hierarchy_without_new_words_or_moving_reserved_areas(self):
        from pathlib import Path
        root=Path(__file__).resolve().parents[1];value=layout();zone=value['zones'][1]
        zone.update(role='body',text='Metodo\nAttività pratiche e dimostrazioni guidate.\nProgramma\n• Introduzione\n• Laboratorio',font_size=26,bbox=[60,600,940,940])
        result=visual.validate(value,1280,2275,5,root);styled=result['zones'][1]
        self.assertEqual(styled['bbox'],zone['bbox']);self.assertEqual(styled['text'],zone['text'])
        self.assertEqual([b['lines'][0] for b in styled['blocks'] if b['heading']],['Metodo','Programma'])
        self.assertTrue(all(b['weight']>=750 for b in styled['blocks'] if b['heading']))
        self.assertEqual(' '.join(' '.join(b['lines']) for b in styled['blocks']).split(),zone['text'].split())

    def test_pixel_plan_is_converted_using_declared_canvas_not_clamped_or_guessed(self):
        from pathlib import Path
        root=Path(__file__).resolve().parents[1];value=layout();value['coordinate_space']='pixels'
        for item in value['objects']+value['zones']:item['bbox']=[n*axis/1000 for n,axis in zip(item['bbox'],[1280,2275,1280,2275])]
        result=visual.validate(value,1280,2275,5,root)
        self.assertEqual(result['zones'][1]['bbox'],[104,680,896,788]);self.assertEqual(result['coordinate_space'],'normalized')
        value['zones'][1]['bbox'][3]=2500
        with self.assertRaises(ValueError):visual.validate(value,1280,2275,5,root)

    def test_native_text_boxes_and_quiet_zones_share_coordinates_without_double_print(self):
        from pathlib import Path
        root=Path(__file__).resolve().parents[1]
        value=visual.validate(layout(),1280,1280*16/9,5,root)
        prompt=json.loads(visual.moss_prompt(value,1008,1792))
        self.assertEqual(prompt['items'][1]['label'],'text');self.assertEqual(prompt['items'][1]['text'],'OPEN LAB')
        self.assertEqual(prompt['items'][1]['bbox'],[-788,-444,-538,444])
        self.assertNotIn('12 novembre',json.dumps(prompt))
        for item in prompt['items']:
            self.assertNotRegex(item['caption'],r'Spell|supplied|HTML|application|original language')
        html=visual.compose(value,'generated-background',1280,1280*16/9)
        self.assertNotIn('OPEN LAB',html);self.assertIn('12 novembre',html)
        self.assertEqual(html.count('data-asset-id='),1);self.assertIn('top:70.0%',html)

    def test_invalid_layout_fails_before_gpu_not_clips_text(self):
        from pathlib import Path
        root=Path(__file__).resolve().parents[1]
        mutations=[lambda x:x['zones'].__setitem__(1,None),
         lambda x:x['zones'][1].update(bbox=[0,0,100,100]),
         lambda x:x['zones'][1].update(bbox=[60,60,940,200]),
         lambda x:x['zones'][1].update(text='molto lungo '*500,bbox=[60,700,940,701]),
         lambda x:x['zones'][1].update(renderer='moss',role='program'),
         lambda x:x['zones'][0].update(text='x'*81),
         lambda x:x['objects'][0].update(bbox=[100,700,900,810]),
         lambda x:x['objects'][0].update(bbox=[1,2,float('nan'),4])]
        for mutate in mutations:
            with self.subTest(mutation=str(mutate)):
                value=copy.deepcopy(layout());mutate(value)
                with self.assertRaises(ValueError):visual.validate(value,1280,2275,5,root)


class PosterMossTests(PosterTests):
    def test_expressive_default_validates_copy_and_cpu_layout_before_generating_unlettered_background(self):
        moss=self.qwen|dict(architecture='moss',sampler='euler',scheduler='sgm_uniform',steps=50,cfg=3)
        chat=self.app.store.create_chat()['id'];value=layout();value['art_caption']='A dynamic neon robot illustration in a luminous laboratory, with blank text surfaces.'
        events=[]
        with patch.object(self.app.engine,'require_model',side_effect=lambda ident,cap:moss if ident==self.qwen['id'] else self.app.catalog[ident]):
            ticket=self.app.send(chat,{'prompt':'Crea una locandina OPEN LAB','lab':'poster','poster':{'composition':'moss_layout','image_model':self.qwen['id']},'rag':False})
            job=self.app.store.one('SELECT * FROM jobs WHERE id=?',(ticket['job_id'],))
            def check(*a,**kw):events.append('CPU');return {'pages':[{'issue':False,'poster_overflow':[]}]}
            def generate(model,settings,prompt,refs,ident,*_):
                self.assertEqual(events,['CPU']);events.append('image');self.assertEqual(refs,[])
                native=json.loads(prompt);self.assertFalse(any(i['label']=='text' for i in native['items']));self.assertIn('Unlettered',native['summary']['caption'])
                folder=self.app.data/'outputs'/ident;folder.mkdir(parents=True);(folder/'image.png').write_bytes(PNG)
                return {'id':ident,'name':'image.png','path':f'outputs/{ident}/image.png','mime':'image/png','generation':{'seed':123}}
            typography={'zones':[{'id':z['id'],'html':'<p style="font-family:BebasNeue;margin:0;color:inherit">'+z['text']+'</p>'} for z in value['zones']]}
            with patch('h3chat.poster_overlay.measure',side_effect=check),patch.object(self.app.engine,'prepare'),patch.object(self.app.engine,'prepare_tools',side_effect=lambda h,*a,**k:(h,{},[],[])),patch.object(self.app.engine,'start_llama'),patch.object(self.app.engine,'stop'),patch.object(self.app.engine,'completion',side_effect=[(json.dumps(plan()),'stop'),(json.dumps(referenced(value)),'stop'),(json.dumps(typography),'stop')]),patch.object(self.app.engine,'generate',side_effect=generate):self.app.execute_job(job,threading.Event())
        row=self.app.store.one('SELECT status,error FROM jobs WHERE id=?',(job['id'],));self.assertEqual(row['status'],'done',row)
        artifact=self.app.store.canvas_history.get(chat);page=json.loads(artifact['content'][len(PREFIX):-4])['pages'][0]
        self.assertIn('OPEN LAB',page['html']);self.assertEqual(len(page['poster_fragments']),2);self.assertTrue(all(z['renderer']=='html' for z in page['poster_layout']['zones']));self.assertEqual(events,['CPU','image'])

    def test_moss_whole_poster_single_guide_preserves_ratio_recipe_and_skips_second_layout(self):
        # A fixture model shares the production MOSS options without loading weights.
        import base64
        moss=self.qwen|dict(architecture='moss',sampler='euler',scheduler='sgm_uniform',steps=50,cfg=3)
        media=self.app.upload({'name':'Robot.png','data':base64.b64encode(PNG).decode()})
        chat=self.app.store.create_chat()['id']
        self.app.store.save_settings({'vision_enabled':False})
        before=self.app.store.settings()
        with patch.object(self.app.engine,'require_model',side_effect=lambda ident,cap:moss if ident==self.qwen['id'] else self.app.catalog[ident]):
            ticket=self.app.send(chat,{'prompt':'Crea una locandina 9:16 OPEN LAB','lab':'poster','poster':{'composition':'moss_layout','image_model':self.qwen['id'],'reference_image':1,'typography_engine':'preset','text_renderer':'moss_short'},'media':[media],'rag':False})
            job=self.app.store.one('SELECT * FROM jobs WHERE id=?',(ticket['job_id'],))
            def generate(model,settings,prompt,refs,ident,*_):
                params=settings['_image_options'];self.assertFalse(params['preserve_reference_aspect'])
                self.assertAlmostEqual(params['width']/params['height'],9/16,places=3)
                self.assertEqual(params['strength'],.9);self.assertEqual([r['id'] for r in refs],[media['id']])
                self.assertEqual(json.loads(prompt)['items'][1]['text'],'OPEN LAB')
                folder=self.app.data/'outputs'/ident;folder.mkdir(parents=True);(folder/'image.png').write_bytes(PNG)
                return {'id':ident,'name':'image.png','path':f'outputs/{ident}/image.png','mime':'image/png','generation':{'seed':987}}
            with patch.object(self.app.engine,'prepare'),patch.object(self.app.engine,'prepare_tools',side_effect=lambda h,*a,**k:(h,{},[],[])),patch.object(self.app.engine,'start_llama'),patch.object(self.app.engine,'stop'),patch.object(self.app.engine,'completion',side_effect=[(json.dumps(plan()),'stop'),(json.dumps(referenced(layout())),'stop')]) as complete,patch.object(self.app.engine,'generate',side_effect=generate) as inference:
                self.app.execute_job(job,threading.Event())
        row=self.app.store.one('SELECT status,error FROM jobs WHERE id=?',(job['id'],));self.assertEqual(row['status'],'done',row)
        self.assertEqual(complete.call_count,2);self.assertEqual(inference.call_count,1)
        artifact=self.app.store.canvas_history.get(chat);deck=json.loads(artifact['content'][len(PREFIX):-4]);page=deck['pages'][0]
        self.assertEqual(page['status'],'ready');self.assertIn('poster-background',page['html']);self.assertNotIn('OPEN LAB',page['html'])
        self.assertEqual(page['poster_layout']['zones'][0]['renderer'],'moss')
        self.assertEqual(artifact['media'][-1]['generation']['seed'],987)
        self.assertEqual(self.app.store.settings(),before);validate_content(artifact['content'],artifact['media'])

    def test_hybrid_preflight_rejects_incompatible_model_cpu_missing_guide_and_no_generation(self):
        opts=options(value={'composition':'moss_layout','image_model':self.qwen['id']})
        with self.assertRaisesRegex(ValueError,'MOSS'):image_model(self.app,self.settings,opts,[])
        with self.assertRaisesRegex(ValueError,'CPU'):image_model(self.app,self.settings|{'execution_mode':'cpu'},opts,[])
        with self.assertRaisesRegex(ValueError,'guida'):image_model(self.app,self.settings,opts|{'reference_image':1},[])
        for images in ('existing','none','attached'):
            with self.assertRaises(ValueError):options(value=opts|{'images':images})


if __name__=='__main__':unittest.main()

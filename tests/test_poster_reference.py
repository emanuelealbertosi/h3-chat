import copy,hashlib,importlib.util,json,tempfile,threading,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
from h3chat.posters import options
from h3chat.poster_reference import prepare,validate,clean_photo_box,preserve_regions,brief,refine_text,require_readable_source,resolve_reference
from h3chat.poster_reference_check import diagnose,verify

PLAN={'summary':'Titolo alto, foto in basso.','background':'#ffffff','regions':[
    {'kind':'text','box':[.1,.05,.8,.1],'text':'OPEN LAB','appearance':'Titolo blu, grande, centrato'},
    {'kind':'image','box':[.2,.4,.5,.4],'text':'','appearance':'Fotografia senza testo'}],
    'warnings':['Font originale non identificato.']}

class PosterReferenceTests(unittest.TestCase):
    def worker(self):
        spec=importlib.util.spec_from_file_location('reference_worker',Path(__file__).resolve().parents[1]/'native/poster-reference-worker.py')
        m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

    def test_bounded_image_crop_preserves_source_and_rejects_external_output(self):
        from PIL import Image
        with tempfile.TemporaryDirectory() as tmp:
            data=Path(tmp);(data/'uploads').mkdir();source=data/'uploads/source.png';Image.new('RGB',(400,600),'coral').save(source);digest=hashlib.sha256(source.read_bytes()).hexdigest()
            request={'data':str(data),'source':'uploads/source.png','output':str(data/'outputs/test/reference'),'page':1};worker=self.worker();p=worker.run(request)
            self.assertEqual((p['width'],p['height']),(400,600))
            crop=worker.run(request|{'mode':'crop','source':p['path'],'regions':[[.25,.25,.5,.5]]})
            with Image.open(data/crop['files'][0]['path']) as im:self.assertEqual(im.size,(200,300))
            self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(),digest)
            for box in ([.8,.1,.5,.5],[0,0,float('nan'),.5]):
                with self.assertRaises(ValueError):worker.run(request|{'mode':'crop','regions':[box]})
            with self.assertRaises(ValueError):worker.run(request|{'output':str(data/'uploads/overwrite')})

    def test_pdf_selected_page_exposes_real_text_geometry(self):
        from pypdf import PdfWriter
        from pypdf.generic import DictionaryObject,NameObject,DecodedStreamObject
        with tempfile.TemporaryDirectory() as tmp:
            data=Path(tmp);(data/'uploads').mkdir();source=data/'uploads/layout.pdf';pdf=PdfWriter()
            for title in ('PAGE ONE','SECOND POSTER'):
                page=pdf.add_blank_page(width=400,height=600);font=DictionaryObject({NameObject('/Type'):NameObject('/Font'),NameObject('/Subtype'):NameObject('/Type1'),NameObject('/BaseFont'):NameObject('/Helvetica')});page[NameObject('/Resources')]=DictionaryObject({NameObject('/Font'):DictionaryObject({NameObject('/F1'):pdf._add_object(font)})});stream=DecodedStreamObject();stream.set_data(('BT /F1 24 Tf 70 500 Td ('+title+') Tj ET').encode());page[NameObject('/Contents')]=pdf._add_object(stream)
            pdf.write(str(source));pdf.close()
            worker=self.worker();request={'data':str(data),'source':'uploads/layout.pdf','output':str(data/'outputs/test/reference'),'page':2};p=worker.run(request)
            self.assertEqual(p['page'],2);self.assertEqual(p['pages'],2)
            self.assertIn('SECOND POSTER',str(p['text_regions']));self.assertNotIn('PAGE ONE',str(p['text_regions']))
            self.assertTrue(all(0<=r['box'][0]<1 and 0<=r['box'][1]<1 for r in p['text_regions']))
            with self.assertRaises(ValueError):worker.run(request|{'page':3})

    def test_structured_analysis_registers_only_photo_crops_and_records_uncertainty(self):
        from PIL import Image
        with tempfile.TemporaryDirectory() as tmp:
            data=Path(tmp);(data/'uploads').mkdir();Image.new('RGB',(1200,1800),'white').save(data/'uploads/source.png')
            source={'id':'a'*32,'path':'uploads/source.png','mime':'image/png','name':'Originale'}
            engine=Mock();worker=self.worker();engine.tool_call.side_effect=lambda name,req,*a,**kw:worker.run(req)
            engine.chat_messages.side_effect=lambda history,*a:history
            # Real engine returns a tuple only when a streaming callback is supplied.
            engine.completion.side_effect=lambda *a,**kw:(json.dumps(PLAN),'stop') if kw.get('on_text') else json.dumps(PLAN)
            app=SimpleNamespace(data=data,root=Path(tmp),engine=engine);meta={}
            opts=options(value={'reference_mode':'reproduce','reference_asset_id':source['id']})
            info,media=prepare(app,{'id':'test'},{'media':[source]},opts,{'vision_enabled':True,'max_tokens':8000},{'vision':{'enabled':True}},threading.Event(),lambda _:None,Path(tmp)/'log',meta)
            self.assertEqual(info['source_asset_id'],source['id']);self.assertEqual(info['mode'],'reproduce')
            self.assertEqual(len([m for m in media if m['mime'].startswith('image/')]),1)
            self.assertNotIn(source['id'],[m['id'] for m in media]);self.assertIn('Font originale',str(meta))
            self.assertEqual(engine.completion.call_count,1)
            with self.assertRaisesRegex(ValueError,'Vision'):
                prepare(app,{'id':'test'},{'media':[source]},opts,{'vision_enabled':False},{},threading.Event(),lambda _:None,None,{})
            with self.assertRaisesRegex(ValueError,'più riferimenti'):
                prepare(app,{'id':'test'},{'media':[source,source|{'id':'b'*32}]},options(value={'reference_mode':'improve'}),{}, {},threading.Event(),lambda _:None,None,{})

    def test_replaced_attachment_rebinds_stale_reference_but_never_guesses_among_many(self):
        opts=options(value={'reference_mode':'improve','reference_asset_id':'a'*32,'reference_page':8})
        new={'id':'b'*32,'mime':'image/jpeg'};other={'id':'c'*32,'mime':'application/pdf'}
        selected=resolve_reference(opts,[new])
        self.assertEqual(selected['reference_asset_id'],new['id']);self.assertEqual(selected['reference_page'],1)
        self.assertEqual(opts['reference_asset_id'],'a'*32) # no mutation of saved history
        with self.assertRaisesRegex(ValueError,'più riferimenti'):resolve_reference(opts,[new,other])
        with self.assertRaisesRegex(ValueError,'non è allegato'):resolve_reference(opts,[])
        self.assertEqual(resolve_reference(selected,[new,other]),selected)
        self.assertEqual(resolve_reference(options(),[new]),options())

    def test_prompt_modes_and_plan_geometry_are_checked(self):
        self.assertEqual(options('Fammela uguale',{'reference_mode':'improve'})['reference_mode'],'reproduce')
        self.assertEqual(options('Migliora questa locandina')['reference_mode'],'improve')
        self.assertEqual(options()['reference_mode'],'none')
        self.assertEqual(options(value={'reference_mode':'reproduce'})['images'],'existing')
        plan=copy.deepcopy(PLAN);plan['regions'][0]['box']=[.9,0,.3,.1]
        with self.assertRaises(ValueError):validate(plan)
        with self.assertRaises(ValueError):options(value={'reference_page':True})

    def test_photo_crop_excludes_original_titles_instead_of_duplicating_printed_text(self):
        original=[.42,.05,.58,.95];texts=[[.05,.09,.5,.11],[.05,.23,.5,.05],[.05,.65,.3,.25]]
        box=clean_photo_box(original,texts);self.assertIsNotNone(box)
        x,y,w,h=box
        self.assertGreater(w*h,original[2]*original[3]*.25)
        for tx,ty,tw,th in texts:self.assertTrue(x+w<=tx or tx+tw<=x or y+h<=ty or ty+th<=y)
        self.assertEqual(clean_photo_box(original,[]),original)
        self.assertIsNone(clean_photo_box([0,0,1,1],[[0,0,1,1]]))

    def test_main_subject_logo_and_qr_survive_printed_text_and_uncertainty(self):
        plan=copy.deepcopy(PLAN)
        plan['regions']=[
            {'kind':'image','role':'hero','box':[.3,.3,.4,.4],'text':'','appearance':'Soggetto centrale'},
            {'kind':'text','role':'subtitle','box':[.3,.45,.4,.1],'text':'OFFERTA','appearance':'Titolo','legibility':'clear'},
            {'kind':'image','role':'logo','box':[.7,.8,.25,.1],'text':'LOGO','appearance':'Marchio'},
            {'kind':'image','role':'qr','box':[.5,.8,.1,.1],'text':'','appearance':'QR'},
            {'kind':'text','role':'contact','box':[.7,.9,.25,.05],'text':'numero inventato','appearance':'Recapito','legibility':'uncertain'}]
        photos=preserve_regions(plan)
        self.assertEqual(len(photos),4)
        self.assertEqual(photos[0]['box'],[.3,.3,.4,.4])
        self.assertEqual(photos[0]['embedded_text'],['OFFERTA'])
        self.assertEqual(photos[1]['box'],[.7,.8,.25,.1])
        self.assertTrue(photos[-1]['facsimile']);self.assertEqual(photos[-1]['text'],'')
        message=brief({'mode':'improve','plan':plan})
        self.assertNotIn('numero inventato',message);self.assertIn('STRUTTURA SEMANTICA',message)

    def test_detail_reading_uses_only_crops_and_respects_vision_capacity(self):
        plan=copy.deepcopy(PLAN);plan['regions']=plan['regions'][:1]*3
        plan['regions']=[copy.deepcopy(r) for r in plan['regions']]
        plan['regions'][0]['text']='VERIFICAT0'
        app=SimpleNamespace(data=Path('data'),engine=Mock())
        app.engine.tool_call.return_value={'files':[{'region_index':i,'path':f'outputs/test/{i}.png'} for i in range(3)]}
        app.engine.chat_messages.side_effect=lambda history,*a:history
        replies=[{'readings':[{'index':0,'text':'VERIFICATO','legibility':'clear','box':[.1,.2,.8,.6]},{'index':1,'text':'dubbio','legibility':'uncertain','box':[0,0,1,1]}]}, {'readings':[{'index':2,'text':'ALTRO','legibility':'clear','box':[0,0,1,1]}]}]
        app.engine.completion.side_effect=[(json.dumps(r),'stop') for r in replies]
        refine_text(app,plan,{'width':400,'height':600,'path':'uploads/original.png'},Path('outputs/test'),{'vision_max_refs':4},{'api':True,'max_refs':2},{},threading.Event(),lambda _:None,None,lambda _:None)
        self.assertEqual(app.engine.completion.call_count,2)
        self.assertEqual(plan['regions'][0]['text'],'VERIFICATO')
        self.assertEqual(plan['regions'][1]['legibility'],'uncertain')
        calls=app.engine.chat_messages.call_args_list
        self.assertEqual([len(c.args[0][0]['media']) for c in calls],[2,1])
        self.assertNotIn('OPEN LAB',str(calls)) # do not anchor OCR to an earlier guess

    def test_large_illustrated_decoration_is_preserved_and_not_lost_as_a_shape(self):
        plan=copy.deepcopy(PLAN);plan['regions'][1].update(kind='decoration',role='decoration')
        photos=preserve_regions(plan)
        self.assertEqual(len(photos),1);self.assertEqual(photos[0]['kind'],'image')

    def test_verification_rejects_printing_raster_headings_twice(self):
        info={'plan':{'regions':[{'kind':'image','asset_id':'header','embedded_text':['School Open Day']}]}}
        report={'width':1000,'height':1400,'images':[{'id':'header','visible':True,'width':1000,'height':400}],'visible_text':'SCHOOL OPEN DAY'}
        self.assertIn('duplicate_raster_text',str(diagnose(report,info,[])))

    def test_dense_thumbnail_requires_better_original_instead_of_ready_mutilated_copy(self):
        plan=copy.deepcopy(PLAN);row={'kind':'text','box':[.1,.2,.3,.03],'text':'Unclear','appearance':'Small','legibility':'uncertain'}
        plan['regions']=[copy.deepcopy(row) for _ in range(16)]
        with self.assertRaisesRegex(ValueError,'PDF originale'):require_readable_source(plan,{'width':400,'height':600},'improve')
        require_readable_source(plan,{'width':400,'height':600},'reproduce')
        require_readable_source(plan,{'width':1600,'height':2400},'improve')
        with self.assertRaises(ValueError):require_readable_source(plan,{'width':1600,'height':2400},'improve',after_details=True)

    def test_contacts_cannot_be_invented_from_unverified_image_caption(self):
        info={'plan':{'regions':[{'kind':'image','role':'logo','text':'fake@example.com'}]}}
        report={'width':1000,'height':1400,'images':[],'visible_text':'fake@example.com'}
        self.assertIn('unverified_contacts',str(diagnose(report,info,[])))
        self.assertEqual(diagnose(report,info,[],authorized_text='Usa fake@example.com'),[])

    def test_provider_array_error_reaches_app_repair_instead_of_aborting_reference_analysis(self):
        from h3chat.remote_llm import StructuredCompletionError
        from PIL import Image
        with tempfile.TemporaryDirectory() as tmp:
            data=Path(tmp);(data/'uploads').mkdir();Image.new('RGB',(1200,1800),'white').save(data/'uploads/source.png')
            source={'id':'a'*32,'path':'uploads/source.png','mime':'image/png','name':'Originale'}
            engine=Mock();worker=self.worker();engine.tool_call.side_effect=lambda name,req,*a,**kw:worker.run(req)
            engine.chat_messages.side_effect=lambda history,*a:[{'role':'user','content':[{'type':'text','text':history[0]['content']}]}]
            bad=json.dumps(PLAN|{'warnings':['uncertain']*17})
            engine.completion.side_effect=[StructuredCompletionError('Numero di elementi API JSON non valido: campo $.warnings, ricevuti 17, intervallo consentito 0–16.',content=bad),(json.dumps(PLAN),'stop')]
            app=SimpleNamespace(data=data,root=data,engine=engine);meta={}
            info,_=prepare(app,{'id':'test'},{'media':[source]},options(value={'reference_mode':'improve'}),{'vision_enabled':True,'max_tokens':8000},{'vision':{'enabled':True}},threading.Event(),lambda _:None,None,meta)
            self.assertEqual(info['source_asset_id'],source['id']);self.assertEqual(engine.completion.call_count,2)
            repair=str(engine.completion.call_args_list[1].args[0])
            self.assertIn('$.warnings',repair);self.assertIn('0 a 16',repair)
            self.assertEqual((data/'outputs/test/poster-reference/analysis-1-rejected.txt').read_text(encoding='utf8'),bad)

    def test_checks_reject_hidden_dates_missing_hero_and_thumbnail_substitution(self):
        info={'plan':{'regions':[{'kind':'text','text':'5 dicembre 2025','role':'calendar'}]}}
        planned=[{'id':'hero','role':'hero','source_box':[.3,.3,.4,.4]}]
        report={'width':1000,'height':1400,'images':[],'visible_text':'5 dicembre 2025','covered_text':[{'text':'5 dicembre 2025'}]}
        self.assertTrue(diagnose(report,info,planned))
        report.update(covered_text=[],images=[{'id':'hero','visible':True,'width':15,'height':15}])
        self.assertIn('hero_too_small',str(diagnose(report,info,planned)))
        report['images'][0].update(width=400,height=400)
        self.assertEqual(diagnose(report,info,planned),[])
        report['visible_text']='5 dicembre 2026'
        self.assertIn('missing_text',str(diagnose(report,info,planned)))

    def test_app_repairs_failed_layout_and_remeasures_before_ready(self):
        app=SimpleNamespace(data=Path('data'),engine=Mock())
        bad={'width':1000,'height':1400,'images':[],'visible_text':'','covered_text':[{'text':'data nascosta'}]}
        good=bad|{'visible_text':'5 dicembre 2025','covered_text':[]}
        app.engine.tool_call.side_effect=[{'pages':[bad]},{'pages':[good]}]
        html='<main>5 dicembre 2025</main><style>main{color:black}</style>'
        app.engine.completion.return_value=(html,'stop')
        info={'plan':{'regions':[{'kind':'text','text':'5 dicembre 2025'}]}}
        deck={'poster':{'count':1},'pages':[]};meta={}
        result=verify(app,deck,{},[],info,[],'old',[],{},threading.Event(),lambda _:None,lambda _:None,None,Path('outputs/test'),meta)
        self.assertEqual(result,html);self.assertEqual(app.engine.tool_call.call_count,2)
        self.assertEqual(len(meta['poster_reference_checks']),2)

    def test_raster_branding_repetition_is_cosmetic_and_does_not_block_complete_poster(self):
        app=SimpleNamespace(data=Path('data'),engine=Mock())
        report={'width':1000,'height':1400,'images':[{'id':'header','visible':True,'width':1000,'height':300}],'visible_text':'SCHOOL OPEN DAY','covered_text':[]}
        app.engine.tool_call.return_value={'pages':[report]}
        html='<main><h1>SCHOOL OPEN DAY</h1></main><style>main{color:black}</style>';app.engine.completion.return_value=(html,'stop')
        info={'plan':{'regions':[{'kind':'image','asset_id':'header','box':[0,0,1,.2],'embedded_text':['SCHOOL OPEN DAY']}]}}
        page={};meta={}
        result=verify(app,{'poster':{'count':1}},page,[],info,[],html,[],{},threading.Event(),lambda _:None,lambda _:None,None,Path('outputs/test'),meta)
        self.assertEqual(result,html);self.assertEqual(app.engine.tool_call.call_count,2)
        self.assertIn('layout_warning',page);self.assertIn('poster_reference_cosmetic_warnings',meta)

    def test_separate_repeated_branding_is_allowed_but_overlapping_words_are_detected(self):
        box={'x':0,'y':0,'width':400,'height':80}
        info={'plan':{'regions':[]}}
        report={'width':1000,'height':1400,'images':[{'id':'header','visible':True,'reference_text':[{'text':'SCHOOL OPEN DAY','visible':True,'box':box}]}],'visible_text':'SCHOOL OPEN DAY','text_boxes':[{'text':'SCHOOL OPEN DAY','boxes':[box|{'y':900}]}]}
        self.assertEqual(diagnose(report,info,[]),[])
        report['text_boxes'][0]['boxes']=[box]
        self.assertIn('duplicate_raster_text',str(diagnose(report,info,[])))

if __name__=='__main__':unittest.main()

import copy,json,tempfile,threading,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
from h3chat import motion_sprites as library
from h3chat.infographic_storyboard import generate,EXAMPLE
from h3chat.infographics import options,background_direction

class MotionTests(unittest.TestCase):
    def test_background_follows_explicit_prompt_without_dark_tech_default(self):
        out=options('Infografica tech con sfondo chiaro',{'background':'dark'})
        self.assertEqual(out['background'],'light');self.assertIn('Sfondo principale chiaro',background_direction(out));self.assertIn('NON impongono',background_direction(options()))
    def test_mode_opt_in_and_sprite_ids_bounded(self):
        self.assertEqual(options()['animation_engine'],'classic')
        for invalid in ({'animation_engine':'script'},{'sprite_ids':['../file']},{'sprite_ids':[{}]},{'animation_engine':'motion','layout':'columns2'}):
            with self.subTest(value=invalid),self.assertRaises(ValueError):options(value=invalid)
    def test_scene_generation_keeps_source_context_and_repairs_once(self):
        engine=Mock();bad=copy.deepcopy(EXAMPLE);bad['duration']=99;engine.completion.side_effect=[(json.dumps(bad),'stop'),(json.dumps(EXAMPLE),'stop')]
        result=generate(engine,[{'role':'user','content':'Fonte selezionata R1 · testo originale'}],{'title':'Data center','narration':'I dati crescono'},1280,720,10,{},threading.Event(),lambda _:None,timing={'kind':'manual-duration'})
        self.assertEqual(result['duration'],10);self.assertEqual(engine.completion.call_count,2);self.assertIn('Fonte selezionata R1',str(engine.completion.call_args.args[0]));self.assertNotIn('R2',str(engine.completion.call_args.args[0]))
        engine.completion.side_effect=None;engine.completion.return_value=('{"script":"alert(1)"}','stop')
        with self.assertRaises(ValueError):generate(engine,[],{},1280,720,10,{},threading.Event(),lambda _:None)
    def test_pretty_json_indentation_and_repeated_geometry_are_not_stalls(self):
        engine=Mock()
        def completion(*args,**kwargs):
            kwargs['on_text'](json.dumps(EXAMPLE,indent=12)+' '*12);return json.dumps(EXAMPLE),'stop'
        engine.completion.side_effect=completion
        self.assertEqual(generate(engine,[],{},1280,720,10,{},threading.Event(),lambda _:None)['id'],'scene01')
    def test_counter_repair_keeps_schema_and_explains_initial_value_vs_track(self):
        engine=Mock();bad=copy.deepcopy(EXAMPLE);bad['objects'].append({'id':'count','type':'counter','width':200,'height':80,'value':0,'barValue':0})
        engine.completion.side_effect=[(json.dumps(bad),'stop'),(json.dumps(EXAMPLE),'stop')]
        generate(engine,[],{},1280,720,10,{},threading.Event(),lambda _:None)
        repair=engine.completion.call_args_list[1]
        self.assertIn('usa value per il valore iniziale',str(repair.args[0]));self.assertIsNotNone(repair.kwargs.get('schema'))
    def test_catalog_requires_confirmation_and_keeps_saved_project_independent(self):
        with tempfile.TemporaryDirectory() as d:
            app=SimpleNamespace(data=Path(d));scene=copy.deepcopy(EXAMPLE);scene['camera']={'keyframes':[]}
            for o in scene['objects']:o['tracks']=[]
            body={'scene':scene,'name':'Server ciano','description':'Rack rettangolare con spia gialla','style':'Vettoriale piatto','tags':['server','tecnologia']}
            with self.assertRaises(ValueError):library.save(app,body)
            saved=library.save(app,body|{'confirmed':True});self.assertEqual(len(library.listing(app,'ciano tecnologia')),1);self.assertEqual(library.listing(app,'persona'),[])
            group={'id':'instance','type':'group','spriteId':saved['id'],'width':1280,'height':720}
            project=copy.deepcopy(EXAMPLE);project['objects']=[group];expanded=library.expand(project,[saved]);self.assertGreater(len(expanded['objects']),1);self.assertNotIn('spriteId',json.dumps(expanded))
            with self.assertRaises(ValueError):library.expand(project,[])
            with self.assertRaises(ValueError):library.remove(app,saved['id'],{})
            library.remove(app,saved['id'],{'confirmed':True});self.assertEqual(library.listing(app),[]);self.assertGreater(len(expanded['objects']),1)
    def test_raster_and_foreign_assets_are_never_silently_saved_or_generated(self):
        engine=Mock();scene=copy.deepcopy(EXAMPLE);scene['objects']=[{'id':'photo','type':'image','assetId':'a'*32,'width':100,'height':100}];engine.completion.return_value=(json.dumps(scene),'stop')
        with self.assertRaisesRegex(ValueError,'catalogo'):generate(engine,[],{},1280,720,10,{},threading.Event(),lambda _:None)
        result=generate(engine,[],{},1280,720,10,{},threading.Event(),lambda _:None,images=[{'id':'a'*32,'name':'Allegato scelto'}]);self.assertEqual(result['objects'][0]['assetId'],'a'*32)
    def test_raster_sprite_owns_a_copy_and_project_survives_library_removal(self):
        with tempfile.TemporaryDirectory() as d:
            data=Path(d);(data/'uploads').mkdir();source=data/'uploads/photo.png';source.write_bytes(b'png-fixture')
            store=SimpleNamespace(canvas_history=SimpleNamespace(get=Mock(return_value={'media':[{'id':'a'*32,'name':'Foto scelta','mime':'image/png','path':'uploads/photo.png'}]})));app=SimpleNamespace(data=data,store=store)
            scene=copy.deepcopy(EXAMPLE);scene['objects']=[{'id':'photo','type':'image','assetId':'a'*32,'width':100,'height':100}];scene['camera']={'keyframes':[]}
            body={'confirmed':True,'scene':scene,'name':'Sprite fotografico','description':'Foto scelta dal progetto','style':'Fotografia','tags':['foto'],'chat_id':'chat','artifact_id':'artifact'}
            saved=library.save(app,body);copied=data/saved['media'][0]['path'];self.assertEqual(copied.read_bytes(),b'png-fixture');source.unlink();self.assertEqual(library.selected(app,[saved['id']])[0]['id'],saved['id']);library.remove(app,saved['id'],{'confirmed':True});self.assertTrue(copied.is_file())

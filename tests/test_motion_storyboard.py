import copy,json,tempfile,threading,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
from h3chat import motion_sprites as library
from h3chat.infographic_storyboard import generate,EXAMPLE
from h3chat.infographics import options,background_direction

class MotionTests(unittest.TestCase):
    def test_explicit_single_attached_logo_is_assigned_without_guessing_among_images(self):
        from h3chat.infographic_art import requested_logo,scene_request
        logo={'id':'a'*32,'mime':'image/png','name':'images.png'}
        requested=requested_logo('Usa il logo originale allegato, non inventarlo.',[logo],3)
        self.assertEqual(requested[0]['scene'],1);self.assertEqual(requested[0]['asset_id'],logo['id'])
        self.assertEqual(requested_logo('Usa il logo allegato solo in chiusura.',[logo],3)[0]['scene'],3)
        self.assertEqual(requested_logo('Usa il logo allegato.',[logo,logo|{'id':'b'*32}],3),[])
        plan={'visual_direction':'Avorio e giada','scenes':[{'purpose':'Apertura'},{'purpose':'Chiusura'}]}
        row=scene_request(plan,0,[],requested);self.assertEqual(row['illustrations'][0]['role'],'logo')

    def test_unpainted_text_is_repaired_but_outline_and_delayed_color_are_valid(self):
        from h3chat.infographic_storyboard import paint_errors
        blank=copy.deepcopy(EXAMPLE);blank['objects'][-1]['fill']='none'
        self.assertIn('title',paint_errors(blank)[0])
        outline=copy.deepcopy(blank);outline['objects'][-1].update(stroke='#165467',strokeWidth=2);self.assertEqual(paint_errors(outline),[])
        delayed=copy.deepcopy(blank);delayed['objects'][-1]['tracks'].append({'property':'fill','keyframes':[{'t':1,'value':'#165467'}]});self.assertEqual(paint_errors(delayed),[])
        engine=Mock();engine.completion.side_effect=[(json.dumps(blank),'stop'),(json.dumps(EXAMPLE),'stop')]
        self.assertEqual(generate(engine,[],{},1280,720,10,{},threading.Event(),lambda _:None)['objects'][-1]['fill'],'#165467')
        self.assertEqual(engine.completion.call_count,2);self.assertIn('testo sempre invisibile',str(engine.completion.call_args.args[0]))

    def test_empty_no_parent_sentinel_is_canonical_but_invalid_links_still_fail(self):
        from h3chat.infographic_storyboard import canonical_roots,hierarchy_errors
        graph=copy.deepcopy(EXAMPLE);graph['objects'][0]['parentId']='';before=copy.deepcopy(graph)
        normalized=canonical_roots(graph);self.assertEqual(graph,before);self.assertIsNone(normalized['objects'][0]['parentId'])
        normalized['objects'][1]['parentId']='missing';self.assertTrue(any('missing' in e for e in hierarchy_errors(normalized)))
        engine=Mock();engine.completion.return_value=(json.dumps(graph),'stop')
        self.assertEqual(generate(engine,[],{},1280,720,10,{},threading.Event(),lambda _:None)['objects'][0]['parentId'],None)
        self.assertEqual(engine.completion.call_count,1)

    def test_generated_art_assignments_and_neighboring_direction_reach_the_shot(self):
        from h3chat.infographic_art import scene_request
        plan={'visual_direction':'Avorio e giada, editoriale','scenes':[{'title':'Uno','purpose':'Ingresso','narration':'Testo'}, {'title':'Due','purpose':'Laboratorio','narration':'Testo 2'}]}
        image={'slide':1,'asset_id':'a'*32,'description':'Scuola illustrata','aspect':'16:9','width':1664,'height':960}
        row=scene_request(plan,0,[image]);self.assertEqual(row['continuity']['next'],'Laboratorio');self.assertEqual(row['visual_direction'],plan['visual_direction'])
        graph=copy.deepcopy(EXAMPLE);graph['objects'].append({'id':'art','type':'image','assetId':'a'*32,'width':600,'height':400})
        engine=Mock();engine.completion.side_effect=[(json.dumps(EXAMPLE),'stop'),(json.dumps(graph),'stop')]
        result=generate(engine,[],row,1280,720,10,{},threading.Event(),lambda _:None,images=[{'id':'a'*32,'name':'Scuola'}])
        self.assertEqual(result['objects'][-1]['assetId'],'a'*32);self.assertIn('Illustrazioni assegnate ignorate',str(engine.completion.call_args.args[0]));self.assertEqual(engine.completion.call_count,2)

    def test_transition_duration_is_finite_and_bounded(self):
        self.assertEqual(options()['transition_seconds'],.9)
        self.assertEqual(options(value={'transition_seconds':1.2})['transition_seconds'],1.2)
        for value in (True,float('nan'),0,2.1):
            with self.subTest(value=value),self.assertRaises(ValueError):options(value={'transition_seconds':value})

    def test_truncated_scene_gets_more_budget_without_replaying_the_partial_graph(self):
        engine=Mock();engine.completion.side_effect=[('{"truncated_marker_unique":','length'),(json.dumps(EXAMPLE),'stop')]
        generate(engine,[{'role':'user','content':'Source R1 retained'}],{},1280,720,10,{'max_tokens':60000},threading.Event(),lambda _:None)
        calls=engine.completion.call_args_list
        self.assertGreater(calls[1].args[1]['max_tokens'],calls[0].args[1]['max_tokens'])
        self.assertLessEqual(calls[1].args[1]['max_tokens'],60000)
        self.assertNotIn('truncated_marker_unique',str(calls[1].args[0]));self.assertIn('Source R1 retained',str(calls[1].args[0]))

    def test_truncation_retry_never_exceeds_explicit_user_allowance(self):
        engine=Mock();engine.completion.side_effect=[('{','length'),(json.dumps(EXAMPLE),'stop')]
        generate(engine,[],{},1280,720,10,{'max_tokens':8000},threading.Event(),lambda _:None)
        self.assertEqual([c.args[1]['max_tokens'] for c in engine.completion.call_args_list],[8000,8000])

    def test_single_repair_receives_both_parent_type_and_child_parallax_errors(self):
        from h3chat.infographic_storyboard import hierarchy_errors
        bad=copy.deepcopy(EXAMPLE)
        bad['objects'] += [{'id':'numberBox','type':'counter','width':200,'height':80,'value':0},
            {'id':'numberLeaf','type':'counter','parentId':'numberBox','parallax':0,'width':200,'height':80,
             'value':0,'maxValue':732,'tracks':[{'property':'barValue','keyframes':[{'t':0,'value':0},{'t':8,'value':732}]}]}]
        before=copy.deepcopy(bad);issues=hierarchy_errors(bad)
        self.assertEqual(bad,before);self.assertTrue(any('numberBox' in e and 'non group' in e for e in issues))
        self.assertTrue(any('numberLeaf.parallax' in e for e in issues))
        fixed=copy.deepcopy(bad);fixed['objects'][-2]['type']='group';fixed['objects'][-1]['parallax']=1
        engine=Mock();engine.completion.side_effect=[(json.dumps(bad),'stop'),(json.dumps(fixed),'stop')]
        result=generate(engine,[],{},1280,720,10,{},threading.Event(),lambda _:None)
        repair=str(engine.completion.call_args_list[1].args[0]);self.assertIn('numberBox',repair);self.assertIn('numberLeaf.parallax',repair)
        self.assertEqual(engine.completion.call_count,2);self.assertEqual(result['objects'][-1]['tracks'][0]['keyframes'][-1]['value'],732)

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

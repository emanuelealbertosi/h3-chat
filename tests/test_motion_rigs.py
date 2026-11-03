import copy,json,tempfile,threading,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
from h3chat.motion_rigs import template,animate,instantiate,validate_rig,PARTS,atlas_prompt
from h3chat.motion_sprites import expand,save,selected
from h3chat.infographic_characters import extend_schema,validate_plan,additional_plan
from h3chat.infographics import options
from h3chat.infographic_scene import validate
from h3chat.infographic_storyboard import schema,generate


def actor():
    parts={name:{'x':(i%2)*100,'y':(i//2)*100,'width':90,'height':90,'sourceWidth':200,'sourceHeight':300} for i,name in enumerate(PARTS)}
    return template({'id':'a'*32,'name':'Atlante','mime':'image/png','path':'outputs/atlas.png'},parts,'Studente','Felpa giada e pantaloni blu','Illustrazione editoriale')


class RigTests(unittest.TestCase):
    def test_wave_moves_articulated_parts_and_compiles_to_one_atlas(self):
        rig=actor();before=copy.deepcopy(rig)
        scene={'version':2,'id':'test','width':1280,'height':720,'duration':8,'background':'#f7f3e8',
            'objects':[{'id':'student','type':'group','spriteId':rig['id'],'width':360,'height':480,'gesture':'wave','actionStart':1,'actionEnd':6}], 'camera':{'keyframes':[]}}
        result=expand(scene,[rig]);self.assertEqual(rig,before)
        self.assertEqual({o['assetId'] for o in result['objects'] if o['type']=='image'},{'a'*32})
        self.assertTrue(any(t['property']=='rotation' and len(t['keyframes'])>5 for o in result['objects'] for t in o.get('tracks',[])))
        self.assertTrue(all('spriteId' not in o and 'gesture' not in o for o in result['objects']))
        validate(result)
        # Renamed non-joint containers remain valid reusable rigs.
        renamed=copy.deepcopy(rig)
        for item in renamed['scene']['objects']:
            if item['id']=='torsoHolder':item['id']='garment'
            if item.get('parentId')=='torsoHolder':item['parentId']='garment'
        validate(animate(renamed,'wave',1,6,8))
        for bad in [('walk',1,6),('point',6,1),('wave',-1,6),('wave',1,9),('wave',True,5)]:
            with self.subTest(action=bad),self.assertRaises(ValueError):animate(rig,*bad,8)

    def test_invalid_crop_and_rig_links_are_rejected(self):
        rig=actor();graph=copy.deepcopy(rig['scene']);next(o for o in graph['objects'] if o['type']=='image')['crop']['x']=200
        with self.assertRaises(ValueError):validate(graph)
        invalid=copy.deepcopy(rig['rig']);invalid['joints']['lower_r']='missing'
        with self.assertRaises(ValueError):validate_rig(rig['scene'],invalid)
        invalid['joints']['lower_r']={}
        with self.assertRaises(ValueError):validate_rig(rig['scene'],invalid)

    def test_generated_scene_must_use_the_requested_character_and_gesture(self):
        rig=actor();scene={'version':2,'id':'test','width':1280,'height':720,'duration':8,'background':'#f7f3e8',
            'objects':[{'id':'student','type':'group','spriteId':rig['id'],'width':360,'height':480,'gesture':'point','actionStart':1,'actionEnd':6}],'camera':{'keyframes':[]}}
        engine=Mock();bad=copy.deepcopy(scene);bad['objects'][0]['gesture']='idle';engine.completion.side_effect=[(json.dumps(bad),'stop'),(json.dumps(scene),'stop')]
        result=generate(engine,[],{'characters':[{'id':rig['id'],'action':'point'}]},1280,720,8,{},threading.Event(),lambda _:None,[rig])
        self.assertGreater(len(result['objects']),10);self.assertEqual(engine.completion.call_count,2)
        variants=schema(1280,720,8,[rig],[])['properties']['objects']['items']['anyOf']
        choices=[v for v in variants if 'spriteId' in v['properties']];self.assertEqual(len(choices),1);self.assertIn('gesture',choices[0]['required'])

    def test_library_preserves_articulation_and_copies_the_owned_atlas(self):
        with tempfile.TemporaryDirectory() as tmp:
            data=Path(tmp);(data/'outputs').mkdir();(data/'outputs/atlas.png').write_bytes(b'owned-atlas')
            rig=actor();app=SimpleNamespace(data=data,store=SimpleNamespace(canvas_history=SimpleNamespace(get=Mock(return_value={'media':rig['media']}))))
            body={'scene':rig['scene'],'rig':rig['rig'],'name':rig['name'],'description':rig['description'],'style':rig['style'],'tags':rig['tags'],'chat_id':'chat','artifact_id':'artifact','confirmed':True}
            saved=save(app,body);self.assertEqual(saved['rig'],rig['rig']);self.assertEqual(selected(app,[saved['id']])[0]['rig'],rig['rig'])
            self.assertNotEqual(saved['media'][0]['id'],rig['media'][0]['id']);(data/'outputs/atlas.png').unlink()
            self.assertTrue((data/saved['media'][0]['path']).is_file())

    def test_mode_and_inventory_are_opt_in_and_bounded(self):
        self.assertEqual(options()['character_animation'],'illustrated')
        self.assertEqual(options('Personaggi articolati, ritmo YouTube')['character_animation'],'articulated')
        self.assertEqual(options('Personaggi articolati, ritmo YouTube')['pace'],'explainer')
        self.assertEqual(options('Senza personaggi articolati',{'animation_engine':'motion','character_animation':'articulated'})['character_animation'],'illustrated')
        with self.assertRaises(ValueError):options(value={'character_animation':'articulated'})
        plan={'visual_direction':'Avorio e giada','characters':[{'id':'student','name':'Studente','appearance':'Felpa giada'}],'scenes':[{'characters':[{'id':'student','action':'wave'}]}]}
        validate_plan(plan,[]);self.assertEqual(additional_plan(plan)[0]['role'],'character_parts')
        self.assertNotIn('sfondo avorio',atlas_prompt('Felpa giada','sfondo avorio e font Manrope'))
        bad=copy.deepcopy(plan);bad['scenes'][0]['characters'][0]['id']='foreign'
        with self.assertRaises(ValueError):validate_plan(bad,[])

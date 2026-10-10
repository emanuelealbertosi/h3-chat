import copy,json,tempfile,threading,unittest
from pathlib import Path
from unittest.mock import Mock,patch
from h3chat.video_clip_budget import contract
from h3chat.video_storyboard import build,validate,local_plan,SCHEMA
from h3chat.video_engine import VideoEngine

def story(count,duration):
    return {'style':'A music video, stable cast.','shots':[
        {'end':duration*(i+1)/count,'prompt':f'[Shot 1] The teacher enters room {i+1}. [Shot 2] At 00:05.000, cut to the desk.',
         'time_basis':'local','continuity':'cut','lip_sync':False,'images':[]} for i in range(count)]}

class ClipBudgetTests(unittest.TestCase):
    def test_count_is_generations_not_internal_shots(self):
        for prompt in ('Fai 9 clip con 21 inquadrature','Nine clips with twenty-one shots',
                       'Crea nove scene, più stacchi in ciascuna','clip: 9','Non fare 21 clip, ma 9 clip',
                       'Fai 9 clip con 21 scene\nSCENA 1: First\nSCENA 2: Second'):
            with self.subTest(prompt=prompt):self.assertEqual(contract(prompt,90)['count'],9)
        self.assertEqual(contract('Una canzone con tanti stacchi',89.512)['count'],6)
        self.assertEqual(contract('A 16:9 video with 24 fps, 12 steps and 3 images',90)['count'],6)
        self.assertEqual(contract('Canta <d>[Italian] nove clip</d>',90)['count'],6)
        self.assertEqual(contract('Una scena sul divano, poi due scene in cucina',90)['count'],6)
        self.assertEqual(contract('Il protagonista entra in una scena di festa',90)['count'],6)

    def test_numbered_clip_blocks_and_explicit_global_intervals(self):
        prompt='\n'.join(f'CLIP {i+1} TIMELINE {i*10//60:02}:{i*10%60:02}–{(i+1)*10//60:02}:{(i+1)*10%60:02}: scene' for i in range(9))
        value=contract(prompt,90)
        self.assertEqual(value['count'],9);self.assertEqual(value['end_frames'],[240*(i+1) for i in range(9)])
        self.assertEqual(contract('CLIP 2 TIMELINE 00:15–00:30',15)['count'],1)
        nominal='CLIP 1 TIMELINE 00:00–00:15\nCLIP 2 TIMELINE 00:15–00:30'
        self.assertEqual(contract(nominal,29.512)['end_frames'],[360,709])
        self.assertEqual(contract('CLIP 1: 00:00–00:15\nCLIP 2: 00:00–00:15',30)['end_frames'],[360,720])
        self.assertEqual(contract('CLIP 1: 01:00–01:15\nCLIP 2: 01:15–01:30',30,audio_start=60)['end_frames'],[360,720])

    def test_invalid_counts_and_missing_time_are_not_silently_expanded(self):
        for prompt in ('Fai 5 clip','Fai 161 clip','1000 clip','0 clip','Fai 9 clip e 21 clip'):
            with self.subTest(prompt=prompt),self.assertRaises(ValueError):contract(prompt,90)
        with self.assertRaisesRegex(ValueError,'elencati'):
            contract('Fai 9 clip\nCLIP 1: Opening\nCLIP 2: End',90)
        with self.assertRaisesRegex(ValueError,'buchi'):
            contract('CLIP 1 TIMELINE 00:00–00:10\nCLIP 2 TIMELINE 00:11–00:20',20)
        with self.assertRaisesRegex(ValueError,'coprire'):
            contract('CLIP 1 TIMELINE 00:00–00:10\nCLIP 2 TIMELINE 00:10–00:20',24)

    def test_21_generations_are_repaired_to_9_and_internal_cuts_are_retained(self):
        engine=VideoEngine();engine.require_model=Mock(return_value={});engine.start_llama=Mock()
        engine.completion=Mock(side_effect=[(json.dumps(story(21,90)),'stop'),(json.dumps(story(9,90)),'stop')])
        settings={'chat_model':'fixture','context':80000,'video_prompt_max_tokens':4000,'_video_duration':90}
        stage=Mock();schema_before=copy.deepcopy(SCHEMA)
        result=build(engine,{},[],settings,'Fai 9 clip con 21 inquadrature',threading.Event(),stage,Path('log'))
        self.assertEqual(len(result['shots']),9);self.assertEqual(engine.completion.call_count,2)
        schema=engine.completion.call_args.kwargs['schema']['properties']['shots']
        self.assertEqual((schema['minItems'],schema['maxItems']),(9,9));self.assertEqual(SCHEMA,schema_before)
        self.assertIn('servono esattamente 9 clip',engine.completion.call_args.args[0][-1]['content'])
        self.assertIn('9 clip da generare',stage.call_args_list[0].args[0])
        self.assertIn('[Shot 2] At 00:05',result['shots'][0]['prompt'])

    def test_invalid_budget_stops_before_loading_llm_and_repeated_bad_plan_never_renders(self):
        engine=VideoEngine();engine.require_model=Mock();engine.start_llama=Mock();engine.generate_video=Mock()
        settings={'chat_model':'fixture','context':80000,'video_prompt_max_tokens':4000,'_video_duration':90}
        with self.assertRaisesRegex(ValueError,'almeno|servono da'):
            build(engine,{},[],settings,'Fai 5 clip',threading.Event(),Mock(),Path('log'))
        engine.start_llama.assert_not_called()
        engine.completion=Mock(return_value=(json.dumps(story(21,90)),'stop'))
        with self.assertRaisesRegex(ValueError,'Nessun video'):
            build(engine,{},[],settings,'Fai 9 clip',threading.Event(),Mock(),Path('log'))
        engine.generate_video.assert_not_called();self.assertEqual(engine.completion.call_count,2)

    def test_automatic_minimum_grouping_and_precise_requested_boundaries(self):
        engine=VideoEngine();engine.require_model=Mock(return_value={});engine.start_llama=Mock()
        engine.completion=Mock(return_value=(json.dumps(story(6,90)),'stop'))
        settings={'chat_model':'fixture','context':80000,'video_prompt_max_tokens':4000,'_video_duration':90}
        result=build(engine,{},[],settings,'Use the whole song',threading.Event(),Mock(),Path('log'))
        self.assertEqual(len(result['shots']),6);self.assertFalse(result['clip_budget']['explicit'])
        prompt='CLIP 1 TIMELINE 00:00–00:06\nCLIP 2 TIMELINE 00:06–00:15'
        wrong=story(2,15)
        with self.assertRaisesRegex(ValueError,'terminare a 6'):validate(wrong,15,[],prompt)

    def test_multiple_visual_shots_share_references_and_one_audio_window(self):
        refs=[{'id':'first','mime':'image/png'},{'id':'second','mime':'image/png'},{'id':'audio','mime':'audio/wav'}]
        value=story(1,10);value['shots'][0].update(
            prompt='[Shot 1] Start from <Picture 2>. [Shot 2] At 00:05.000, cut to <Picture 1>.',
            images=[{'index':2,'role':'keyframe'},{'index':1,'role':'reference'}],lip_sync=True)
        saved=validate(value,10,refs,'Fai 1 clip')
        plan,chosen=local_plan(saved,saved['shots'][0],{'audios':[{'index':1,'role':'reuse','start':0}]},refs,1,60)
        self.assertEqual([r['id'] for r in chosen],['second','first','audio'])
        self.assertIn('[Shot 1] Start from <Picture 1>',plan['prompt'])
        self.assertIn('At 00:05, cut to <Picture 2>',plan['prompt'])
        self.assertEqual(plan['images'],[{'index':1,'role':'keyframe','seconds':0},{'index':2,'role':'reference','seconds':0}])
        self.assertEqual(plan['audios'],[{'index':1,'role':'lipsync','start':60}])

    def test_9_gpu_calls_keep_full_audio_timeline_and_survive_resume(self):
        with tempfile.TemporaryDirectory() as directory:
            engine=VideoEngine();engine.data=Path(directory);engine.require_model=Mock(return_value={});engine.start_llama=Mock()
            engine.completion=Mock(return_value=(json.dumps(story(9,90)),'stop'));calls=[]
            audio={'id':'audio','mime':'audio/wav','path':'song.wav','name':'song.wav'}
            plan={'prompt':'A music video','images':[],'audios':[{'index':1,'role':'reuse','start':0}]}
            settings={'chat_model':'fixture','context':80000,'video_prompt_max_tokens':4000,'_video_duration':90,
                      '_video_audio_start':30,'_video_audio_source_duration':120,'_video_soundtrack':audio,
                      '_video_editing':'storyboard','_assistant':True}
            def generate(model,settings,local,refs,job,*args,**kwargs):
                calls.append(local);path=engine.data/'outputs'/job/'video.mp4';path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(b'\0\0\0\x18ftypmp42')
                return {'path':path.relative_to(engine.data).as_posix(),'generation':{'width':960,'height':540,'canvas_width':960,'canvas_height':544,'aspect':'16:9','aspect_source':'preset'}}
            engine.generate_video=generate
            with patch('h3chat.soundtrack.compose',return_value={'duration':90}) as mux:
                result=engine.generate_long_video({'id':'hybrid'},settings,plan,[audio],'a'*32,threading.Event(),Mock(),prompt='Fai 9 clip')
            self.assertEqual(len(calls),9);self.assertEqual(result['generation']['scenes'],9)
            self.assertEqual([p['audios'][0]['start'] for p in calls],list(range(30,120,10)))
            self.assertEqual(mux.call_args.kwargs,{'audio_start':30,'audio_duration':90})
            record=engine.data/'outputs'/('a'*32)/'scenes.json';saved=json.loads(record.read_text())
            saved['completed']=8;saved['outputs']=saved['outputs'][:8];saved['parameters']=saved['parameters'][:8];record.write_text(json.dumps(saved))
            calls.clear();engine.completion=Mock(side_effect=AssertionError('Do not replan'))
            with patch('h3chat.soundtrack.compose',return_value={'duration':90}):
                engine.generate_long_video({'id':'hybrid'},settings|{'_video_resume':'a'*32},plan,[audio],'b'*32,threading.Event(),Mock(),prompt='Fai 9 clip')
            self.assertEqual(len(calls),1);self.assertEqual(calls[0]['audios'][0]['start'],110)

import ast
import copy
import json
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock,patch
from h3chat.video_storyboard import validate,local_plan,build
from h3chat.video_engine import VideoEngine
from h3chat.video_request import audio_window
import test_video as fixture

ROOT=Path(__file__).resolve().parents[1]


class StoryboardTests(unittest.TestCase):
    def setUp(self):
        self.refs=[{'id':'i1','mime':'image/png','path':'first.png','name':'first.png'},
                   {'id':'i2','mime':'image/png','path':'second.png','name':'second.png'},
                   {'id':'audio','mime':'audio/wav','path':'song.wav','name':'song.wav'}]
        self.value={'style':'Two schoolteachers, cinematic anime, stable clothing.','shots':[
            {'end':6,'prompt':'The teacher wakes in his bedroom.','continuity':'cut','lip_sync':False,'images':[{'index':2,'role':'reference'}]},
            {'end':15,'prompt':'<Picture 1> sings while walking toward the school.','continuity':'cut','lip_sync':True,'images':[{'index':1,'role':'keyframe'}]},
            {'end':24,'prompt':'The teacher reaches the entrance and greets his students.','continuity':'continue','lip_sync':False,'images':[]}]}
        self.plan={'prompt':'A music video','images':[{'index':i,'role':'reference','seconds':0} for i in (1,2)],'audios':[{'index':1,'role':'lipsync','start':0}]}
        self.settings={'chat_model':'fixture','context':80000,'video_prompt_max_tokens':3000,'_video_duration':24,
                       '_video_audio_start':15,'_video_audio_source_duration':90,'_video_soundtrack':self.refs[-1],
                       '_video_editing':'storyboard','_assistant':True}

    def test_variable_shot_timing_and_only_selected_references_with_audio_offsets(self):
        before=copy.deepcopy(self.value);result=validate(self.value,24,self.refs,'A music video')
        self.assertEqual([(s['start'],s['duration'],s['frames']) for s in result['shots']],[(0,6,144),(6,9,216),(15,9,216)])
        for index,expected_image in ((0,'i2'),(1,'i1')):
            plan,refs=local_plan(result,result['shots'][index],self.plan,self.refs,1,15)
            self.assertEqual([r['id'] for r in refs],[expected_image,'audio'])
            self.assertEqual(plan['images'][0]['index'],1)
            self.assertEqual(plan['audios'][0]['start'],15+result['shots'][index]['start'])
            self.assertEqual(plan['audios'][0]['role'],'reuse' if index==0 else 'lipsync')
        self.assertEqual(self.value,before)
        value=copy.deepcopy(self.value);value['shots'][0]['prompt']='Retain <Picture 2> identity.'
        result=validate(value,24,self.refs,'A film');plan,_=local_plan(result,result['shots'][0],self.plan,self.refs,1,0)
        self.assertIn('<Picture 1>',plan['prompt']);self.assertNotIn('<Picture 2>',plan['prompt'])

    def test_bad_coverage_references_and_copied_action_fail_before_gpu(self):
        for mutate in (lambda v:v['shots'][-1].update(end=23),lambda v:v['shots'][0].update(end=16),
                       lambda v:v['shots'][1].update(end=6),lambda v:v['shots'][0]['images'][0].update(index=3),
                       lambda v:v['shots'][0].update(prompt='Use <Picture 1>.'),lambda v:v['shots'][0].update(lip_sync='yes')):
            value=copy.deepcopy(self.value);mutate(value)
            with self.subTest(value=value),self.assertRaises(ValueError):validate(value,24,self.refs,'A film')
        value=copy.deepcopy(self.value);value['shots'][0]['prompt']=value['shots'][1]['prompt']='The teacher wakes in his bedroom, turns off the alarm clock, and pulls the blanket back over his head.'
        with self.assertRaisesRegex(ValueError,'copia'):validate(value,24,self.refs,'A film')
        self.assertEqual(len(validate(value,24,self.refs,'Ripeti la prima scena')['shots']),3)

    def test_storyboard_repairs_once_and_provider_failures_propagate(self):
        bad=copy.deepcopy(self.value);bad['shots'][-1]['end']=20
        engine=VideoEngine();engine.require_model=Mock(return_value={});engine.start_llama=Mock()
        engine.completion=Mock(side_effect=[(json.dumps(bad),'stop'),(json.dumps(self.value),'stop')])
        result=build(engine,self.plan,self.refs,self.settings,'A film in 3 clip',threading.Event(),Mock(),Path('log'))
        self.assertEqual(len(result['shots']),3);self.assertEqual(engine.completion.call_count,2)
        engine.completion=Mock(side_effect=RuntimeError('Provider 401'))
        with self.assertRaisesRegex(RuntimeError,'401'):build(engine,self.plan,self.refs,self.settings,'A film in 3 clip',threading.Event(),Mock(),Path('log'))
        self.assertEqual(engine.completion.call_count,1)

    def test_per_clip_duration_does_not_shorten_entire_song(self):
        window=audio_window('Usa la canzone intera. FORMAT: 15 seconds per clip',90,storyboard=True)
        self.assertEqual(window['duration'],90)
        self.assertEqual(audio_window('FORMAT: 15 seconds\nAUDIO: 00:00–00:15',90,storyboard=True)['duration'],15)
        self.assertEqual(audio_window('Usa tutta la canzone\nCLIP 1 TIMELINE 00:00–00:15\nFORMAT: 15 seconds\nCLIP 2 TIMELINE 00:15–00:30',90,storyboard=True)['duration'],90)
        self.assertEqual(audio_window('CLIP 2 TIMELINE 00:15–00:30\nFORMAT: 15 seconds',90,storyboard=True)['start'],15)

    def test_large_storyboard_budget_is_used_without_exceeding_half_context(self):
        engine=VideoEngine();engine.require_model=Mock(return_value={});engine.start_llama=Mock()
        engine.completion=Mock(return_value=(json.dumps(self.value),'stop'))
        for configured,expected in ((16000,16000),(100000,40000)):
            settings=self.settings|{'video_prompt_max_tokens':configured}
            build(engine,self.plan,self.refs,settings,'A film in 3 clip',threading.Event(),Mock(),Path('log'))
            self.assertEqual(engine.completion.call_args.args[1]['max_tokens'],expected)
            self.assertEqual(engine.completion.call_args.args[1]['think_level'],'off')
            self.assertEqual(settings['video_prompt_max_tokens'],configured)

    def test_local_clip_ends_and_invented_character_sheet_keyframe_are_corrected(self):
        value={'style':'Kratos and Freya in the cabin.','shots':[
            {'end':15,'prompt':'[Shot 1] <Picture 1> as Kratos. [Shot 2] At 00:03, Freya lowers the axe.',
             'time_basis':'local','continuity':'cut','lip_sync':True,'images':[{'index':1,'role':'keyframe'}]},
            {'end':15,'prompt':'[Shot 1] <Picture 1> as Kratos singing. [Shot 2] At 00:08, the wardrobe collapses.',
             'time_basis':'local','continuity':'cut','lip_sync':True,'images':[{'index':1,'role':'reference'}]}]}
        engine=VideoEngine();engine.require_model=Mock(return_value={});engine.start_llama=Mock()
        engine.completion=Mock(return_value=(json.dumps(value),'stop'))
        settings=self.settings|{'_video_duration':30,'_video_audio_start':0}
        prompt='Two consecutive video clips, 15 seconds each. Video format 16:9. All internal shot times are clip-local.'
        result=build(engine,self.plan,self.refs,settings,prompt,threading.Event(),Mock(),Path('log'))
        self.assertEqual([(x['start'],x['end']) for x in result['shots']],[(0,15),(15,30)])
        self.assertEqual(engine.completion.call_count,1)
        from h3chat.video_options import resolve_canvas,DEFAULTS
        for shot in result['shots']:
            local,selected=local_plan(result,shot,self.plan,self.refs,1,0)
            self.assertEqual(local['images'][0]['role'],'reference')
            self.assertEqual(selected[0]['id'],'i1')
            canvas=resolve_canvas(DEFAULTS,local,[(896,1184)],prompt)
            self.assertEqual((canvas['aspect'],canvas['aspect_source']),('16:9','prompt'))
            self.assertIn('<Picture 1>',local['prompt'])
        context=json.loads(engine.completion.call_args.args[0][1]['content'])
        self.assertEqual(context['required_clip_ends'],[15,30])
        self.assertEqual(context['images'][0]['role'],'reference')

    def test_user_start_frame_keeps_its_role_and_original_aspect(self):
        value=copy.deepcopy(self.value);value['shots'][0]['images']=[{'index':2,'role':'keyframe'}]
        plan=copy.deepcopy(self.plan);plan['images'][1]['role']='keyframe'
        engine=VideoEngine();engine.require_model=Mock(return_value={});engine.start_llama=Mock()
        engine.completion=Mock(return_value=(json.dumps(value),'stop'))
        result=build(engine,plan,self.refs,self.settings,'A film in 3 clip',threading.Event(),Mock(),Path('log'))
        self.assertEqual(result['shots'][0]['images'][0]['role'],'keyframe')

    def test_native_cuts_skip_previous_visual_memory_and_forced_start_frame(self):
        tree=ast.parse((ROOT/'native/video-worker.py').read_text(encoding='utf-8'))
        definition=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='Worker')
        definition.body=[n for n in definition.body if isinstance(n,ast.FunctionDef) and n.name=='condition']
        namespace={};exec(compile(ast.Module(body=[definition],type_ignores=[]),'<native condition>','exec'),namespace)
        for continuity in ('cut','continue'):
            worker=namespace['Worker']();worker.torch=worker.comfy=Mock();worker.h3=Mock();worker.clip=Mock();worker.vae=Mock();worker.fit_frame=Mock()
            worker.h3._empty_av_latent.return_value=({'samples':Mock()},362);worker.anchor='opening';worker.recent=['previous end']
            request={'options':{'width':960,'height':544,'frames':144},'plan':{'prompt':'A new shot','images':[],'audios':[]},'scene_index':2,'continuity':continuity}
            helper=SimpleNamespace(conditioning_set_values=lambda positive,values:positive)
            with patch.dict('sys.modules',{'node_helpers':helper}):worker.condition(request,images=[])
            self.assertEqual(worker.vae.encode.called,continuity=='continue')
            self.assertEqual('minimax_ref_items' in worker.clip.tokenize.call_args.kwargs,continuity=='continue')

    def test_full_generation_and_resume_keep_music_once_and_shot_assignments(self):
        with tempfile.TemporaryDirectory() as directory:
            engine=VideoEngine();engine.data=Path(directory);engine.require_model=Mock(return_value={});engine.start_llama=Mock()
            engine.completion=Mock(return_value=(json.dumps(self.value),'stop'));calls=[]
            def generate(model,settings,plan,refs,job,cancel,stage,**kwargs):
                calls.append((plan,refs,kwargs['scene']));path=engine.data/'outputs'/job/'video.mp4';path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(b'\0\0\0\x18ftypmp42')
                return {'path':path.relative_to(engine.data).as_posix(),'generation':{'width':960,'height':540,'canvas_width':960,'canvas_height':544,'aspect':'16:9','aspect_source':'preset'}}
            engine.generate_video=generate
            with patch('h3chat.soundtrack.compose',return_value={'duration':24}) as mux:
                result=engine.generate_long_video({'id':'hybrid'},self.settings,self.plan,self.refs,'a'*32,threading.Event(),Mock(),prompt='A film in 3 clip')
            self.assertEqual([scene['continuity'] for _,_,scene in calls],['cut','cut','continue'])
            self.assertEqual([plan['audios'][0]['start'] for plan,_,_ in calls],[15,21,30])
            self.assertEqual([[r['id'] for r in refs] for _,refs,_ in calls],[['i2','audio'],['i1','audio'],['audio']])
            self.assertEqual(mux.call_count,1);self.assertEqual(mux.call_args.kwargs,{'audio_start':15,'audio_duration':24})
            self.assertEqual(result['generation']['editing'],'storyboard')
            record=engine.data/'outputs'/('a'*32)/'scenes.json';full_record=json.loads(record.read_text());value=copy.deepcopy(full_record);value['completed']=1;value['outputs']=value['outputs'][:1];value['parameters']=value['parameters'][:1];record.write_text(json.dumps(value))
            calls.clear();engine.completion=Mock(side_effect=AssertionError('Do not replan saved storyboard'))
            with patch('h3chat.soundtrack.compose',return_value={'duration':24}):engine.generate_long_video({'id':'hybrid'},self.settings|{'_video_resume':'a'*32},self.plan,self.refs,'b'*32,threading.Event(),Mock(),prompt='A film')
            self.assertEqual(len(calls),2);self.assertNotIn('resume_memory',calls[0][2]);self.assertEqual(calls[0][2]['continuity'],'cut')
            value=copy.deepcopy(full_record);value['completed']=2;value['outputs']=value['outputs'][:2];value['parameters']=value['parameters'][:2];record.write_text(json.dumps(value));calls.clear()
            with patch('h3chat.soundtrack.compose',return_value={'duration':24}):engine.generate_long_video({'id':'hybrid'},self.settings|{'_video_resume':'a'*32},self.plan,self.refs,'c'*32,threading.Event(),Mock(),prompt='A film')
            memory=calls[0][2]['resume_memory'];self.assertEqual(memory['opening'],str(engine.data/full_record['outputs'][1]));self.assertEqual(memory['recent'],[str(engine.data/full_record['outputs'][1])])


class StoryboardServiceTests(unittest.TestCase):
    setUp=fixture.VideoTests.setUp
    tearDown=fixture.VideoTests.tearDown

    def test_selection_is_captured_and_inactive_storyboard_does_not_block_other_modes(self):
        chat=self.app.store.create_chat()
        with self.assertRaisesRegex(ValueError,'Assistant On'):self.app.send(chat['id'],{'prompt':'Video','video':True,'assistant':False,'video_editing':'storyboard'})
        with patch.object(self.app.engine,'require_model'):
            job=self.app.send(chat['id'],{'prompt':'Crea un video musicale','video':True,'video_editing':'storyboard'})['job_id']
        payload=json.loads(self.app.store.one('SELECT payload FROM jobs WHERE id=?',(job,))['payload'])
        self.assertEqual(payload['settings']['_video_editing'],'storyboard')
        self.assertEqual(self.app.store.chat(chat['id'])['messages'][0]['meta']['video_editing'],'storyboard')
        self.app.store.execute("UPDATE jobs SET status='done' WHERE id=?",(job,))
        with patch.object(self.app.engine,'require_model'):
            self.app.send(chat['id'],{'prompt':'Un ritratto','image_model':self.model['id'],'assistant':False,'video_editing':'storyboard'})

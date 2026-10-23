import copy
import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from h3chat.video_direct_storyboard import read, request_text, attachment_plan
from h3chat.video_storyboard import build, local_plan
from h3chat.video_engine import VideoEngine
import test_video as fixture


def document(value):
    return 'Create a 24 seconds music video in 2 clips. Audio 1 original soundtrack.\n```h3-storyboard\n'+json.dumps(value)+'\n```'


class DirectStoryboardTests(unittest.TestCase):
    def setUp(self):
        self.refs=[{'id':f'i{i}','mime':'image/png','path':f'{i}.png','name':f'{i}.png'} for i in (1,2)]
        self.refs.append({'id':'song','mime':'audio/wav','path':'song.wav','name':'song.wav'})
        self.value={'style':'Warm light. Warrior from <Picture 1>. Singer from <Picture 2>.',
                    'shots':[{'end':15,'prompt':'[Shot 1] <Picture 2> waves with closed lips. [Shot 2] At 00:06.000, she turns toward a tree.',
                              'continuity':'cut','lip_sync':False,'time_basis':'local','images':[{'index':2,'role':'reference'}]},
                             {'end':24,'prompt':'[Shot 1] <Picture 1> enters the room and performs the male vocal alone.',
                              'continuity':'continue','lip_sync':True,'time_basis':'local','images':[{'index':1,'role':'reference'}]}]}
        self.settings={'_assistant':False,'_video_editing':'storyboard','_video_duration':24,
                       '_video_audio_start':3,'_video_audio_source_duration':40,'_video_soundtrack':self.refs[-1]}

    def test_explicit_plan_skips_all_llm_calls_and_binds_only_selected_images(self):
        engine=Mock();engine.start_llama.side_effect=AssertionError('No LLM');engine.completion.side_effect=AssertionError('No LLM')
        prompt=document(self.value);before=copy.deepcopy(self.value)
        plan=attachment_plan(self.refs,self.refs[-1],24)
        result=build(engine,plan,self.refs,self.settings,prompt,threading.Event(),Mock(),Path('unused'))
        self.assertTrue(result['direct']);self.assertFalse(engine.start_llama.called);self.assertFalse(engine.completion.called)
        for position,expected in enumerate((['i2','song'],['i1','song'])):
            native,refs=local_plan(result,result['shots'][position],plan,self.refs,1,3)
            self.assertEqual([r['id'] for r in refs],expected)
            self.assertIn('<Picture 1>',native['prompt']);self.assertNotIn('<Picture 2>',native['prompt'])
            self.assertEqual(native['audios'][0]['start'],3+15*position)
            self.assertEqual(native['audios'][0]['role'],'reuse' if position==0 else 'lipsync')
            self.assertEqual(native['prompt'].count(result['shots'][position]['prompt'].replace('<Picture 2>','<Picture 1>')),1)
        self.assertEqual(self.value,before)

    def test_bad_references_coverage_and_ambiguous_documents_fail_before_llm(self):
        for mutate in (lambda v:v['shots'][0].update(prompt='Use <Picture 1> instead.'),
                       lambda v:v['shots'][-1].update(end=23),
                       lambda v:v['shots'][0].update(continuity='guess')):
            value=copy.deepcopy(self.value);mutate(value);engine=Mock()
            with self.assertRaises(ValueError):
                build(engine,{},self.refs,self.settings,document(value),threading.Event(),Mock(),Path('unused'))
            self.assertFalse(engine.start_llama.called)
        for text in ('```h3-storyboard\n{}','```h3-storyboard\nbad\n```',document(self.value)+'\n'+document(self.value)):
            with self.assertRaises(ValueError):read(text)
        self.assertIsNone(read('A normal free-text prompt'))
        self.assertNotIn('Shot 2',request_text(document(self.value)))

    def test_full_execution_keeps_audio_offsets_memory_and_checkpoint_without_llm(self):
        with tempfile.TemporaryDirectory() as directory:
            engine=VideoEngine();engine.data=Path(directory)
            engine.start_llama=Mock(side_effect=AssertionError('No LLM'))
            engine.completion=Mock(side_effect=AssertionError('No LLM'));calls=[]
            def generate(model,settings,plan,refs,job,cancel,stage,**kwargs):
                calls.append((plan,refs,kwargs['scene']))
                path=engine.data/'outputs'/job/'video.mp4';path.parent.mkdir(parents=True,exist_ok=True)
                path.write_bytes(b'\0\0\0\x18ftypmp42')
                return {'path':path.relative_to(engine.data).as_posix(),'generation':{'width':960,'height':540,
                        'canvas_width':960,'canvas_height':544,'aspect':'16:9','aspect_source':'preset'}}
            engine.generate_video=generate
            with patch('h3chat.soundtrack.compose',return_value={'duration':24}) as mux:
                result=engine.generate_long_video({'id':'model'},self.settings,attachment_plan(self.refs,self.refs[-1],24),
                           self.refs,'a'*32,threading.Event(),Mock(),prompt=document(self.value))
            self.assertEqual([s['continuity'] for _,_,s in calls],['cut','continue'])
            self.assertEqual([p['audios'][0]['start'] for p,_,_ in calls],[3,18])
            self.assertEqual([[r['id'] for r in refs] for _,refs,_ in calls],[['i2','song'],['i1','song']])
            self.assertEqual(mux.call_count,1);self.assertTrue(result['generation']['storyboard']['direct'])
            saved=json.loads((engine.data/'outputs'/('a'*32)/'scenes.json').read_text())
            self.assertEqual(saved['completed'],2);self.assertTrue(saved['storyboard']['direct'])
            self.assertFalse(engine.start_llama.called);self.assertFalse(engine.completion.called)


class DirectStoryboardServiceTests(unittest.TestCase):
    setUp=fixture.VideoTests.setUp
    tearDown=fixture.VideoTests.tearDown

    def test_direct_request_captures_assistant_off_and_rejects_on_before_queue(self):
        chat=self.app.store.create_chat();value={'style':'Warm light.','shots':[]}
        body={'prompt':document(value),'video':True,'assistant':False,'video_editing':'continuous'}
        with patch.object(self.app.engine,'require_model'):
            job=self.app.send(chat['id'],body)['job_id']
        payload=json.loads(self.app.store.one('SELECT payload FROM jobs WHERE id=?',(job,))['payload'])
        self.assertFalse(payload['settings']['_assistant']);self.assertEqual(payload['settings']['_video_editing'],'storyboard')
        with self.assertRaisesRegex(ValueError,'Disattiva Assistant'):
            self.app.send(chat['id'],body|{'assistant':True})

    def test_execution_bypasses_initial_refinement_and_uses_header_audio_window(self):
        chat=self.app.store.create_chat()
        refs=[{'id':'song','name':'song.wav','path':'song.wav','mime':'audio/wav'}]
        value={'style':'Winter light.','shots':[
            {'end':15,'prompt':'[Shot 1] Snow falls on a house.','time_basis':'local',
             'continuity':'cut','lip_sync':False,'images':[]},
            {'end':24,'prompt':'[Shot 1] The door opens.','time_basis':'local',
             'continuity':'continue','lip_sync':False,'images':[]}]}
        with patch.object(self.app,'validate_media',return_value=refs):
            ident=self.app.send(chat['id'],{'prompt':document(value),'video':True,'assistant':False,'media':refs})['job_id']
        job=self.app.store.one('SELECT * FROM jobs WHERE id=?',(ident,))
        media={'id':ident,'name':'video.mp4','path':f'outputs/{ident}/video.mp4','mime':'video/mp4','generation':{'duration':24}}
        with patch('h3chat.soundtrack.probe',return_value={'duration':24}), \
             patch.object(self.app.engine,'refine_video',side_effect=AssertionError('No initial planner')) as refine, \
             patch.object(self.app.engine,'generate_long_video',return_value=media) as generate, \
             patch.object(self.app.engine,'start_llama',side_effect=AssertionError('No LLM')) as llama:
            self.app.execute_job(job,threading.Event())
        refine.assert_not_called();llama.assert_not_called();generate.assert_called_once()
        self.assertEqual(generate.call_args.args[1]['_video_duration'],24)
        self.assertEqual(generate.call_args.args[2]['audios'][0]['role'],'lipsync')
        answer=self.app.store.chat(chat['id'])['messages'][-1]
        self.assertEqual(answer['status'],'done',answer['meta']);self.assertFalse(answer['meta']['assistant_on'])

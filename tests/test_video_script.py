import copy,json,tempfile,threading,unittest
from pathlib import Path
from unittest.mock import Mock
from h3chat.video_engine import VideoEngine
from h3chat.video_timeline import timeline
from h3chat.video_routing import attachment_instructions
from h3chat.remote_llm import Client,EmptyCompletion,StructuredCompletionError
from h3chat.downloads import Cancelled

class SceneScriptTests(unittest.TestCase):
    def setUp(self):
        self.engine=VideoEngine();self.settings={'context':500000,'max_tokens':100000,'video_prompt_max_tokens':3000,'think_level':'med'}
        self.plan={'prompt':'A continuous, playful film','images':[],'audios':[{'index':1,'role':'lipsync','start':0}]}
    def complete(self,messages,settings,cancel,**kwargs):
        clips=json.loads(messages[1]['content'])['clips']
        return json.dumps({'scenes':[f'Clip {clip["index"]+1}, retain <Audio 1> lip sync.' for clip in clips]}),'stop'
    def test_ten_scenes_are_bounded_and_keep_continuity_without_changing_chat(self):
        before=copy.deepcopy(self.settings);self.engine.completion=Mock(side_effect=self.complete)
        scripts=self.engine.scene_scripts(self.plan,timeline(150),self.settings,threading.Event(),lambda _:None,prompt='Synthetic request')
        self.assertEqual(len(scripts),10);calls=self.engine.completion.call_args_list
        self.assertEqual([len(json.loads(c.args[0][1]['content'])['clips']) for c in calls],[3,3,3,1])
        for call in calls:
            self.assertEqual(call.args[1]['think_level'],'off');self.assertEqual(call.args[1]['max_tokens'],3000)
        context=json.loads(calls[1].args[0][1]['content']);self.assertEqual(context['opening'],scripts[0]);self.assertEqual(context['previous'],scripts[1:3])
        self.assertEqual(context['plan']['audios'],self.plan['audios']);self.assertEqual(self.settings,before)
    def test_length_is_handled_before_parsing_and_splits_only_incomplete_group(self):
        responses=iter([('{"scenes":["unfinished','length'),(json.dumps({'scenes':['first complete']}),'stop'),(json.dumps({'scenes':['second complete']}),'stop')])
        self.engine.completion=Mock(side_effect=lambda *a,**kw:next(responses))
        result=self.engine.scene_scripts(self.plan,timeline(30),self.settings,threading.Event(),lambda _:None,prompt='Synthetic')
        self.assertEqual(result,['first complete','second complete']);self.assertEqual(self.engine.completion.call_count,3)
        self.assertEqual(json.loads(self.engine.completion.call_args_list[-1].args[0][1]['content'])['previous'],['first complete'])
    def test_empty_single_scene_retries_once_and_small_budget_uses_one_clip(self):
        responses=iter([EmptyCompletion('Empty'),(json.dumps({'scenes':['complete']}),'stop'),(json.dumps({'scenes':['next']}),'stop')])
        def complete(*args,**kwargs):
            result=next(responses)
            if isinstance(result,Exception):raise result
            return result
        self.engine.completion=Mock(side_effect=complete)
        scripts=self.engine.scene_scripts(self.plan,timeline(30),self.settings|{'video_prompt_max_tokens':256},threading.Event(),lambda _:None,prompt='Synthetic')
        self.assertEqual(scripts,['complete','next'])
        for call in self.engine.completion.call_args_list:self.assertEqual(len(json.loads(call.args[0][1]['content'])['clips']),1)
    def test_failed_plan_does_not_start_video_generation(self):
        self.engine.completion=Mock(side_effect=EmptyCompletion('Empty'));self.engine.require_model=Mock(return_value={});self.engine.start_llama=Mock();self.engine.generate_video=Mock()
        with tempfile.TemporaryDirectory() as tmp:
            self.engine.data=Path(tmp);audio={'id':'track','mime':'audio/wav'}
            settings=self.settings|{'chat_model':'synthetic','_assistant':True,'_video_duration':30,'_video_soundtrack':audio}
            with self.assertRaisesRegex(ValueError,'due tentativi'):
                self.engine.generate_long_video({},settings,self.plan,[audio],'job',threading.Event(),lambda _:None,prompt='Synthetic')
        self.engine.generate_video.assert_not_called();self.assertEqual(self.engine.completion.call_count,3)
    def test_audio_only_script_repairs_invented_picture_before_accepting_batch(self):
        valid=['Stage performance with <Audio 1> lip sync.','Battle continues with <Audio 1> lip sync.']
        self.engine.completion=Mock(side_effect=[
            (json.dumps({'scenes':['Use <Picture 1> as start frame.',valid[1]]}),'stop'),
            (json.dumps({'scenes':valid}),'stop')])
        before=copy.deepcopy(self.plan);stages=[]
        result=self.engine.scene_scripts(self.plan,timeline(30),self.settings,threading.Event(),stages.append,prompt='Music video from attached audio')
        self.assertEqual(result,valid);self.assertEqual(self.plan,before)
        first=self.engine.completion.call_args_list[0].args[0][0]['content']
        retry=self.engine.completion.call_args_list[1].args[0][0]['content']
        self.assertIn('Allowed Picture labels: NONE',first);self.assertIn('Allowed Audio labels: <Audio 1>',first)
        self.assertNotIn('<Picture 1>',first);self.assertIn('Previous output failed scene validation',retry)
        self.assertIn('correggo i riferimenti',' '.join(stages));self.assertEqual(self.engine.completion.call_count,2)
    def test_repeated_invented_reference_fails_before_loading_video(self):
        self.engine.completion=Mock(return_value=(json.dumps({'scenes':['Valid <Audio 1>.','Invented <Picture 1>.']}),'stop'))
        self.engine.require_model=Mock(return_value={});self.engine.start_llama=Mock();self.engine.generate_video=Mock()
        with tempfile.TemporaryDirectory() as tmp:
            self.engine.data=Path(tmp);audio={'id':'track','mime':'audio/wav'}
            settings=self.settings|{'chat_model':'synthetic','_assistant':True,'_video_duration':30,'_video_soundtrack':audio}
            with self.assertRaisesRegex(ValueError,'scena 2.*dopo la correzione'):
                self.engine.generate_long_video({},settings,self.plan,[audio],'job',threading.Event(),lambda _:None,prompt='Music video')
        self.engine.generate_video.assert_not_called();self.assertEqual(self.engine.completion.call_count,2)
    def test_actual_picture_and_audio_are_preserved_across_local_keyframe_times(self):
        plan=copy.deepcopy(self.plan);plan['images']=[{'index':1,'role':'keyframe','seconds':20}]
        self.engine.completion=Mock(return_value=(json.dumps({'scenes':['Retain <Picture 1> identity and <Audio 1>.','Keyframe <Picture 1> at 5 seconds; sing with <Audio 1>.']}),'stop'))
        result=self.engine.scene_scripts(plan,timeline(30),self.settings,threading.Event(),lambda _:None,prompt='Use image and soundtrack')
        self.assertEqual(len(result),2);self.assertEqual(plan['images'][0]['seconds'],20)
        instructions=self.engine.completion.call_args.args[0][0]['content']
        self.assertIn('Allowed Picture labels: <Picture 1>',instructions)
        self.assertIn('Allowed Audio labels: <Audio 1>',instructions)
    def test_invented_audio_is_repaired_and_no_attachment_inventory_is_explicit(self):
        self.engine.completion=Mock(side_effect=[
            (json.dumps({'scenes':['Reuse <Audio 2>.']}),'stop'),
            (json.dumps({'scenes':['Reuse <Audio 1>.']}),'stop')])
        result=self.engine.scene_scripts(self.plan,timeline(15),self.settings,threading.Event(),lambda _:None,prompt='Use soundtrack')
        self.assertEqual(result,['Reuse <Audio 1>.']);self.assertEqual(self.engine.completion.call_count,2)
        inventory=attachment_instructions([],[])
        self.assertIn('Allowed Picture labels: NONE',inventory);self.assertIn('Allowed Audio labels: NONE',inventory)
    def test_provider_errors_and_cancellation_are_not_retried(self):
        self.engine.completion=Mock(side_effect=RuntimeError('Provider API 401'))
        with self.assertRaisesRegex(RuntimeError,'401'):self.engine.scene_scripts(self.plan,timeline(30),self.settings,threading.Event(),lambda _:None,prompt='Synthetic')
        self.assertEqual(self.engine.completion.call_count,1)
        cancel=threading.Event();cancel.set();self.engine.completion.reset_mock()
        with self.assertRaises(Cancelled):self.engine.scene_scripts(self.plan,timeline(30),self.settings,cancel,lambda _:None,prompt='Synthetic')
        self.engine.completion.assert_not_called()
    def test_empty_api_output_limit_has_specific_error(self):
        client=Client()
        def exchange(*args,**kwargs):kwargs['on_event']({'choices':[{'delta':{},'finish_reason':'length'}]})
        client.exchange=exchange
        with self.assertRaisesRegex(EmptyCompletion,'esaurito i token'):
            client.completion({'model':'synthetic','thinking':'none'},'test',[],self.settings|{'temperature':.7},threading.Event(),on_text=lambda _:None)

    def test_identical_scene_bodies_are_repaired_before_accepting_batch(self):
        opening='The camera flies over the walls, approaches the bedroom, and shows the teacher waking up to his ringing alarm clock.'
        later='The teacher leaves his bed, packs his books, and hurries down the stairs toward the school gate.'
        self.engine.completion=Mock(side_effect=[(json.dumps({'scenes':[opening,opening]}),'stop'),(json.dumps({'scenes':[opening,later]}),'stop')])
        stages=[];result=self.engine.scene_scripts(self.plan,timeline(30),self.settings,threading.Event(),stages.append,prompt='A continuous school parody')
        self.assertEqual(result,[opening,later]);self.assertIn('scene ripetute',' '.join(stages))
        context=json.loads(self.engine.completion.call_args_list[1].args[0][1]['content'])
        self.assertEqual(context['rejected_scenes'],[opening,opening])

    def test_copy_across_batches_is_rejected_before_loading_video(self):
        text='The camera flies over the walls, approaches the bedroom, and shows the teacher waking up to his ringing alarm clock.'
        self.engine.completion=Mock(return_value=(json.dumps({'scenes':[text]}),'stop'))
        self.engine.require_model=Mock(return_value={});self.engine.start_llama=Mock();self.engine.generate_video=Mock()
        with tempfile.TemporaryDirectory() as tmp:
            self.engine.data=Path(tmp);audio={'id':'track','mime':'audio/wav'}
            settings=self.settings|{'chat_model':'synthetic','_assistant':True,'_video_duration':30,'_video_soundtrack':audio,'video_prompt_max_tokens':256}
            with self.assertRaisesRegex(ValueError,'scena 2.*ripete.*Nessun video'):
                self.engine.generate_long_video({},settings,self.plan,[audio],'job',threading.Event(),lambda _:None,prompt='A continuous parody')
        self.engine.generate_video.assert_not_called()

    def test_deliberate_repeat_is_allowed(self):
        text='The camera flies over the walls, approaches the bedroom, and shows the teacher waking up to his ringing alarm clock.'
        self.engine.completion=Mock(return_value=(json.dumps({'scenes':[text,text]}),'stop'))
        self.assertEqual(self.engine.scene_scripts(self.plan,timeline(30),self.settings,threading.Event(),lambda _:None,prompt='Ripeti la stessa scena due volte'),[text,text])

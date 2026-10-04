import copy,json,tempfile,threading,unittest
from pathlib import Path
from unittest.mock import Mock
from h3chat.video_engine import VideoEngine
from h3chat.video_timeline import timeline
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


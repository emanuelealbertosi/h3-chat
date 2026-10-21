"""Explicit attention choices are frozen in requests and never mutate presets."""
import ast,copy,json,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock,patch
from h3chat.video_options import options,validate
from h3chat.video_attention import prompt_choice
from h3chat.veda_memory import head_chunks_for_edit
import test_video as fixture
import test_video_recreate as replay_fixture


class AttentionChoiceTests(unittest.TestCase):
    setUp=fixture.VideoTests.setUp
    tearDown=fixture.VideoTests.tearDown

    def test_manual_groups_override_only_automatic_heuristic(self):
        config=dict(aligned=True,width=1344,height=768,frames=240,total_bytes=16*1024**3)
        self.assertEqual(head_chunks_for_edit(8,**config),56)
        self.assertEqual(head_chunks_for_edit(8,**config,manual=True),8)
        self.assertEqual(head_chunks_for_edit(56,**config,manual=True),56)

    def test_explicit_veda_and_plain_choices_survive_queue_and_reload(self):
        from h3chat.request_draft import load
        before=copy.deepcopy(self.app.store.settings());chat=self.app.store.create_chat()['id']
        choices=[{'attention':'veda','attention_chunks':n,'attention_chunks_mode':'manual'} for n in (8,56)]
        choices.append({'attention':'pytorch','attention_chunks':0,'attention_chunks_mode':'auto'})
        choices.append({'attention':'comfy_kitchen','attention_chunks':0,'attention_chunks_mode':'auto'})
        for parameters in choices:
            job=self.app.send(chat,{'prompt':'Video','video':True,'assistant':False,'video_parameters':parameters})['job_id']
            payload=json.loads(self.app.store.one('SELECT payload FROM jobs WHERE id=?',(job,))['payload'])
            opts=options(self.model,payload['settings'],False)
            for key,value in parameters.items():self.assertEqual(opts[key],value)
            message=self.app.store.one('SELECT message_id FROM jobs WHERE id=?',(job,))
            # Reload by the queued original user message, without enqueueing.
            draft=load(self.app,chat,message['message_id'])
            for key,value in parameters.items():self.assertEqual(draft['controls']['video_parameters'][key],value)
            self.app.store.execute("UPDATE jobs SET status='cancelled' WHERE id=?",(job,))
        self.assertEqual(self.app.store.settings(),before)

    def test_prompt_aliases_and_explicit_control_precedence(self):
        self.assertEqual(prompt_choice('Crea video\nVEDA 8')['attention_chunks'],8)
        self.assertEqual(prompt_choice('Video con VEDA 56')['attention_chunks'],56)
        self.assertEqual(prompt_choice('Crea video\nAccelerazione: nessuna')['attention'],'pytorch')
        self.assertEqual(prompt_choice('Crea video\nAccelerazione: ComfyKitchen')['attention'],'comfy_kitchen')
        self.assertEqual(prompt_choice('Accelerazione: Sage')['attention'],'sage')
        self.assertEqual(prompt_choice('Accelerazione: VEDA')['attention_chunks_mode'],'auto')
        self.assertEqual(prompt_choice('camera senza accelerazione brusca'),{})
        for text in ('VEDA 8 oppure VEDA 56','VEDA 8\nno accelerazione','VEDA 56\nAccelerazione: ComfyKitchen','Accelerazione: Sage\nAccelerazione: PyTorch'):
            with self.assertRaises(ValueError):prompt_choice(text)
        chat=self.app.store.create_chat()['id']
        ident=self.app.send(chat,{'prompt':'Video\nVEDA 56','video':True,'assistant':False,
            'video_parameters':{'attention':'pytorch','attention_chunks_mode':'auto'}})['job_id']
        payload=json.loads(self.app.store.one('SELECT payload FROM jobs WHERE id=?',(ident,))['payload'])
        self.assertEqual(options(self.model,payload['settings'],False)['attention'],'pytorch')

    def test_invalid_manual_modes_fail_before_render(self):
        for changes in ({'attention_chunks_mode':'wrong'},{'attention':'veda','attention_chunks_mode':'manual','attention_chunks':0},
            {'attention':'sage','attention_chunks_mode':'manual','attention_chunks':56}):
            with self.subTest(changes=changes),self.assertRaises(ValueError):validate(changes)

    def native_selector(self):
        tree=ast.parse((Path(__file__).resolve().parents[1]/'native/video-worker.py').read_text(encoding='utf-8'))
        cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='Worker')
        method=next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='configure_attention')
        ns={'emit':Mock(),'logging':Mock(),'chunked_attention':Mock()}
        exec(compile(ast.Module(body=[method],type_ignores=[]),'native-worker','exec'),ns)
        return ns

    def test_no_acceleration_bypasses_sage_and_veda_in_native_worker(self):
        ns=self.native_selector()
        attention=SimpleNamespace(SAGE_ATTENTION_IS_AVAILABLE=True,attention_pytorch=object(),attention_sage=object())
        modules=SimpleNamespace(attention=attention)
        worker=SimpleNamespace(model=Mock(),torch=SimpleNamespace(cuda=SimpleNamespace(get_device_properties=lambda n:SimpleNamespace(total_memory=16*1024**3))))
        with patch.dict('sys.modules',{'comfy.ldm.modules':modules}):
            actual=ns['configure_attention'](worker,'pytorch')
        self.assertEqual(actual,'pytorch');self.assertEqual(worker.attention_chunks,1)
        worker.model.set_model_optimized_attention.assert_called_once_with(attention.attention_pytorch)
        ns['chunked_attention'].assert_not_called()

    def test_comfy_kitchen_selects_native_kernel_and_preserves_container_path(self):
        ns=self.native_selector();kernel=Mock();kernel.container_function=object()
        attention=SimpleNamespace(COMFY_KITCHEN_INT8_ATTENTION_IS_AVAILABLE=True,attention_comfy_kitchen_int8=kernel)
        worker=SimpleNamespace(model=Mock())
        with patch.dict('sys.modules',{'comfy.ldm.modules':SimpleNamespace(attention=attention)}):
            self.assertEqual(ns['configure_attention'](worker,'comfy_kitchen'),'comfy_kitchen')
        worker.model.set_model_optimized_attention.assert_called_once_with(kernel)
        self.assertEqual(worker.attention_chunks,1);ns['chunked_attention'].assert_not_called()

    def test_comfy_kitchen_unavailable_fails_without_silent_substitution(self):
        ns=self.native_selector();worker=SimpleNamespace(model=Mock())
        for attention in (SimpleNamespace(),SimpleNamespace(COMFY_KITCHEN_INT8_ATTENTION_IS_AVAILABLE=False,attention_comfy_kitchen_int8=Mock())):
            with patch.dict('sys.modules',{'comfy.ldm.modules':SimpleNamespace(attention=attention)}),self.assertRaisesRegex(ValueError,'ComfyKitchen INT8 attention non disponibile'):
                ns['configure_attention'](worker,'comfy_kitchen')
        worker.model.set_model_optimized_attention.assert_not_called()


class AttentionAcrossClipsTests(unittest.TestCase):
    setUp=replay_fixture.VideoRecreateTests.setUp
    tearDown=replay_fixture.VideoRecreateTests.tearDown
    original=replay_fixture.VideoRecreateTests.original
    film=replay_fixture.VideoRecreateTests.film
    renderer=replay_fixture.VideoRecreateTests.renderer
    execute=replay_fixture.VideoRecreateTests.execute

    def test_recreate_passes_explicit_backend_to_every_clip_and_keeps_source(self):
        from h3chat.video_recreate import request
        chat,ident,refs,outputs,p=self.film();before=copy.deepcopy(self.app.store.settings())
        source=(self.app.data/'outputs'/ident/'scenes.json').read_bytes()
        for selection in ({'attention':'comfy_kitchen','attention_chunks':0,'attention_chunks_mode':'auto'},
                {'attention':'veda','attention_chunks':8,'attention_chunks_mode':'manual'}):
            new=request(self.app,chat,{'source':ident,'parameters':selection})['job_id'];calls=[]
            with patch.object(self.app.engine,'generate_video',side_effect=self.renderer(calls)),patch('h3chat.soundtrack.probe',return_value={'duration':60}),patch('h3chat.soundtrack.compose',return_value={'duration':42}):self.execute(new)
            self.assertEqual(self.app.store.chat(chat)['messages'][-1]['status'],'done')
            self.assertEqual(len(calls),3)
            for call in calls:
                for key,value in selection.items():self.assertEqual(call[2][key],value)
        self.assertEqual(self.app.store.settings(),before)
        self.assertEqual((self.app.data/'outputs'/ident/'scenes.json').read_bytes(),source)

    def test_edit_preserves_shared_attention_controls(self):
        from h3chat.video_edit import request
        chat,ident,refs,outputs,p=self.film()
        for selection in ({'attention':'comfy_kitchen','attention_chunks':0,'attention_chunks_mode':'auto'},
                {'attention':'veda','attention_chunks':56,'attention_chunks_mode':'manual'}):
            new=request(self.app,chat,{'source':ident,'assistant':False,'parameters':selection,
                'patches':[{'clip':2,'prompt':'A closer view'}]})['job_id']
            payload=json.loads(self.app.store.one('SELECT payload FROM jobs WHERE id=?',(new,))['payload'])
            opts=options(self.model,payload['settings'],False)
            for key,value in selection.items():self.assertEqual(opts[key],value)
            self.app.store.execute("UPDATE jobs SET status='cancelled' WHERE id=?",(new,))


if __name__=='__main__':unittest.main()

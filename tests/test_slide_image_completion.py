"""Exercise image planning through real local/API completion adapters, without models."""
import json
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from h3chat.engine import Engine
from h3chat.slide_generation_images import create
from h3chat.store import DEFAULTS

ROOT = Path(__file__).resolve().parents[1]


class CompletionStub(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        self.server.calls.append(body)
        text = json.dumps({'images': [
            {'slide': slide, 'prompt': 'colorful illustration, ' * 30,
             'description': 'Illustrazione sintetica ' + str(slide)} for slide in (1, 8)]})
        self.send_response(200)
        self.send_header('Content-Type', 'text/event-stream' if body.get('stream') else 'application/json')
        self.end_headers()
        if body.get('stream'):
            for piece in (text[:200], text[200:]):
                value = {'choices': [{'delta': {'content': piece}, 'finish_reason': None}]}
                self.wfile.write(('data: ' + json.dumps(value) + '\n\n').encode())
            value = {'choices': [{'delta': {}, 'finish_reason': self.server.finish}]}
            self.wfile.write(('data: ' + json.dumps(value) + '\n\ndata: [DONE]\n\n').encode())
        else:
            self.wfile.write(json.dumps({'choices': [{'message': {'content': text},
                                                     'finish_reason': self.server.finish}]}).encode())


class SlideImageCompletionTests(unittest.TestCase):
    def setUp(self):
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), CompletionStub)
        self.server.daemon_threads = True
        self.server.calls = []
        self.server.finish = 'stop'
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.temp = tempfile.TemporaryDirectory()
        self.engine = Engine(ROOT, self.temp.name, {})
        self.engine.active = SimpleNamespace(port=self.server.server_port,
                                             api_key='synthetic-test', acceleration=None)
        self.app = SimpleNamespace(engine=self.engine, store=Mock())
        self.image = {'id': 'synthetic-image', 'name': 'Anima fixture', 'architecture': 'anima'}
        self.settings = DEFAULTS | {'context': 8192, 'prompt_max_tokens': 3000,
                                   '_slides': {'image_model': self.image['id'], 'design': 'professional'}}
        self.outline = {'title': 'Collaudo', 'slides': [{'title': str(i), 'purpose': 'Test'} for i in range(8)]}

    def tearDown(self):
        self.engine.stop()
        self.server.shutdown()
        self.server.server_close()
        self.temp.cleanup()

    def run_plan(self, remote=False):
        model = {'id': 'synthetic-chat', 'name': 'Chat fixture', 'api': remote}
        self.engine.active_model = model
        self.engine.remote_config = ({'base_url': f'http://127.0.0.1:{self.server.server_port}/v1',
                                      'model': 'test', 'vision': False, 'thinking': 'none',
                                      'format': 'json_schema'}, 'synthetic-test') if remote else None
        generated = []

        def generate(image_model, settings, prompt, refs, ident, cancel, stage):
            self.assertEqual(settings['memory_policy'], 'on_demand')
            self.assertEqual(refs, [])
            self.assertEqual(stop.call_count,0 if image_model.get('remote_media') else 1)
            reload.assert_not_called()
            media = {'id': ident, 'mime': 'image/png', 'path': 'outputs/' + ident + '/image.png'}
            generated.append(media)
            return media

        stage = Mock()
        with patch.object(self.engine, 'require_model', return_value=self.image), \
             patch.object(self.engine, 'generate', side_effect=generate) as images, \
             patch.object(self.engine, 'stop') as stop, patch.object(self.engine, 'start_llama') as reload:
            self.last_calls = images, stop, reload
            result = create(self.app, {'id': 'fixture', 'payload': '{"loras":[]}'}, self.outline,
                            [{'role': 'user', 'content': 'Crea slide'}], self.settings, model,
                            threading.Event(), stage, Path(self.temp.name) / 'test.log', {})
        return result, images, stop, reload, stage

    def test_local_and_api_plans_stream_then_generate_all_images_and_reload_llm_once(self):
        for remote in (False, True):
            with self.subTest(remote=remote):
                (assets, captions), images, stop, reload, stage = self.run_plan(remote)
                self.assertEqual(len(assets), 2)
                self.assertEqual(set(captions), {media['id'] for media in assets})
                self.assertEqual(images.call_count, 2)
                self.assertEqual(stop.call_count,2)
                reload.assert_called_once()
                self.assertEqual(reload.call_args.args[1],self.settings)
                self.assertTrue(self.server.calls[-1]['stream'])
                self.assertEqual(self.server.calls[-1]['max_tokens'], 1920)
                self.assertTrue(any('caratteri ricevuti' in call.args[0] for call in stage.call_args_list))

    def test_truncated_plan_is_rejected_before_any_image_or_model_switch(self):
        self.server.finish = 'length'
        for remote in (False, True):
            with self.subTest(remote=remote):
                with self.assertRaisesRegex(ValueError, 'Piano immagini incompleto'):
                    self.run_plan(remote)
                images, stop, reload = self.last_calls
                images.assert_not_called()
                stop.assert_not_called()
                reload.assert_not_called()

    def test_remote_images_keep_the_chat_model_and_avoid_an_unnecessary_reload(self):
        self.image['remote_media']=True
        _,images,stop,reload,_=self.run_plan()
        self.assertEqual(images.call_count,2)
        stop.assert_not_called();reload.assert_not_called()

    def test_style_reaches_planner_and_actual_image_prompts_for_tags_and_prose(self):
        for remote in (False,True):
            for architecture in ('anima','flux2'):
                for design,cue in (('professional','professional editorial visual style'),
                                   ('playful','playful visual style'),('comic','comic book visual style')):
                    with self.subTest(remote=remote,architecture=architecture,design=design):
                        self.image['architecture']=architecture
                        self.settings['_slides']['design']=design
                        _,images,_,_,_=self.run_plan(remote)
                        request=self.server.calls[-1]['messages'][-1]['content']
                        self.assertIn('STILE VISIVO:',request)
                        self.assertIn('Ogni prompt deve essere autosufficiente',request)
                        for call in images.call_args_list:
                            prompt=call.args[2]
                            self.assertIn(cue,prompt)
                            self.assertTrue(prompt.startswith('colorful illustration, '))
                            self.assertEqual('\nVisual direction:' in prompt,architecture=='flux2')
                        # The style does not add a second planning call or another image batch.
                        self.assertEqual(images.call_count,2)

import ast
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import test_residency as fixture
from h3chat.residency import Session

ROOT = Path(__file__).resolve().parents[1]


class WarmEngineTests(unittest.TestCase):
    setUp = fixture.ResidencyTests.setUp
    tearDown = fixture.ResidencyTests.tearDown
    loaded = fixture.ResidencyTests.loaded
    # Reuse the tiny process/model fixture, not the parent test cases.
    def vision(self, settings=None):
        self.models['image']['engine'] = 'vision'
        session = self.loaded('image', 'image', settings)
        session.worker_backend = 'cpu'
        session.send = Mock()
        session.wait = Mock(return_value={'event': 'unloaded'})
        return session

    def test_model_is_unloaded_and_runtime_reused_after_chat(self):
        image = self.vision()
        self.loaded('chat', 'llm')
        image.send.assert_called_once_with({'op': 'unload'})
        self.assertTrue(image.alive())
        self.assertFalse(image.ready)
        self.assertTrue(self.engine.snapshot()['warm_image_engine'])
        self.assertEqual([s['kind'] for s in self.engine.snapshot()['models']], ['chat'])
        again = self.engine._activate('image', self.models['image'], self.settings,
            self.root/'next.log', self.cancel)
        self.assertIs(again, image)
        self.assertIsNone(self.engine.warm_image)
        self.assertFalse(again.ready)  # Must load weights, cannot infer from old model.

    def test_cache_off_full_release_and_backend_change_close_the_runtime(self):
        for action in ('disable', 'release', 'device'):
            image = self.vision()
            self.loaded('chat', 'llm')
            if action == 'disable':
                self.engine.configure(self.settings | {'ram_cache_gb': 0})
            elif action == 'release':
                self.engine.stop()
            else:
                self.engine._activate('image', self.models['image'], self.settings | {'profile':'low','backend':'cuda'}, self.root/'next.log', self.cancel)
            self.assertFalse(image.alive(), action)
            self.assertIsNone(self.engine.warm_image)

    def test_unload_failure_falls_back_to_terminating_the_process(self):
        image = self.vision()
        image.wait.side_effect = RuntimeError('unload failed')
        self.loaded('chat', 'llm')
        self.assertFalse(image.alive())
        self.assertIsNone(self.engine.warm_image)

    def test_cancel_before_activation_keeps_existing_ownership(self):
        image = self.vision()
        self.cancel.set()
        from h3chat.downloads import Cancelled
        with self.assertRaises(Cancelled):
            self.engine._activate('chat', self.models['llm'], self.settings, self.root/'next.log', self.cancel)
        self.assertTrue(image.ready)
        image.send.assert_not_called()

    def video(self, settings=None, stage=None):
        path=self.root/'video.bin';path.write_bytes(b'video weights')
        model=self.models['image'] | {'id':'video','capabilities':['video'],
            'files':[{'role':'model','path':path.name,'size':path.stat().st_size}]}
        return self.engine._activate('video',model,settings or self.settings,
            self.root/'video.log',self.cancel,stage=stage)

    def test_direct_image_to_video_closes_image_without_warm_unload(self):
        image=self.vision()
        self.video()
        self.assertFalse(image.alive())
        image.send.assert_not_called()
        self.assertIsNone(self.engine.warm_image)
        self.assertGreater(self.engine.cache.snapshot()['mapped_bytes'],0)

    def test_video_releases_image_runtime_already_warmed_during_chat(self):
        image=self.vision()
        self.loaded('chat','llm')
        stage=Mock()
        self.video(stage=stage)
        self.assertFalse(image.alive())
        self.assertIsNone(self.engine.warm_image)
        self.assertFalse(self.engine.snapshot()['warm_image_engine'])
        stage.assert_any_call('Rilascio memoria · motore immagini inattivo prima del video')

    def test_resident_video_keeps_the_requested_image_model(self):
        image=self.vision(self.settings | {'memory_policy':'resident'})
        self.video(self.settings | {'memory_policy':'resident'})
        self.assertTrue(image.alive())
        self.assertTrue(image.ready)
        image.send.assert_not_called()


class WorkerLifecycleTests(unittest.TestCase):
    def test_unload_releases_models_without_reinitializing_libraries(self):
        source = ast.parse((ROOT/'native/vision-worker.py').read_text(encoding='utf-8'))
        definition = next(n for n in source.body if isinstance(n, ast.ClassDef) and n.name == 'Worker')
        events = Mock()
        namespace = {'emit': events}
        exec(compile(ast.Module(body=[definition], type_ignores=[]), '<worker>', 'exec'), namespace)
        worker = namespace['Worker']()
        worker.base_model, worker.base_clip, worker.vae = object(), object(), object()
        manager = Mock()
        worker.comfy = SimpleNamespace(model_management=manager)
        worker.backend = 'cuda'
        worker.torch = object()
        def cleanup():
            self.assertIsNone(worker.base_model)
            self.assertIsNone(worker.base_clip)
            self.assertIsNone(worker.vae)
        manager.cleanup_models.side_effect = cleanup
        worker.unload()
        manager.soft_empty_cache.assert_called_once_with(force=True)
        events.assert_called_once_with('unloaded')
        worker.initialize({'backend':'cuda'})  # Does not import torch again.
        with self.assertRaises(ValueError):worker.initialize({'backend':'cpu'})

    def test_video_windows_offload_and_native_exit_diagnostics(self):
        tree = ast.parse((ROOT/'native/video-worker.py').read_text(encoding='utf-8'))
        definition = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'Worker')
        namespace = {}
        exec(compile(ast.Module(body=[definition], type_ignores=[]), '<video-worker>', 'exec'), namespace)
        worker = namespace['Worker']()
        worker.clip, worker.vae, worker.audio_vae = object(), object(), object()
        manager = Mock()
        worker.comfy = SimpleNamespace(model_management=manager)
        manager.cleanup_models.side_effect = lambda: self.assertIsNone(worker.clip)
        worker.discard('clip', 'vae', 'audio_vae')
        manager.soft_empty_cache.assert_called_once_with(force=True)
        self.assertIsNone(worker.vae)
        self.assertIsNone(worker.audio_vae)
        session = Session((), 'video', {}, {}, {}, Path('unused.log'))
        session.process = Mock()
        for code, message in ((-1073741819,'0xC0000005'),(0xc0000017,'Memoria di sistema insufficiente'),(1,'codice 1')):
            session.process.poll.return_value=code
            self.assertIn(message, session.exit_message())

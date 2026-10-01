import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from bootstrap_bundle import build, verify_sources
spec=importlib.util.spec_from_file_location('clone_install',ROOT/'scripts/install.py')
installer=importlib.util.module_from_spec(spec);spec.loader.exec_module(installer)

class InstallTests(unittest.TestCase):
    def test_repository_bundle_matches_sources_and_shipped_worker(self):
        manifest=json.loads((ROOT/'distribution/windows-bootstrap.json').read_text(encoding='utf-8'))
        verify_sources(ROOT,manifest)
        self.assertEqual(installer.file_hash(ROOT/'distribution/windows-bootstrap.zip'),manifest['sha256'])
        self.assertEqual(installer.file_hash(ROOT/'native/h3-sd-worker.exe'),manifest['files']['native/h3-sd-worker.exe'])

    def fixture(self,root):
        for name in ('ui/app.js','package.json','package-lock.json','scripts/build-ui.mjs','scripts/Launcher.cs','native/sd-worker.cpp',
                     'H3-Chat.exe','native/h3-sd-worker.exe','static/app.js','static/vendor/katex.min.css','data/chat.sqlite','models/user.gguf'):
            p=root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(name,encoding='utf-8')
        build(root)

    def test_clone_bundle_repairs_generated_files_preserves_data_and_is_repeatable(self):
        with tempfile.TemporaryDirectory(prefix='h3 clone ') as tmp:
            root=Path(tmp);self.fixture(root)
            (root/'static/app.js').write_text('old')
            installer.install_bundle(root);mtime=(root/'static/app.js').stat().st_mtime_ns
            installer.install_bundle(root)
            self.assertEqual((root/'static/app.js').stat().st_mtime_ns,mtime)
            self.assertEqual((root/'static/app.js').read_text(),'static/app.js')
            self.assertEqual((root/'data/chat.sqlite').read_text(),'data/chat.sqlite')
            self.assertEqual((root/'models/user.gguf').read_text(),'models/user.gguf')

    def test_stale_or_corrupt_bundle_fails_before_replacing_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);self.fixture(root)
            (root/'ui/app.js').write_text('changed source')
            with self.assertRaisesRegex(ValueError,'allineati'):installer.install_bundle(root)
            self.fixture(root)
            (root/'distribution/windows-bootstrap.zip').write_bytes(b'corrupt')
            with self.assertRaisesRegex(ValueError,'corrotto'):installer.install_bundle(root)
            self.assertEqual((root/'static/app.js').read_text(),'static/app.js')

    def test_verified_runtime_reuses_installation_without_network(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'runtime').mkdir();p=root/'runtime/test.dll';p.write_bytes(b'valid')
            manifest={'files':[{'path':'unused.zip'}]}
            (root/'runtimes.json').write_text(json.dumps({'cpu':manifest}))
            (root/'runtime/installed-cpu.json').write_text(json.dumps({'manifest':manifest,'files':{'runtime/test.dll':installer.file_hash(p)}}))
            with patch.object(installer,'download') as download:installer.install_runtime('cpu',root)
            download.assert_not_called()


class NativeRuntimeTests(unittest.TestCase):
    def test_crt_is_local_verified_repeatable_and_restored_after_damage(self):
        from h3chat.native_runtime import install_redist
        import hashlib
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);source=root/'native/redist';source.mkdir(parents=True)
            (source/'vcruntime140.dll').write_bytes(b'signed-fixture')
            (source/'SOURCES.json').write_text(json.dumps({'files':{'vcruntime140.dll':hashlib.sha256(b'signed-fixture').hexdigest()}}))
            for backend in ('cpu','cuda','vulkan'):
                for engine in ('llama','sd'):
                    dest=root/'runtime'/backend/engine
                    paths=install_redist(root,dest);self.assertEqual(paths,[(dest/'vcruntime140.dll').resolve()])
                    timestamp=paths[0].stat().st_mtime_ns
                    install_redist(root,dest);self.assertEqual(paths[0].stat().st_mtime_ns,timestamp)
                    paths[0].write_bytes(b'broken');install_redist(root,dest)
                    self.assertEqual(paths[0].read_bytes(),b'signed-fixture')
            for kind in ('documents','asr','lab'):
                dest=root/'runtime/tools'/kind;self.assertEqual(len(install_redist(root,dest)),1);self.assertEqual((dest/'vcruntime140.dll').read_bytes(),b'signed-fixture')
            self.assertEqual(install_redist(root,root/'runtime/vision'),[])
            (source/'vcruntime140.dll').write_bytes(b'tampered')
            with self.assertRaisesRegex(ValueError,'danneggiata'):install_redist(root,root/'runtime/cpu/sd')

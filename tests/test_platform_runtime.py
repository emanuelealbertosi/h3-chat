import sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from h3chat.platform_runtime import python_executable,info,require_local_model
from h3chat.providers import protect
from h3chat.installation_profile import first_run_settings


class PlatformTests(unittest.TestCase):
    def test_macos_worker_paths_capabilities_and_safe_first_run(self):
        with tempfile.TemporaryDirectory() as folder,patch('sys.platform','darwin'):
            root=Path(folder)
            self.assertEqual(python_executable(root),root/'runtime/python/bin/python3')
            self.assertEqual(info()['backends'],['cpu','metal'])
            self.assertTrue(info()['local_code_execution'])
            self.assertEqual(first_run_settings(root,True),{})
            self.assertEqual(first_run_settings(root,False)['backend'],'metal')
            for model in ({'api':True},{'remote_media':True},{'capabilities':['chat']}):require_local_model(model)
            with self.assertRaisesRegex(ValueError,'macOS'):require_local_model({'capabilities':['video']})

    def test_macos_protect_uses_keychain_without_replacing_windows_dpapi(self):
        with patch('sys.platform','darwin'),patch('h3chat.macos_keychain.protect',return_value='keychain:test') as native:
            self.assertEqual(protect('test-only-key'),'keychain:test')
            native.assert_called_once_with('test-only-key',False)
        self.assertEqual(protect(''),'')

    def test_windows_path_remains_unchanged(self):
        with patch('sys.platform','win32'):
            self.assertEqual(python_executable(Path('root')),Path('root/runtime/python/python.exe'))
            self.assertEqual(info()['backends'],['cpu','vulkan','cuda'])

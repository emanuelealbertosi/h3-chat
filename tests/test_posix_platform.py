import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from h3chat.platform_runtime import python_executable,info
from h3chat.installation_profile import first_run_settings
from h3chat.providers import protect
from h3chat.linux_runtime import manifests


class PosixTests(unittest.TestCase):
    def test_linux_has_native_python_cpu_first_run_and_no_windows_downloads(self):
        with tempfile.TemporaryDirectory() as temporary,patch('sys.platform','linux'):
            root=Path(temporary)
            self.assertEqual(python_executable(root),root/'runtime/python/bin/python3')
            self.assertEqual(info()['backends'],['cpu','vulkan','cuda'])
            self.assertEqual(first_run_settings(root,False)['gpu_layers'],0)
            self.assertEqual(first_run_settings(root,True),{})
            (root/'runtimes.json').write_text(json.dumps({'cuda':{'platform':'linux','files':[]},'windows':{'files':[{'url':'windows.dll'}]}}))
            self.assertEqual(set(manifests(root)),{'cuda'})

    def test_linux_api_key_is_a_reference_and_requires_its_secret_service(self):
        items={}
        class Collection:
            def is_locked(self):return False
            def create_item(self,label,attributes,value,**kwargs):items[attributes['id']]=value
            def search_items(self,attributes):
                raw=items.get(attributes['id'])
                return [] if raw is None else [SimpleNamespace(get_secret=lambda:raw)]
        backend=SimpleNamespace(dbus_init=lambda:SimpleNamespace(close=lambda:None),get_default_collection=lambda bus:Collection())
        with patch('sys.platform','linux'),patch.dict(sys.modules,{'secretstorage':backend}):
            reference=protect('TEST-ONLY-SECRET')
            self.assertTrue(reference.startswith('secretservice:'))
            self.assertNotIn('TEST-ONLY-SECRET',reference)
            self.assertEqual(protect(reference,True),'TEST-ONLY-SECRET')
            with self.assertRaisesRegex(ValueError,'altro sistema'):protect('windows-dpapi-ciphertext',True)
            items.clear()
            with self.assertRaisesRegex(ValueError,'non presente'):protect(reference,True)

if __name__=='__main__':unittest.main()

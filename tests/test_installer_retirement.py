import importlib.util,tempfile,unittest
from pathlib import Path
spec=importlib.util.spec_from_file_location('installer_retire',Path(__file__).resolve().parents[1]/'scripts/install.py');installer=importlib.util.module_from_spec(spec);spec.loader.exec_module(installer)

class RetirementTests(unittest.TestCase):
    def test_verified_obsolete_binaries_are_backed_up_without_touching_user_files(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);engine=root/'runtime/cpu/llama';engine.mkdir(parents=True);old=engine/'old-backend.dll';old.write_bytes(b'old');keep=engine/'server.exe';keep.write_bytes(b'new');user=root/'data/source.dll';user.parent.mkdir();user.write_bytes(b'private')
            files={str(p.relative_to(root)).replace('\\','/'):installer.file_hash(p) for p in (old,keep,user)};retired=installer.retire_obsolete(root,{'files':files},{'runtime/cpu/llama/server.exe':'hash'},[engine],'cpu')
            self.assertEqual(retired,['runtime/cpu/llama/old-backend.dll']);self.assertFalse(old.exists());self.assertTrue(keep.exists());self.assertEqual(user.read_bytes(),b'private');self.assertEqual(next((root/'runtime/retired').rglob('old-backend.dll')).read_bytes(),b'old')
    def test_modified_old_binary_and_traversal_are_not_moved(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);engine=root/'runtime/cpu/llama';engine.mkdir(parents=True);old=engine/'old.dll';old.write_bytes(b'custom')
            with self.assertRaisesRegex(ValueError,'modificato'):installer.retire_obsolete(root,{'files':{'runtime/cpu/llama/old.dll':'0'*64}},{},[engine],'cpu')
            self.assertTrue(old.exists())
            with self.assertRaises(ValueError):installer.retire_obsolete(root,{'files':{'../outside.dll':'0'*64}},{},[engine],'cpu')

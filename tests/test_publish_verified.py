import tempfile
from pathlib import Path
import unittest
from scripts.publish_verified import safe_name, verify_packages, asset_inventory


class PublicationValidators(unittest.TestCase):
    def test_safe_paths(self):
        safe_name('h3chat/agent_runtime.py')
        for path in ('../key', '/etc/passwd', 'data/chat.sqlite', 'models/x.gguf',
                     'work/test', 'docs/h3-session-state.json', 'C:/private', 'a\\b'):
            with self.subTest(path=path), self.assertRaises(ValueError):
                safe_name(path)

    def test_missing_archive_never_passes(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaisesRegex(ValueError, 'Missing archive'):
                verify_packages(folder)

    def test_asset_inventory_requires_all_nine_and_sizes(self):
        with tempfile.TemporaryDirectory() as folder:
            files = []
            for i in range(9):
                path = Path(folder) / str(i)
                path.write_bytes(b'test')
                files.append(path)
            assets = [{'name': p.name, 'size': 4, 'state': 'uploaded'} for p in files]
            asset_inventory({'assets': assets}, files)
            for wrong in (assets[:-1], assets + assets[:1], assets[:-1] +
                          [{'name': '8', 'size': 0, 'state': 'uploaded'}], assets[:-1] +
                          [{'name': '8', 'size': 4, 'state': 'new'}]):
                with self.assertRaises(ValueError):
                    asset_inventory({'assets': wrong}, files)

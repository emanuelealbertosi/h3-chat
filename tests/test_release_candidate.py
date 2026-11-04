import importlib.util
import json
from pathlib import Path
import unittest

from h3chat import __version__

ROOT=Path(__file__).resolve().parents[1]


class CandidateTests(unittest.TestCase):
    def test_application_ui_and_lock_versions_match(self):
        package=json.loads((ROOT/'package.json').read_text(encoding='utf8'))
        lock=json.loads((ROOT/'package-lock.json').read_text(encoding='utf8'))
        self.assertEqual(package['version'],__version__)
        self.assertEqual(lock['version'],__version__)
        self.assertEqual(lock['packages']['']['version'],__version__)
        self.assertTrue((ROOT/f'docs/release-{__version__}.md').is_file())

    def test_macos_bundle_versions_remain_numeric_for_release_candidates(self):
        spec=importlib.util.spec_from_file_location('candidate_macos_build',ROOT/'scripts/build_macos.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        self.assertEqual(module.bundle_versions('1.0.0-rc.1'),('1.0.0','1.0.0'))
        self.assertEqual(module.bundle_versions('1.0.0'),('1.0.0','1.0.0'))
        for invalid in ('1.0','1.0.0/rc','', '1.0.0-'):
            with self.subTest(version=invalid),self.assertRaises(ValueError):module.bundle_versions(invalid)

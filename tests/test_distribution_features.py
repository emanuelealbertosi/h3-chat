"""Ensure the common archive gate covers the actual portable feature source."""
from pathlib import Path
import unittest
from scripts.verify_feature_files import REQUIRED,POSTER_FILES,STUDIO_FILES,FONT_FILES,verify_members
from scripts.package import collect_files

ROOT=Path(__file__).resolve().parents[1]

class DistributionFeatureTests(unittest.TestCase):
    def test_common_archive_gate_checks_relative_or_packaged_members(self):
        expected=verify_members(REQUIRED)
        self.assertEqual(verify_members('H3-Chat/'+name for name in REQUIRED),expected)
        self.assertEqual(expected['poster_files'],len(POSTER_FILES));self.assertEqual(expected['studio_files'],len(STUDIO_FILES));self.assertEqual(expected['font_and_license_files'],len(FONT_FILES))
    def test_missing_new_module_font_or_license_blocks_release(self):
        for name in ('h3chat/poster_overlay.py','h3chat/study_import.py','static/Baloo2.ttf','static/font-licenses/bangers/OFL.txt'):
            with self.subTest(name=name),self.assertRaisesRegex(ValueError,name.replace('.','\\.')):verify_members(REQUIRED-{name})
    def test_current_feature_sources_and_licenses_are_in_portable_windows_allowlist(self):
        included={p.relative_to(ROOT).as_posix() for p in collect_files(ROOT)}
        self.assertEqual(REQUIRED-included,set())
        for name in REQUIRED:self.assertTrue((ROOT/name).is_file(),name)

if __name__=='__main__':unittest.main()

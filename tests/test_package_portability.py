"""Portable package selection and skill discovery; no real runtime or account."""
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]


def module(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    value=importlib.util.module_from_spec(spec);spec.loader.exec_module(value)
    return value


package=module('portable_package_test',ROOT/'scripts/package.py')
roots=module('portable_skill_root_test',ROOT/'skills/h3/scripts/h3_root.py')


class PackageTests(unittest.TestCase):
    def test_package_includes_api_launchers_and_skill_but_excludes_local_state(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            included=('docs/slides.md','Avvia-server-immagini.bat','Installa-API-senza-GPU.bat',
                      'scripts/start-image-server.py','scripts/image-api-server.py','scripts/download-moss-bf16.py',
                      'skills/h3/SKILL.md','skills/h3/scripts/h3_root.py','skills/h3/scripts/status.py',
                      'native/h3-sd-worker.exe','runtime/cpu/llama/llama-server.exe')
            excluded=('docs/h3-session-state.json','docs/video-roadmap.md','docs/notes.bak',
                      'docs/old.tmp','docs/debug.log','docs/private.sqlite','docs/.git/config',
                      'skills/h3/scripts/__pycache__/status.pyc','data/chat.sqlite','models/private.gguf',
                      'runtime/installation-profile.json')
            for relative in (*included,*excluded):
                path=root/relative;path.parent.mkdir(parents=True,exist_ok=True);path.write_text('synthetic',encoding='utf-8')
            actual={p.relative_to(root).as_posix() for p in package.collect_files(root)}
            self.assertEqual(actual,set(included))

    def test_paths_outside_package_root_are_excluded(self):
        with tempfile.TemporaryDirectory() as folder:
            base=Path(folder);root=base/'release';(root/'docs').mkdir(parents=True)
            source=base/'private.txt';source.write_text('private',encoding='utf-8')
            try:(root/'docs/linked.md').symlink_to(source)
            except OSError:self.skipTest('The platform does not permit test symlinks.')
            self.assertEqual(package.collect_files(root),[])

    def test_source_skill_contains_no_personal_drive_or_old_run_path(self):
        for path in (ROOT/'skills/h3').rglob('*'):
            if path.suffix not in ('.py','.md','.yaml'):continue
            content=path.read_text(encoding='utf-8')
            self.assertIsNone(re.search(r'\b[A-Z]:[/\\]',content),str(path))
            self.assertNotIn('2026-10-23',content,str(path))
            self.assertNotIn('work/direct-video-',content,str(path))


class SkillRootTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.base=Path(self.temp.name)
        self.env=patch.dict(os.environ,{},clear=True);self.env.start();self.addCleanup(self.env.stop)

    def installation(self,name):
        root=self.base/name;(root/'h3chat').mkdir(parents=True)
        (root/'app.py').touch();(root/'catalog.json').write_text('{}',encoding='utf-8')
        return root.resolve()

    def test_explicit_root_precedes_environment_and_bundled_location(self):
        wanted=self.installation('wanted');other=self.installation('other')
        os.environ['H3_CHAT_ROOT']=str(other)
        with patch.object(roots,'__file__',str(other/'skills/h3/scripts/h3_root.py')):
            self.assertEqual(roots.find_root(wanted),wanted)

    def test_environment_root_is_used_without_assuming_a_drive(self):
        root=self.installation('cartella con spazi');os.environ['H3_CHAT_ROOT']=str(root)
        self.assertEqual(roots.find_root(),root)

    def test_bundled_skill_finds_its_own_installation(self):
        root=self.installation('portable')
        with patch.object(roots,'__file__',str(root/'skills/h3/scripts/h3_root.py')),patch('os.getcwd',return_value=str(self.base)):
            self.assertEqual(roots.find_root(),root)

    def test_installed_skill_uses_current_project_ancestor(self):
        root=self.installation('project');cwd=root/'work/test';cwd.mkdir(parents=True)
        with patch.object(roots,'__file__',str(self.base/'user-skills/h3/scripts/h3_root.py')),patch('os.getcwd',return_value=str(cwd)):
            self.assertEqual(roots.find_root(),root)

    def test_invalid_explicit_or_environment_root_does_not_fall_back(self):
        root=self.installation('portable')
        with patch.object(roots,'__file__',str(root/'skills/h3/scripts/h3_root.py')):
            with self.assertRaises(ValueError):roots.find_root(self.base/'missing')
            os.environ['H3_CHAT_ROOT']=str(self.base/'missing')
            with self.assertRaises(ValueError):roots.find_root()

    def test_missing_installation_has_actionable_error(self):
        with patch.object(roots,'__file__',str(self.base/'user-skills/h3/scripts/h3_root.py')),patch('os.getcwd',return_value=str(self.base)):
            with self.assertRaisesRegex(ValueError,'H3_CHAT_ROOT'):roots.find_root()

    def test_status_cli_works_outside_checkout_without_creating_data(self):
        root=self.installation('portable')
        process=subprocess.run([sys.executable,'-B',str(ROOT/'skills/h3/scripts/status.py'),'--root',str(root)],
                               cwd=self.base,capture_output=True,text=True,check=True)
        value=json.loads(process.stdout)
        self.assertEqual(Path(value['root']),root)
        self.assertFalse(value['server']['available'])
        self.assertFalse((root/'data').exists())


if __name__=='__main__':unittest.main()

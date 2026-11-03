import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch
from scripts.publish_verified import safe_name, verify_packages, asset_inventory, provenance
from scripts import publish_verified as publication


class PublicationValidators(unittest.TestCase):
    def publication_fixture(self, *, missing_gate=False, unrelated_failure=False,
                            wrong_kali_revision=False, application_change=False):
        def git(*args):
            if args == ('rev-parse', 'HEAD'): return 'fixture-head'
            if args[0] == 'diff':
                if application_change: return 'h3chat/service.py'
                if args[-1] == 'HEAD': return 'scripts/publish_verified.py'
                return '\n'.join(sorted(publication.ENVIRONMENT_CHANGES))
            raise AssertionError(args)
        def api(path):
            run = int(path.split('/')[2]); kali = run == 41646238896
            revision = publication.KALI_BASE if kali else publication.BASE
            if wrong_kali_revision and kali: revision = 'unverified-revision'
            if '/jobs?' not in path:
                return {'head_repository': {'full_name': publication.REPO}, 'status': 'completed',
                        'conclusion': 'success' if kali else 'failure', 'head_sha': revision}
            jobs = [{'id': key, 'name': name, 'conclusion': 'success', 'head_sha': revision}
                    for key, name in publication.JOBS[run].items()]
            if missing_gate and kali: jobs[0]['conclusion'] = 'skipped'
            if not kali: jobs.append({'id': 1, 'name': 'linux / kali', 'conclusion': 'failure'})
            if unrelated_failure: jobs.append({'id': 2, 'name': 'unexpected gate', 'conclusion': 'failure'})
            return {'jobs': jobs}
        with patch.dict('os.environ', {'GITHUB_EVENT_NAME': 'workflow_dispatch',
              'GITHUB_REPOSITORY': publication.REPO, 'GITHUB_SHA': 'fixture-head'}), \
              patch.object(publication, 'git', side_effect=git), \
              patch.object(publication, 'api', side_effect=api), \
              patch.object(publication.subprocess, 'run'):
            provenance()

    def test_exact_archive_and_environment_only_retest_allowed(self):
        self.publication_fixture()

    def test_unverified_source_or_gate_cannot_publish(self):
        for options in ({'missing_gate': True}, {'unrelated_failure': True},
                        {'wrong_kali_revision': True}, {'application_change': True}):
            with self.subTest(options=options), self.assertRaises(ValueError):
                self.publication_fixture(**options)

    def test_automatic_events_cannot_publish(self):
        for event in ('push', 'pull_request', 'schedule', 'workflow_run'):
            with self.subTest(event=event), patch.dict('os.environ', {'GITHUB_EVENT_NAME': event}), self.assertRaisesRegex(ValueError, 'Manual dispatch'):
                provenance()

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

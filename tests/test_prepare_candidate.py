from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts import prepare_candidate as candidate

class CandidateGates(unittest.TestCase):
    def fixture(self,*,failed=False,missing=False,foreign=False,changed='scripts/prepare_candidate.py'):
        def git(*args):
            if args==('rev-parse','HEAD'):return 'candidate-sha'
            if args[0]=='diff':return changed
            raise AssertionError(args)
        def api(path):
            if '/jobs?' in path:
                names=candidate.GATES-({'linux / kali'} if missing else set())
                return {'jobs':[{'name':n,'conclusion':'success','head_sha':'build-sha'} for n in names]}
            return {'head_repository':{'full_name':'other/repo' if foreign else candidate.REPO},'status':'completed','conclusion':'failure' if failed else 'success','head_sha':'build-sha'}
        with patch.dict('os.environ',{'GITHUB_EVENT_NAME':'workflow_dispatch','GITHUB_REPOSITORY':candidate.REPO,'GITHUB_SHA':'candidate-sha'}),patch.object(candidate,'api',side_effect=api),patch.object(candidate,'git',side_effect=git),patch.object(candidate.subprocess,'run'):
            return candidate.provenance('123')

    def test_exact_successful_build_allows_only_draft_preparation_code_changes(self):
        self.assertEqual(self.fixture()['build_sha'],'build-sha')
        for args in ({'failed':True},{'missing':True},{'foreign':True},{'changed':'h3chat/service.py'}):
            with self.subTest(args=args),self.assertRaises(ValueError):self.fixture(**args)

    def test_stable_versions_cannot_be_prepared_by_candidate_helper(self):
        for value in ('1.0.0','0.19.2','v1.0.0-rc.1','1.0.0-rc.1/other'):
            with self.assertRaises(ValueError):candidate.candidate_version(value)
        self.assertEqual(candidate.candidate_version('1.0.0-rc.1'),'1.0.0-rc.1')

    def test_incomplete_inputs_fail_before_release_creation(self):
        with tempfile.TemporaryDirectory() as folder,patch.object(candidate,'provenance'),patch.object(candidate.subprocess,'run') as run:
            with self.assertRaisesRegex(ValueError,'Missing'):candidate.prepare('123',folder)
            run.assert_not_called()

    def test_published_release_wrong_tag_or_missing_assets_cannot_be_accepted(self):
        with tempfile.TemporaryDirectory() as folder:
            files=[]
            for i in range(9):
                p=Path(folder)/str(i);p.write_bytes(b'test');files.append(p)
            base={'draft':True,'prerelease':True,'tag_name':'v'+candidate.__version__,'assets':[{'name':p.name,'size':4,'state':'uploaded'} for p in files]}
            candidate.check_inventory(base,files)
            for change in ({'draft':False},{'prerelease':False},{'tag_name':'v1.0.0'},{'assets':base['assets'][:-1]}):
                with self.assertRaises(ValueError):candidate.check_inventory(base|change,files)

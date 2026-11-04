from pathlib import Path
import hashlib
import io
import json
import tarfile
import tempfile
import unittest
import zipfile
from unittest.mock import patch

from scripts import prepare_candidate as candidate

class CandidateGates(unittest.TestCase):
    def packages(self,folder):
        version=(candidate.ROOT/'h3chat/__init__.py').read_bytes().replace(b'\r\n',b'\n')
        reports={}
        for platform,arch,extension in (('windows','x64','zip'),('macos','arm64','zip'),('linux','x64','tar.gz')):
            stem=f'H3-Chat-{candidate.__version__}-{platform}-{arch}';base=Path(folder)/platform;base.mkdir()
            path=base/(stem+'.'+extension)
            if extension=='zip':
                with zipfile.ZipFile(path,'w') as z:z.writestr('H3-Chat/h3chat/__init__.py',version.replace(b'\n',b'\r\n') if platform=='windows' else version)
            else:
                with tarfile.open(path,'w:gz') as tar:
                    info=tarfile.TarInfo('H3-Chat/h3chat/__init__.py');info.size=len(version);tar.addfile(info,io.BytesIO(version))
            digest=hashlib.sha256(path.read_bytes()).hexdigest()
            path.with_name(path.name+'.sha256').write_text(digest+'  '+path.name+'\n')
            reports[platform]={'status':'passed','archive':path.name,'sha256':digest,'size':path.stat().st_size,'verified_files':1}
            path.with_name(stem+'.verification.json').write_text(json.dumps(reports[platform]))
        return reports

    def test_nine_files_checksums_reports_and_cross_platform_version_encodings(self):
        with tempfile.TemporaryDirectory() as folder:
            reports=self.packages(folder)
            # Archive internals use the separately tested ZIP and Linux verifiers.
            with patch.object(candidate,'verify_zip',return_value=1),patch.object(candidate,'verify_linux',return_value=reports['linux']):
                files,proof=candidate.verify_packages(folder)
                self.assertEqual(len(files),9);self.assertEqual(set(proof),{'windows','macos','linux'})
                unexpected=Path(folder)/'extra.txt';unexpected.write_text('not a release file')
                with self.assertRaisesRegex(ValueError,'nine'):candidate.verify_packages(folder)
                unexpected.unlink()
                checksum=next((Path(folder)/'windows').glob('*.sha256'));checksum.write_text('0'*64+' wrong.zip')
                with self.assertRaisesRegex(ValueError,'checksum'):candidate.verify_packages(folder)

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

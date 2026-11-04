"""Prepare a draft RC from one successful build. Never publish or update main."""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tarfile
import urllib.error
import urllib.request
import zipfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from h3chat import __version__
from scripts.publish_verified import verify_zip
from scripts.verify_linux_package import verify as verify_linux

REPO='emanuelealbertosi/h3-chat'
GATES={'windows','macos / macos','linux / cpu','linux / package','linux / kali'}
ADMIN_CHANGES={'.github/workflows/publish-verified.yml','scripts/prepare_candidate.py','tests/test_prepare_candidate.py'}

def require(ok,message):
    if not ok:raise ValueError(message)

def git(*args):
    return subprocess.check_output(['git',*args],cwd=ROOT,text=True).strip()

def api(path):
    request=urllib.request.Request('https://api.github.com/repos/'+REPO+'/'+path,
        headers={'Authorization':'Bearer '+os.environ['GH_TOKEN'],'Accept':'application/vnd.github+json'})
    with urllib.request.urlopen(request,timeout=90) as response:return json.load(response)

def candidate_version(version):
    require(bool(re.fullmatch(r'\d+\.\d+\.\d+-rc\.\d+',version)),'This helper only prepares release candidates.')
    return version

def provenance(run_id):
    candidate_version(__version__)
    require(str(run_id).isdecimal(),'Build run ID must be numeric.')
    require(os.environ.get('GITHUB_EVENT_NAME')=='workflow_dispatch','Manual dispatch required.')
    require(os.environ.get('GITHUB_REPOSITORY')==REPO,'Unexpected repository.')
    require(git('rev-parse','HEAD')==os.environ.get('GITHUB_SHA'),'Checkout revision mismatch.')
    run=api('actions/runs/'+str(run_id))
    require(run.get('head_repository',{}).get('full_name')==REPO,'Build belongs to another repository.')
    require(run.get('status')=='completed' and run.get('conclusion')=='success','Build has not passed.')
    revision=run['head_sha']
    subprocess.run(['git','fetch','origin',revision],cwd=ROOT,check=True)
    changed=set(git('diff','--name-only',revision,'HEAD').splitlines())
    require(not changed-ADMIN_CHANGES,'Application differs from tested build: '+str(sorted(changed-ADMIN_CHANGES)))
    jobs=api('actions/runs/'+str(run_id)+'/jobs?per_page=100')['jobs']
    passed={j['name'] for j in jobs if j.get('conclusion')=='success' and j.get('head_sha')==revision}
    require(GATES<=passed,'Missing successful platform checks: '+str(sorted(GATES-passed)))
    return {'run_id':int(run_id),'build_sha':revision,'candidate_sha':git('rev-parse','HEAD'),'version':__version__,'gates':sorted(GATES)}

def verify_packages(folder):
    folder=Path(folder);expected=set();proof={}
    for platform,arch,extension in (('windows','x64','zip'),('macos','arm64','zip'),('linux','x64','tar.gz')):
        stem=f'H3-Chat-{candidate_version(__version__)}-{platform}-{arch}'
        archive=folder/platform/(stem+'.'+extension)
        checksum=archive.with_name(archive.name+'.sha256');report_path=archive.with_name(stem+'.verification.json')
        expected.update((archive,checksum,report_path))
        require(all(p.is_file() and not p.is_symlink() for p in (archive,checksum,report_path)),'Missing regular package files: '+platform)
        with archive.open('rb') as stream:digest=hashlib.file_digest(stream,'sha256').hexdigest()
        require(checksum.read_text().split()==[digest,archive.name],'Archive checksum mismatch: '+platform)
        report=json.loads(report_path.read_text())
        require(report.get('status')=='passed' and report.get('archive')==archive.name and report.get('sha256')==digest and report.get('size')==archive.stat().st_size,'Invalid verification report: '+platform)
        if extension=='zip':
            require(verify_zip(archive)==report.get('verified_files'),'ZIP member count differs: '+platform)
            with zipfile.ZipFile(archive) as package:
                require(package.read('H3-Chat/h3chat/__init__.py').replace(b'\r\n',b'\n')==(ROOT/'h3chat/__init__.py').read_bytes().replace(b'\r\n',b'\n'),'Packaged version differs: '+platform)
        else:
            require(verify_linux(archive)==report,'Linux package report differs.')
            with tarfile.open(archive,'r|gz') as package:
                for member in package:
                    if member.name=='H3-Chat/h3chat/__init__.py':
                        require(package.extractfile(member).read().replace(b'\r\n',b'\n')==(ROOT/'h3chat/__init__.py').read_bytes().replace(b'\r\n',b'\n'),'Packaged Linux version differs.');break
                else:raise ValueError('Packaged Linux version missing.')
        proof[platform]=report
    actual={p for p in folder.rglob('*') if p.is_file() or p.is_symlink()}
    require(actual==expected and len(actual)==9,'Exactly nine verified files are required.')
    return sorted(expected),proof

def check_inventory(release,files):
    require(release.get('draft') is True and release.get('prerelease') is True,'Expected an unpublished release-candidate draft.')
    require(release.get('tag_name')=='v'+candidate_version(__version__),'Wrong candidate tag.')
    expected={p.name:p.stat().st_size for p in files}
    assets=release.get('assets',[])
    require(len(assets)==9 and {a['name']:a['size'] for a in assets}==expected and all(a.get('state')=='uploaded' for a in assets),'Incomplete or different candidate attachments.')

def prepare(run_id,folder):
    record=provenance(run_id);files,reports=verify_packages(folder);tag='v'+__version__
    try:api('releases/tags/'+tag)
    except urllib.error.HTTPError as exc:
        if exc.code!=404:raise
    else:raise ValueError('Candidate already exists: inspect it instead of overwriting or duplicating.')
    require(not git('ls-remote','--tags','origin','refs/tags/'+tag),'Candidate tag already exists.')
    # Every member is verified before making the draft; main and stable releases are untouched.
    subprocess.run(['gh','release','create',tag,*map(str,files),'--repo',REPO,
        '--target',record['candidate_sha'],'--draft','--prerelease','--latest=false',
        '--title','H3-Chat '+__version__,'--notes-file',str(ROOT/f'docs/release-{__version__}.md')],check=True)
    release=api('releases/tags/'+tag);check_inventory(release,files)
    record.update(status='draft_ready',url=release['html_url'],release_id=release['id'],assets=[p.name for p in files],reports=reports,stable_release_changed=False)
    output=ROOT/'build/candidate-proof.json';output.parent.mkdir(exist_ok=True);output.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    if os.environ.get('GITHUB_STEP_SUMMARY'):
        with open(os.environ['GITHUB_STEP_SUMMARY'],'a',encoding='utf8') as stream:stream.write(f'RC draft ready: [{tag}]({record["url"]}) — nine verified attachments. Stable release unchanged.\n')
    print(json.dumps(record,ensure_ascii=False,indent=2))

if __name__=='__main__':
    if len(sys.argv)==3 and sys.argv[1]=='provenance':print(json.dumps(provenance(sys.argv[2])))
    elif len(sys.argv)==4 and sys.argv[1]=='prepare':prepare(sys.argv[2],sys.argv[3])
    else:raise SystemExit('Usage: prepare_candidate.py provenance RUN | prepare RUN FOLDER')

"""One explicitly authorized, manual publication; no forced updates or overwrites."""
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import subprocess
import sys
import urllib.error
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
VERSION = '0.19.2'
REPO = 'emanuelealbertosi/h3-chat'
BASE = 'fcd4612097f2857a258b4dfd9b0c1d29973ceecb'
KALI_BASE = 'b3d77ee649fd33ddb55fa60dbd0a3b3f83a89504'
ENVIRONMENT_CHANGES = {'scripts/check_kali_rootfs.sh', 'scripts/verify_linux_package_reuse.py'}
JOBS = {41624230410: {125947756118: 'windows', 125947824758: 'macos / macos',
                      125947758758: 'linux / cpu', 125947759582: 'linux / package'},
        41646238896: {125952211859: 'kali'}}
PACKAGES = {
    'windows': ('zip', 136356712, '1984d22c56892f491b1e8ac3122654782c5999f1073100166c4598fb62d743d1'),
    'macos': ('zip', 681352226, '166fd9c66145d36cb6ed276c808d350bb7da7fb8607459dd4f2ded4c1ac41f25'),
    'linux': ('tar.gz', 1834954097, 'db1c3d65c62ad1bc965f0f89d68e4fa7287c7d08704f747d4a659d0592bd9741'),
}
ALLOWED_CHANGES = {
    '.github/workflows/publish-verified.yml', '.github/workflows/release.yml',
    'scripts/publish_verified.py',
    'tests/test_publish_verified.py',
} | ENVIRONMENT_CHANGES


def require(condition, message):
    if not condition:
        raise ValueError(message)


def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT, text=True).strip()


def api(path, method='GET', body=None):
    raw = None if body is None else json.dumps(body).encode()
    request = urllib.request.Request('https://api.github.com/repos/' + REPO + '/' + path,
        data=raw, method=method, headers={'Authorization': 'Bearer ' + os.environ['GH_TOKEN'],
        'Accept': 'application/vnd.github+json', 'Content-Type': 'application/json',
        'X-GitHub-Api-Version': '2022-11-28'})
    with urllib.request.urlopen(request, timeout=90) as response:
        return json.load(response)


def provenance():
    require(os.environ.get('GITHUB_EVENT_NAME') == 'workflow_dispatch', 'Manual dispatch required.')
    require(os.environ.get('GITHUB_REPOSITORY') == REPO, 'Unexpected repository.')
    require(git('rev-parse', 'HEAD') == os.environ['GITHUB_SHA'], 'Checkout revision mismatch.')
    subprocess.run(['git', 'fetch', 'origin', BASE], cwd=ROOT, check=True)
    changed = set(git('diff', '--name-only', BASE, 'HEAD').splitlines())
    require(not changed - ALLOWED_CHANGES, 'Unverified source changes: ' + str(sorted(changed - ALLOWED_CHANGES)))
    subprocess.run(['git', 'fetch', 'origin', KALI_BASE], cwd=ROOT, check=True)
    environment_changes = set(git('diff', '--name-only', BASE, KALI_BASE).splitlines())
    require(environment_changes == ENVIRONMENT_CHANGES, 'Kali retest changed application or installer sources.')
    for run_id, expected in JOBS.items():
        run = api(f'actions/runs/{run_id}')
        require(run['head_repository']['full_name'] == REPO and run['status'] == 'completed',
                f'Run {run_id} is incomplete or belongs to another repository.')
        revision = KALI_BASE if run_id == 41646238896 else BASE
        require(run['head_sha'] == revision, f'Run {run_id} used another revision.')
        jobs = {j['id']: j for j in api(f'actions/runs/{run_id}/jobs?per_page=100')['jobs']}
        if run_id == 41624230410:
            # Only the old Kali environment failed (external mirror 500/404).
            # Its replacement below passed against the exact original archive.
            failed = {j['name'] for j in jobs.values() if j['conclusion'] == 'failure'}
            require(run['conclusion'] == 'failure' and failed == {'linux / kali'}, 'Unexpected original build failure.')
        else:
            require(run['conclusion'] == 'success', 'The native Kali retest did not pass.')
        for job_id, name in expected.items():
            job = jobs.get(job_id, {})
            require(job.get('name') == name and job.get('conclusion') == 'success'
                    and job.get('head_sha') == revision,
                    f'Required job {job_id} ({name}) did not pass.')
    print('Pinned Windows, Mac, Ubuntu, package and Kali jobs passed; application sources unchanged.', flush=True)


def safe_name(name):
    parts = PurePosixPath(name).parts
    require(bool(parts) and not PurePosixPath(name).is_absolute() and '..' not in parts
            and '\\' not in name and ':' not in name, 'Unsafe package path: ' + name)
    require(parts[0] not in ('data', 'models', 'work') and name not in
            ('docs/h3-session-state.json', 'docs/video-roadmap.md'), 'Private package path: ' + name)


def verify_zip(path):
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        require(len(names) == len(set(names)), 'Duplicate ZIP members.')
        manifest = json.loads(archive.read('H3-Chat/FILES-SHA256.json'))
        require(set(names) == {'H3-Chat/' + n for n in manifest} | {'H3-Chat/FILES-SHA256.json'},
                'ZIP payload does not match manifest.')
        for name, digest in manifest.items():
            safe_name(name)
            with archive.open('H3-Chat/' + name) as stream:
                require(hashlib.file_digest(stream, 'sha256').hexdigest() == digest,
                        'Invalid ZIP member hash: ' + name)
        from scripts.verify_feature_files import REQUIRED
        for name in REQUIRED | set(('app.py', 'h3chat/__init__.py', 'h3chat/agent_runtime.py',
                     'h3chat/agent_planning.py', 'h3chat/image_options.py',
                     'h3chat/infographic_scene.py', 'h3chat/infographic_storyboard.py',
                     'h3chat/motion_sprites.py', 'h3chat/posters.py', 'h3chat/downloads.py',
                     'static/infographic-scene.js', 'static/infographic-motion.js',
                     'native/infographic-worker.py', 'ui/posters.js', 'runtimes.json')):
            require(archive.read('H3-Chat/' + name).replace(b'\r\n', b'\n') ==
                    (ROOT / name).read_bytes().replace(b'\r\n', b'\n'), 'Packaged source differs: ' + name)
    return len(manifest)


def verify_packages(folder):
    folder = Path(folder)
    files = [p for p in folder.rglob('*') if p.is_file()]
    expected = set()
    archives = []
    for platform, (extension, size, digest) in PACKAGES.items():
        arch = 'arm64' if platform == 'macos' else 'x64'
        stem = f'H3-Chat-{VERSION}-{platform}-{arch}'
        path = folder / platform / (stem + '.' + extension)
        report_path = path.with_name(stem + '.verification.json')
        checksum_path = path.with_name(path.name + '.sha256')
        expected.update((path, report_path, checksum_path))
        require(path.is_file() and not path.is_symlink() and path.stat().st_size == size and size < 2**31,
                'Missing archive or unexpected size: ' + path.name)
        with path.open('rb') as stream:
            require(hashlib.file_digest(stream, 'sha256').hexdigest() == digest, 'Pinned archive digest mismatch.')
        require(checksum_path.read_text().split() == [digest, path.name], 'Checksum file mismatch.')
        report = json.loads(report_path.read_text())
        require(report.get('status') == 'passed' and report.get('sha256') == digest
                and report.get('archive') == path.name and report.get('size') == size, 'Invalid package report.')
        if extension == 'zip':
            require(report.get('verified_files') == verify_zip(path), 'ZIP verification count mismatch.')
        else:
            from scripts.verify_linux_package import verify
            verified = verify(path)
            require(verified == report, 'Linux archive differs from its passed report.')
        archives.append(path)
    require(set(files) == expected and len(files) == 9 and all(not p.is_symlink() for p in files),
            'Release must contain exactly the nine verified files.')
    print('All nine files and every archive member verified.', flush=True)
    return sorted(files)


def asset_inventory(release, files):
    expected = {p.name: p.stat().st_size for p in files}
    actual = {a['name']: a['size'] for a in release['assets']}
    require(len(release['assets']) == 9 and actual == expected and
            all(a['state'] == 'uploaded' for a in release['assets']), 'Release assets incomplete or different.')


def publish(folder):
    provenance()
    files = verify_packages(folder)
    tag = 'v' + VERSION
    try:
        api('releases/tags/' + tag)
    except urllib.error.HTTPError as exc:
        if exc.code != 404:
            raise
    else:
        raise ValueError('Release already exists; reconcile it explicitly, never overwrite.')
    require(not git('ls-remote', '--tags', 'origin', 'refs/tags/' + tag), 'Tag already exists.')
    subprocess.run(['git', 'fetch', 'origin', 'main'], cwd=ROOT, check=True)
    subprocess.run(['git', 'merge-base', '--is-ancestor', 'origin/main', 'HEAD'], cwd=ROOT, check=True)
    sha = git('rev-parse', 'HEAD')
    subprocess.run(['git', 'push', 'origin', sha + ':refs/heads/main'], cwd=ROOT, check=True)
    require(api('git/ref/heads/main')['object']['sha'] == sha, 'Main was not updated to the verified revision.')
    release = api('releases', 'POST', {'tag_name': tag, 'target_commitish': sha,
        'name': 'H3-Chat ' + VERSION, 'body': (ROOT / ('docs/release-' + VERSION + '.md')).read_text(),
        'draft': True, 'prerelease': False})
    print('Created draft release', release['id'], 'at', sha, flush=True)
    for path in files:
        subprocess.run(['gh', 'release', 'upload', tag, str(path), '--repo', REPO], check=True)
    release = api('releases/' + str(release['id']))
    require(release['draft'], 'Expected an unpublished draft.')
    asset_inventory(release, files)
    release = api('releases/' + str(release['id']), 'PATCH', {'draft': False, 'make_latest': 'true'})
    require(not release['draft'] and release['tag_name'] == tag, 'Publication was not confirmed.')
    asset_inventory(release, files)
    print(json.dumps({'status': 'published', 'url': release['html_url'], 'sha': sha,
                      'assets': [a['name'] for a in release['assets']]}, indent=2), flush=True)


if __name__ == '__main__':
    if sys.argv[1:] == ['provenance']:
        provenance()
    elif len(sys.argv) == 3 and sys.argv[1] == 'publish':
        publish(sys.argv[2])
    else:
        raise SystemExit('Usage: publish_verified.py provenance | publish FOLDER')

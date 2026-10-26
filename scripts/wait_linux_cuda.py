"""Reuse only a successful native CUDA job with byte-identical build inputs."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import urllib.request

ROOT=Path(__file__).resolve().parents[1]
INPUTS=('scripts/linux-sources.json','native/music/CMakeLists.txt','native/music/h3-artifacts.patch','native/sd-worker.cpp')


def api(path):
    request=urllib.request.Request('https://api.github.com/repos/'+os.environ['GITHUB_REPOSITORY']+'/'+path,
        headers={'Authorization':'Bearer '+os.environ['GH_TOKEN'],'Accept':'application/vnd.github+json'})
    with urllib.request.urlopen(request,timeout=30) as response:return json.load(response)


def wait(run):
    if not run.isdecimal():raise ValueError('CUDA run ID must be numeric.')
    info=api('actions/runs/'+run)
    if info.get('head_repository',{}).get('full_name')!=os.environ['GITHUB_REPOSITORY']:raise ValueError('CUDA artifact must originate from this repository.')
    revision=info['head_sha']
    subprocess.run(['git','fetch','--depth=1','origin',revision],cwd=ROOT,check=True)
    for path in (*INPUTS,'scripts/build_linux.py'):
        old=subprocess.check_output(['git','show',revision+':'+path],cwd=ROOT)
        if hashlib.sha256(old).digest()!=hashlib.sha256((ROOT/path).read_bytes()).digest():raise ValueError('CUDA build input changed: '+path)
    deadline=time.monotonic()+3600
    while time.monotonic()<deadline:
        jobs=api('actions/runs/'+run+'/jobs?per_page=100')['jobs']
        cuda=next((job for job in jobs if job['name']=='cuda'),None)
        if not cuda:raise ValueError('Selected run has no native CUDA job.')
        if cuda['status']=='completed':
            if cuda['conclusion']!='success':raise ValueError('Selected native CUDA job failed: '+str(cuda['conclusion']))
            artifacts=api('actions/runs/'+run+'/artifacts?per_page=100')['artifacts']
            if any(a['name']=='H3-Chat-linux-cuda-components' and not a['expired'] for a in artifacts):
                print('Reusing verified native CUDA artifact from',run,revision);return
        time.sleep(30)
    raise TimeoutError('Native CUDA artifact was not completed within one hour.')


if __name__=='__main__':wait(sys.argv[1])

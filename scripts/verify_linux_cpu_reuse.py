"""Reuse a passed CPU base only when application/native sources did not change."""
import json,os,subprocess,sys,urllib.request

def api(path):
    req=urllib.request.Request('https://api.github.com/repos/'+os.environ['GITHUB_REPOSITORY']+'/'+path,
        headers={'Authorization':'Bearer '+os.environ['GH_TOKEN'],'Accept':'application/vnd.github+json'})
    with urllib.request.urlopen(req,timeout=30) as response:return json.load(response)

run=sys.argv[1]
if not run.isdecimal():raise ValueError('CPU run ID must be numeric.')
info=api('actions/runs/'+run)
if info.get('head_repository',{}).get('full_name')!=os.environ['GITHUB_REPOSITORY']:raise ValueError('CPU base must originate from this repository.')
jobs=api('actions/runs/'+run+'/jobs?per_page=100')['jobs']
if not any(j['name'] in ('cpu','linux / cpu') and j['conclusion']=='success' for j in jobs):raise ValueError('Selected CPU base was not successfully verified.')
artifacts=api('actions/runs/'+run+'/artifacts?per_page=100')['artifacts']
if not any(a['name']=='H3-Chat-linux-cpu-base' and not a['expired'] for a in artifacts):raise ValueError('Verified CPU base artifact missing.')
revision=info['head_sha'];subprocess.run(['git','fetch','--depth=1','origin',revision],check=True)
changed=set(subprocess.check_output(['git','diff','--name-only',revision,'HEAD'],text=True).splitlines())
allowed={'.github/workflows/linux.yml','scripts/compact_linux_runtime.py','scripts/verify_linux_cpu_reuse.py','tests/test_linux_package.py'}
if changed-allowed:raise ValueError('Application/build inputs changed: '+str(sorted(changed-allowed)))
print('Reusing the successfully verified CPU base; application and native sources are identical:',revision)

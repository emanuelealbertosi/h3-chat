"""Allow a Kali-only retest when only its test environment changed."""
import json,os,subprocess,sys,urllib.request

def api(path):
    req=urllib.request.Request('https://api.github.com/repos/'+os.environ['GITHUB_REPOSITORY']+'/'+path,headers={'Authorization':'Bearer '+os.environ['GH_TOKEN'],'Accept':'application/vnd.github+json'})
    with urllib.request.urlopen(req,timeout=30) as response:return json.load(response)

run=sys.argv[1]
if not run.isdecimal():raise ValueError('Package run must be numeric.')
info=api('actions/runs/'+run)
if info.get('head_repository',{}).get('full_name')!=os.environ['GITHUB_REPOSITORY']:raise ValueError('Package must originate from this repository.')
jobs=api('actions/runs/'+run+'/jobs?per_page=100')['jobs']
if not any(j['name']=='package' and j['conclusion']=='success' for j in jobs):raise ValueError('The package archive was not successfully verified.')
artifacts=api('actions/runs/'+run+'/artifacts?per_page=100')['artifacts']
if not any(a['name']=='H3-Chat-linux-x64' and not a['expired'] for a in artifacts):raise ValueError('Verified final package artifact unavailable.')
revision=info['head_sha'];subprocess.run(['git','fetch','--depth=1','origin',revision],check=True)
changes=set(subprocess.check_output(['git','diff','--name-only',revision,'HEAD'],text=True).splitlines())
if changes-{'.github/workflows/linux.yml','scripts/verify_linux_package_reuse.py','scripts/check_kali_rootfs.sh'}:raise ValueError('Application/package source changed since archive verification: '+str(changes))
print('Kali-only retest: exact verified archive, unchanged application and installer:',revision)

"""CI packaging uses the exact tested music binary, verified against the pinned manifest."""
import json,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from h3chat.downloads import Downloads
manifest=json.loads((ROOT/'runtimes.json').read_text());entry=manifest['music_cpu']['files'][0];archive=ROOT/entry['path']
archive.parent.mkdir(parents=True,exist_ok=True)
if not archive.exists():
 tag=entry['url'].split('/download/')[1].split('/')[0]
 subprocess.run(['gh','release','download',tag,'--repo','emanuelealbertosi/h3-chat','--pattern',archive.name,'--dir',str(archive.parent)],check=True)
manager=Downloads(ROOT,{},manifest);manager.start('music_cpu','runtime')
while True:
 task=manager.snapshot()[0]
 if task['status']=='done':break
 if task['status']!='running':raise SystemExit(task['error'])
 time.sleep(.25)
worker=ROOT/'runtime/music/cpu/h3-music-worker.exe'
result=subprocess.run([str(worker)],input=b'',capture_output=True,cwd=worker.parent,timeout=30)
assert result.returncode==0,result.stderr.decode('utf-8','replace')
assert json.loads(result.stdout)['event']=='hello',result.stdout
print('Tested CPU music worker installed, checksum and executable protocol verified.')

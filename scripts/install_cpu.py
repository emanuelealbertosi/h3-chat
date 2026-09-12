import json
import sys
import threading
import time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from h3chat.downloads import Downloads
manager=Downloads(ROOT,{},json.loads((ROOT/'runtimes.json').read_text()))
manager.start('cpu','runtime')
while True:
    task=manager.snapshot()[0]
    if task['status']=='done':break
    if task['status']!='running':raise SystemExit(task['error'])
    time.sleep(1)
print('CPU engines installed and verified.')

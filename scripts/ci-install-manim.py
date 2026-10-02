"""Install hash-locked optional render components for Windows release validation."""
import json
import sys
import time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from h3chat.downloads import Downloads
from h3chat.tools_runtime import status

downloads=Downloads(ROOT,{},json.loads((ROOT/'runtimes.json').read_text()))
for kind in ('lab','latex'):
    if status(ROOT)[kind]['ready']:continue
    key='tools_'+kind;downloads.start(key,'runtime');deadline=time.monotonic()+900
    while time.monotonic()<deadline:
        task=next(t for t in downloads.snapshot() if t['id']==key)
        if task['status']=='done':break
        if task['status']!='running':raise RuntimeError(task['error'])
        time.sleep(.5)
    else:downloads.cancel(key);raise TimeoutError(key)
    assert status(ROOT)[kind]['ready'],kind
    print(kind,'installed and verified')

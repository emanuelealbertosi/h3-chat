"""CI-only minimal startup probes. Uses the actual restrictive H3 profile."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from h3chat.posix_computer import sandbox_command
stage=ROOT/'build/macos/H3-Chat'
with tempfile.TemporaryDirectory(prefix='h3-mac-probe-') as folder:
    cwd=Path(folder).resolve();env={'PATH':'/usr/bin:/bin','HOME':str(cwd),'TMPDIR':str(cwd),'LANG':'en_US.UTF-8'}
    for command in (['/usr/bin/true'],['/bin/sh','-c','printf SHELL_OK'],[str(stage/'runtime/python/bin/python3'),'-I','-c','print("PYTHON_OK")']):
        for guarded in (False,True):
            args=sandbox_command(stage,command,cwd,env)
            if guarded:args=[str(stage/'runtime/tools/h3-process-guard'),*args]
            result=subprocess.run(args,cwd=cwd,env=env,capture_output=True,timeout=20)
            print(json.dumps({'command':command[0],'guarded':guarded,'code':result.returncode,'out':result.stdout.decode('utf8','replace')[-500:],'error':result.stderr.decode('utf8','replace')[-1500:]}),flush=True)
for path in sorted((Path.home()/'Library/Logs/DiagnosticReports').glob('*.ips'))[-8:]:
    if any(name in path.name.lower() for name in ('python','sandbox','h3-process')):
        raw=path.read_text(errors='replace')
        print('Crash report:',path.name,raw[:700],raw[raw.find('"exception"'):raw.find('"exception"')+800],flush=True)

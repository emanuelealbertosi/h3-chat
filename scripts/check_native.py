"""Verify the shipped worker can load the pinned CPU DLL without model weights."""
import json
import subprocess
from pathlib import Path

root=Path(__file__).resolve().parents[1]
with subprocess.Popen([str(root/'native/h3-sd-worker.exe')],stdin=subprocess.PIPE,
                      stdout=subprocess.PIPE,stderr=subprocess.PIPE) as process:
    commands=[{'op':'probe','dll':str(root/'runtime/cpu/sd/stable-diffusion.dll')},{'op':'close'}]
    output,errors=process.communicate(('\n'.join(json.dumps(c) for c in commands)+'\n').encode(),timeout=30)
    events=[json.loads(line) for line in output.splitlines()]
    assert process.returncode==0,(process.returncode,errors.decode('utf-8','replace'))
    assert events[0]=={'event':'hello','protocol':1},events
    assert events[1].get('event')=='ready' and events[1].get('commit')=='7f410a3',events
    print('Native worker protocol and stable-diffusion.cpp ABI verified: 7f410a3')

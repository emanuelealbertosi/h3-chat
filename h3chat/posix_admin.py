"""One human-approved POSIX command; native authentication stays outside H3."""
import base64
import json
import os
from pathlib import Path
import secrets
import shlex
import shutil
import socket
import subprocess
import sys
import time


def elevate(root,command,folder,timeout=600):
    from .platform_runtime import python_executable
    if os.geteuid()==0:raise PermissionError('Avvia H3 come utente normale; non mantenere il server come root.')
    root=Path(root);key=secrets.token_hex(32)
    with socket.socket() as server:
        server.bind(('127.0.0.1',0));server.listen(4);server.settimeout(.5)
        request={'command':command,'timeout':min(600,timeout),'port':server.getsockname()[1],'key':key}
        encoded=base64.urlsafe_b64encode(json.dumps(request).encode()).decode()
        args=[str(python_executable(root)),'-I','-X','utf8',str(root/'native/agent-posix-admin-runner.py'),encoded]
        if sys.platform=='darwin':
            script='on run argv\n do shell script (item 1 of argv) with administrator privileges\nend run'
            launch=['/usr/bin/osascript','-e',script,shlex.join(args)]
        elif sys.platform.startswith('linux') and shutil.which('pkexec'):
            launch=[shutil.which('pkexec'),*args]
        else:raise ValueError('Conferma amministratore non disponibile: serve una sessione desktop con Polkit.')
        process=subprocess.Popen(launch,stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)
        try:
            # Authentication can take time. The exact command is in argv, never
            # in a mutable script or environment variable.
            deadline=time.monotonic()+120
            while time.monotonic()<deadline:
                if process.poll() is not None:return {'executed':False,'denied':True,'message':'Autorizzazione amministratore annullata o non disponibile.'}
                try:conn,_=server.accept()
                except socket.timeout:continue
                with conn:
                    conn.settimeout(2);stream=conn.makefile('r',encoding='utf8')
                    hello=json.loads(stream.readline(1000))
                    if not secrets.compare_digest(str(hello.get('key','')),key):continue
                    conn.sendall(b'{"start":true}\n');deadline=time.monotonic()+timeout+15
                    while time.monotonic()<deadline:
                        line=stream.readline(100000)
                        if not line:raise RuntimeError('Collegamento amministratore interrotto: verifica l’esito prima di ripetere.')
                        value=json.loads(line)
                        if 'result' in value:return value['result']
                    raise TimeoutError('Comando amministratore oltre il tempo massimo.')
            raise TimeoutError('Conferma amministratore scaduta.')
        finally:
            # Socket closure tells the elevated helper to kill its own children.
            if process.poll() is None:
                process.terminate()
                try:process.wait(timeout=5)
                except subprocess.TimeoutExpired:process.kill();process.wait(timeout=5)

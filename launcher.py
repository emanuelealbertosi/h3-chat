"""Start an owned loopback server and open the Windows application window."""
import argparse
import hashlib
import json
import os
import socket
import subprocess
import sys
import time
import urllib.request
import webbrowser
from pathlib import Path

ROOT=Path(__file__).resolve().parent
DATA=ROOT/'data'
FLAGS=0x08000000 if os.name=='nt' else 0
INSTANCE=hashlib.sha256(str(ROOT).encode()).hexdigest()[:16]


def get(port,path):
    with urllib.request.urlopen(f'http://127.0.0.1:{port}/api/{path}',timeout=2) as r:return json.load(r)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--stop',action='store_true');args=parser.parse_args()
    DATA.mkdir(exist_ok=True)
    port_file=DATA/'port.json'
    preferred=json.loads(port_file.read_text()) if port_file.exists() else 8787
    port=None
    for candidate in dict.fromkeys([preferred]+list(range(8787,8798))):
        try:
            health=get(candidate,'health')
            if health.get('app')=='h3-chat' and health.get('instance')==INSTANCE:
                port=candidate;break
        except (OSError,ValueError):pass
    if args.stop:
        if port:
            token=get(port,'state')['token']
            req=urllib.request.Request(f'http://127.0.0.1:{port}/api/shutdown',data=b'{}',headers={'Content-Type':'application/json','X-H3-Token':token})
            with urllib.request.urlopen(req,timeout=15):pass
        return
    if port is None:
        for candidate in dict.fromkeys([preferred]+list(range(8787,8798))):
            with socket.socket() as sock:
                try:sock.bind(('127.0.0.1',candidate));port=candidate;break
                except OSError:pass
        if port is None:raise RuntimeError('Nessuna porta locale disponibile tra 8787 e 8797.')
        log=(DATA/'server.log').open('ab')
        subprocess.Popen([sys.executable,str(ROOT/'app.py'),'--port',str(port)],cwd=ROOT,stdout=log,stderr=log,creationflags=FLAGS)
        log.close()
        for _ in range(100):
            try:
                if get(port,'health').get('instance')==INSTANCE:break
            except (OSError,ValueError):pass
            time.sleep(.15)
        else:raise RuntimeError('Avvio non riuscito. Consulta data/server.log.')
        port_file.write_text(json.dumps(port))
    url=f'http://127.0.0.1:{port}'
    candidates=[Path(os.environ.get('PROGRAMFILES(X86)','C:/Program Files (x86)'))/'Microsoft/Edge/Application/msedge.exe',
                Path(os.environ.get('PROGRAMFILES','C:/Program Files'))/'Microsoft/Edge/Application/msedge.exe']
    edge=next((p for p in candidates if p.exists()),None)
    if edge:
        subprocess.Popen([str(edge),'--app='+url,'--user-data-dir='+str(DATA/'window-profile'),'--no-first-run'],creationflags=FLAGS)
    else:webbrowser.open(url)


if __name__=='__main__':
    try:main()
    except Exception as exc:
        if os.name=='nt':
            import ctypes
            ctypes.windll.user32.MessageBoxW(None,str(exc),'H3-Chat',0x10)
        else:raise

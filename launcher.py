"""Start an owned loopback server and open the Windows application window."""
import argparse
import codecs
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


def follow_logs(port):
    """Keep the startup console open without owning the server's lifetime."""
    print(f"H3-Chat · http://127.0.0.1:{port}", flush=True)
    print(f"Log: {DATA / 'server.log'}", flush=True)
    print("Log dettagliati dei motori: " + str(DATA / 'logs'), flush=True)
    print("Questa finestra resta aperta. Per arrestare l'app usa Ferma-H3-Chat.bat.", flush=True)
    print("Chiudere questa finestra o premere Ctrl+C chiude solo la vista dei log.\n", flush=True)
    decoder=codecs.getincrementaldecoder('utf-8')(errors='replace')
    with (DATA/'server.log').open('rb') as stream:
        stream.seek(0,2)
        stream.seek(max(0,stream.tell()-65536))
        next_check=0
        missing=0
        while True:
            chunk=stream.read(65536)
            if chunk:print(decoder.decode(chunk),end='',flush=True)
            if time.monotonic()>=next_check:
                try:
                    if get(port,'health').get('instance')!=INSTANCE:break
                    missing=0
                except (OSError,ValueError):
                    missing+=1
                    if missing>=2:break
                next_check=time.monotonic()+2
            time.sleep(.15)
        chunk=stream.read()
        print(decoder.decode(chunk,final=True),end='',flush=True)
    print("\nH3-Chat non è più in esecuzione.", flush=True)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--stop',action='store_true');parser.add_argument('--logs-only',action='store_true');args=parser.parse_args()
    DATA.mkdir(exist_ok=True)
    port_file=DATA/'port.json'
    try:preferred=json.loads(port_file.read_text()) if port_file.exists() else 8787
    except (OSError,ValueError):preferred=8787
    if type(preferred) is not int or not 8787<=preferred<=8797:preferred=8787
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
        print('Avvio di H3-Chat…',flush=True)
        with (DATA/'server.log').open('ab') as log:
            child=subprocess.Popen([sys.executable,'-X','utf8','-u',str(ROOT/'app.py'),'--port',str(port)],cwd=ROOT,stdout=log,stderr=log,creationflags=FLAGS)
        for _ in range(100):
            try:
                if get(port,'health').get('instance')==INSTANCE:break
            except (OSError,ValueError):pass
            if child.poll() is not None:raise RuntimeError('Avvio non riuscito. Consulta data/server.log.')
            time.sleep(.15)
        else:raise RuntimeError('Avvio non riuscito. Consulta data/server.log.')
        port_file.write_text(json.dumps(port))
    url=f'http://127.0.0.1:{port}'
    candidates=[Path(os.environ.get('PROGRAMFILES(X86)','C:/Program Files (x86)'))/'Microsoft/Edge/Application/msedge.exe',
                Path(os.environ.get('PROGRAMFILES','C:/Program Files'))/'Microsoft/Edge/Application/msedge.exe']
    edge=next((p for p in candidates if p.exists()),None)
    if args.logs_only:
        pass
    elif edge:
        subprocess.Popen([str(edge),'--app='+url,'--user-data-dir='+str(DATA/'window-profile'),'--no-first-run'],creationflags=FLAGS)
    else:webbrowser.open(url)
    follow_logs(port)


if __name__=='__main__':
    code=0
    try:main()
    except KeyboardInterrupt:
        print("\nVista log chiusa. Per arrestare H3-Chat usa Ferma-H3-Chat.bat.",flush=True)
    except Exception as exc:
        code=1
        print("Errore di avvio: "+str(exc),file=sys.stderr,flush=True)
        if (DATA/'server.log').exists():
            with (DATA/'server.log').open('rb') as log:
                log.seek(0,2);log.seek(max(0,log.tell()-12000))
                print(log.read().decode('utf-8',errors='replace'),file=sys.stderr,flush=True)
        if os.name=='nt' and sys.stdin and sys.stdin.isatty():
            try:input("Premi Invio per chiudere…")
            except (EOFError,KeyboardInterrupt):pass
    sys.exit(code)

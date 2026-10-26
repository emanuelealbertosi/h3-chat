"""Elevated one-command helper: authenticated parent liveness + kill-on-close job."""
import base64
import json
import os
from pathlib import Path
import socket
import sys
import threading
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))

def main():
    from h3chat.computer_process import run
    request=json.loads(base64.urlsafe_b64decode(sys.argv[1]));stop=threading.Event()
    with socket.create_connection(('127.0.0.1',request['port']),timeout=10) as conn:
        conn.sendall((json.dumps({'key':request['key']})+'\n').encode());stream=conn.makefile('r',encoding='utf8')
        if json.loads(stream.readline(1000)).get('start') is not True:return
        conn.settimeout(None)
        def disconnected():
            try:
                while conn.recv(1024):pass
            finally:stop.set()
        threading.Thread(target=disconnected,daemon=True).start()
        folder=Path(request['folder']);folder.mkdir(parents=True,exist_ok=True);source=folder/'stdin-empty';source.touch();out=folder/'admin-output.log'
        env={k:v for k,v in os.environ.items() if k.upper() in ('SYSTEMROOT','WINDIR','COMSPEC','PATHEXT','PROGRAMFILES','PROGRAMFILES(X86)','PROGRAMW6432','PROCESSOR_ARCHITECTURE')}
        env.update(TEMP=str(folder),TMP=str(folder),USERPROFILE=str(folder),APPDATA=str(folder),LOCALAPPDATA=str(folder),PATH=str(Path(os.environ['SystemRoot'])/'System32'))
        command=[str(Path(os.environ['SystemRoot'])/'System32/WindowsPowerShell/v1.0/powershell.exe'),'-NoProfile','-NonInteractive','-Command',request['command']]
        result={}
        def execute():
            try:
                code=run(ROOT,command,folder,env,source,out,request['timeout'],cancel=stop)
                result.update(executed=True,exit_code=code,output=out.read_bytes()[:32000].decode('utf8',errors='replace'),truncated=out.stat().st_size>32000)
            except Exception as error:result.update(executed=True,error=str(error))
        thread=threading.Thread(target=execute);thread.start()
        while thread.is_alive():
            if stop.wait(.5):break
            try:conn.sendall(b'{"alive":true}\n')
            except OSError:stop.set();break
        thread.join(5)
        if not stop.is_set():conn.sendall((json.dumps({'result':result})+'\n').encode())

if __name__=='__main__':main()

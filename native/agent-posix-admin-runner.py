"""Root helper: exact approved command, socket liveness, private temporary data."""
import base64
import json
import os
from pathlib import Path
import socket
import sys
import tempfile
import threading

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))


def main():
    from h3chat.posix_computer import run
    request=json.loads(base64.urlsafe_b64decode(sys.argv[1]));stop=threading.Event()
    if os.geteuid()!=0:raise PermissionError('Il sistema non ha concesso i privilegi amministratore.')
    with socket.create_connection(('127.0.0.1',request['port']),timeout=10) as conn:
        conn.sendall((json.dumps({'key':request['key']})+'\n').encode());stream=conn.makefile('r',encoding='utf8')
        if json.loads(stream.readline(1000)).get('start') is not True:return
        conn.settimeout(None)
        def disconnected():
            try:
                while conn.recv(1024):pass
            finally:stop.set()
        threading.Thread(target=disconnected,daemon=True).start()
        # Never open root-owned logs in a folder writable by the model/user.
        with tempfile.TemporaryDirectory(prefix='h3-admin-') as temporary:
            folder=Path(temporary);source=folder/'stdin';source.touch();out=folder/'output'
            env={'PATH':'/usr/sbin:/usr/bin:/sbin:/bin','HOME':str(folder),'TMPDIR':str(folder),'LANG':'en_US.UTF-8'}
            result={}
            def execute():
                try:
                    code=run(ROOT,['/bin/sh','-c',request['command']],folder,env,source,out,request['timeout'],cancel=stop)
                    result.update(executed=True,exit_code=code,output=out.read_bytes()[:32000].decode('utf8',errors='replace'),truncated=out.stat().st_size>32000)
                except Exception as error:result.update(executed=True,error=str(error))
            thread=threading.Thread(target=execute);thread.start()
            while thread.is_alive():
                if stop.wait(.5):break
                try:conn.sendall(b'{"alive":true}\n')
                except OSError:stop.set();break
            thread.join(8)
            if thread.is_alive():os._exit(1)
            if not stop.is_set():conn.sendall((json.dumps({'result':result})+'\n').encode())


if __name__=='__main__':main()

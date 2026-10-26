"""One elevated helper. UAC is always shown by Windows; no persistent admin host."""
import base64
import ctypes as C
from ctypes import wintypes as W
import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import time

class SHELLEXECUTEINFO(C.Structure):
    _fields_=[('cbSize',W.DWORD),('fMask',C.c_ulong),('hwnd',W.HWND),('lpVerb',W.LPCWSTR),('lpFile',W.LPCWSTR),('lpParameters',W.LPCWSTR),('lpDirectory',W.LPCWSTR),('nShow',C.c_int),('hInstApp',W.HINSTANCE),('lpIDList',C.c_void_p),('lpClass',W.LPCWSTR),('hkeyClass',W.HKEY),('dwHotKey',W.DWORD),('hIcon',W.HANDLE),('hProcess',W.HANDLE)]

def elevate(root,command,folder,timeout=600):
    if os.name!='nt':raise ValueError('UAC richiede Windows.')
    from .platform_runtime import python_executable
    root=Path(root);key=secrets.token_hex(32)
    with socket.socket() as server:
        server.bind(('127.0.0.1',0));server.listen(4);server.settimeout(1)
        request={'command':command,'folder':str(folder),'timeout':timeout,'port':server.getsockname()[1],'key':key}
        encoded=base64.urlsafe_b64encode(json.dumps(request).encode()).decode()
        shell=C.WinDLL('shell32',use_last_error=True);shell.ShellExecuteExW.argtypes=[C.POINTER(SHELLEXECUTEINFO)];shell.ShellExecuteExW.restype=W.BOOL
        k=C.WinDLL('kernel32',use_last_error=True);k.CloseHandle.argtypes=[W.HANDLE];k.WaitForSingleObject.argtypes=[W.HANDLE,W.DWORD];k.WaitForSingleObject.restype=W.DWORD
        info=SHELLEXECUTEINFO();info.cbSize=C.sizeof(info);info.fMask=0x40|0x100;info.lpVerb='runas';info.lpFile=str(python_executable(root));info.lpParameters=subprocess.list2cmdline(['-I','-X','utf8',str(root/'native/agent-admin-runner.py'),encoded]);info.lpDirectory=str(root);info.nShow=0
        if not shell.ShellExecuteExW(C.byref(info)):
            error=C.get_last_error()
            if error==1223:return {'executed':False,'denied':True,'message':'Richiesta UAC rifiutata dall’utente.'}
            raise C.WinError(error)
        try:
            deadline=time.monotonic()+30
            while time.monotonic()<deadline:
                try:conn,_=server.accept()
                except socket.timeout:
                    if k.WaitForSingleObject(info.hProcess,0)==0:raise RuntimeError('Il componente amministratore è terminato prima del collegamento.')
                    continue
                conn.settimeout(2)
                with conn:
                    # A random challenge authenticates the helper, not an arbitrary
                    # process racing the local listener. The command was carried in
                    # the elevated process command line, not an editable script file.
                    stream=conn.makefile('r',encoding='utf8');hello=json.loads(stream.readline(1000))
                    if not secrets.compare_digest(hello.get('key',''),key):continue
                    conn.sendall(b'{"start":true}\n');deadline=time.monotonic()+timeout+15
                    while time.monotonic()<deadline:
                        line=stream.readline(100000)
                        if not line:raise RuntimeError('Collegamento amministratore interrotto: esito da verificare.')
                        value=json.loads(line)
                        if 'result' in value:return value['result']
                    raise TimeoutError('Comando amministratore oltre il tempo massimo.')
            raise TimeoutError('Componente amministratore non collegato entro il tempo massimo.')
        finally:
            # Closing the authenticated socket is the helper's stop signal.
            # The elevated helper owns its Job Object and kills its descendants.
            if info.hProcess:k.CloseHandle(info.hProcess)

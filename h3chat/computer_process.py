"""Windows process broker: suspended launch, kill-on-close job and optional LPAC.

The generated program never receives the job handle or the ACL cleanup ticket.
"""
import ctypes as C
from ctypes import wintypes as W
import json
import os
from pathlib import Path
import subprocess
import time
import uuid
from .windows_sandbox import SECURITY_CAPABILITIES,STARTUPINFOEX,PROCESS_INFORMATION,EXTENDED_LIMITS

class SID_AND_ATTRIBUTES(C.Structure):_fields_=[('Sid',C.c_void_p),('Attributes',W.DWORD)]

def dlls():
    k=C.WinDLL('kernel32',use_last_error=True);a=C.WinDLL('advapi32',use_last_error=True);u=C.WinDLL('userenv',use_last_error=True)
    for name,params,result in [
        ('InitializeProcThreadAttributeList',[C.c_void_p,W.DWORD,W.DWORD,C.POINTER(C.c_size_t)],W.BOOL),
        ('UpdateProcThreadAttribute',[C.c_void_p,W.DWORD,C.c_size_t,C.c_void_p,C.c_size_t,C.c_void_p,C.c_void_p],W.BOOL),
        ('DeleteProcThreadAttributeList',[C.c_void_p],None),
        ('CreateProcessW',[W.LPCWSTR,W.LPWSTR,C.c_void_p,C.c_void_p,W.BOOL,W.DWORD,C.c_void_p,W.LPCWSTR,C.c_void_p,C.POINTER(PROCESS_INFORMATION)],W.BOOL),
        ('CreateJobObjectW',[C.c_void_p,W.LPCWSTR],W.HANDLE),
        ('SetInformationJobObject',[W.HANDLE,C.c_int,C.c_void_p,W.DWORD],W.BOOL),
        ('AssignProcessToJobObject',[W.HANDLE,W.HANDLE],W.BOOL),('ResumeThread',[W.HANDLE],W.DWORD),
        ('WaitForSingleObject',[W.HANDLE,W.DWORD],W.DWORD),('GetExitCodeProcess',[W.HANDLE,C.POINTER(W.DWORD)],W.BOOL),
        ('TerminateProcess',[W.HANDLE,W.UINT],W.BOOL),('TerminateJobObject',[W.HANDLE,W.UINT],W.BOOL),
        ('CloseHandle',[W.HANDLE],W.BOOL),('LocalFree',[C.c_void_p],C.c_void_p)]:
        f=getattr(k,name);f.argtypes=params;f.restype=result
    u.CreateAppContainerProfile.argtypes=[W.LPCWSTR,W.LPCWSTR,W.LPCWSTR,C.c_void_p,W.DWORD,C.POINTER(C.c_void_p)];u.CreateAppContainerProfile.restype=C.c_long
    u.DeleteAppContainerProfile.argtypes=[W.LPCWSTR];u.DeleteAppContainerProfile.restype=C.c_long
    a.ConvertSidToStringSidW.argtypes=[C.c_void_p,C.POINTER(W.LPWSTR)];a.ConvertSidToStringSidW.restype=W.BOOL
    a.ConvertStringSidToSidW.argtypes=[W.LPCWSTR,C.POINTER(C.c_void_p)];a.ConvertStringSidToSidW.restype=W.BOOL
    a.FreeSid.argtypes=[C.c_void_p];a.FreeSid.restype=C.c_void_p
    return k,a,u

def acl(path,sid,action,rights=''):
    value='*'+sid+(':'+rights if rights else '')
    result=subprocess.run(['icacls',str(path),action,value,'/Q'],capture_output=True,creationflags=0x08000000)
    if result.returncode:raise RuntimeError('Impossibile applicare/rimuovere il confine di esecuzione: '+str(path))

def cleanup(root,owner=None):
    """Only remove our exact SID ACEs/profile. Never delete the selected folder."""
    if os.name!='nt':return
    _,_,u=dlls()
    for path in (Path(root)/'runtime/computer-jobs/.tickets').glob('*.json'):
        try:
            data=json.loads(path.read_text())
            if owner is not None and data.get('owner')!=owner:continue
            if not data.get('profile','').startswith('H3.Computer.') or not data.get('sid','').startswith('S-1-15-2-'):continue
            for target in data['grants']:acl(Path(target),data['sid'],'/remove:g')
            u.DeleteAppContainerProfile(data['profile']);path.unlink()
        except (OSError,ValueError,RuntimeError):continue

def run(app_root,argv,cwd,env,stdin,stdout,timeout=60,sandbox=None,cancel=None):
    if os.name!='nt':raise ValueError('Broker Windows non disponibile.')
    import msvcrt
    root=Path(app_root).resolve();k,a,u=dlls();sid=C.c_void_p();net=C.c_void_p();text=W.LPWSTR();attribute=None;job=None;proc=PROCESS_INFORMATION();ticket=None;derived=[]
    def check(value):
        if not value:raise C.WinError(C.get_last_error())
        return value
    record={'owner':os.getpid(),'profile':'H3.Computer.'+uuid.uuid4().hex,'sid':'','grants':[]}
    try:
        if sandbox:
            hr=u.CreateAppContainerProfile(record['profile'],'H3 Agent Sandbox','Selected folder only',None,0,C.byref(sid))
            if hr<0:raise RuntimeError(f'AppContainer non disponibile (0x{hr&0xffffffff:08x}).')
            check(a.ConvertSidToStringSidW(sid,C.byref(text)));record['sid']=text.value
            tickets=root/'runtime/computer-jobs/.tickets';tickets.mkdir(parents=True,exist_ok=True);ticket=tickets/(uuid.uuid4().hex+'.json')
            def grant(path,rights):
                # Persist BEFORE each ACL operation, including partial failures.
                record['grants'].append(str(path));ticket.write_text(json.dumps(record),encoding='utf8');acl(path,record['sid'],'/grant',rights)
            grant(root/'runtime/python','(OI)(CI)(RX)')
            grant(root/'native/agent-computer-runner.py','(RX)')
            grant(Path(sandbox),'(OI)(CI)(M)')
            check(a.ConvertStringSidToSidW('S-1-15-3-1',C.byref(net)))
            # Explicit human authorization: system registry *read* needed by
            # Python startup. No COM capability and no registry write grants.
            derive=C.WinDLL('kernelbase',use_last_error=True).DeriveCapabilitySidsFromName
            derive.argtypes=[W.LPCWSTR,C.POINTER(C.POINTER(C.c_void_p)),C.POINTER(W.DWORD),C.POINTER(C.POINTER(C.c_void_p)),C.POINTER(W.DWORD)];derive.restype=W.BOOL
            groups=C.POINTER(C.c_void_p)();caps=C.POINTER(C.c_void_p)();ng=W.DWORD();nc=W.DWORD()
            check(derive('registryRead',C.byref(groups),C.byref(ng),C.byref(caps),C.byref(nc)))
            if not nc.value:raise RuntimeError('Capability Windows registryRead non disponibile.')
            cap_values=[net,*[caps[i] for i in range(nc.value)]]
            derived=[groups[i] for i in range(ng.value)]+[caps[i] for i in range(nc.value)]+[groups,caps]
        count=3 if sandbox else 1;size=C.c_size_t();k.InitializeProcThreadAttributeList(None,count,0,C.byref(size));attribute=C.create_string_buffer(size.value)
        check(k.InitializeProcThreadAttributeList(attribute,count,0,C.byref(size)))
        if sandbox:
            capability=(SID_AND_ATTRIBUTES*len(cap_values))(*(SID_AND_ATTRIBUTES(p,4) for p in cap_values));security=SECURITY_CAPABILITIES(sid,C.cast(capability,C.c_void_p),len(cap_values),0)
            check(k.UpdateProcThreadAttribute(attribute,0,0x20009,C.byref(security),C.sizeof(security),None,None))
            policy=W.DWORD(1) # PROC_THREAD_ATTRIBUTE_ALL_APPLICATION_PACKAGES_POLICY: opt out (LPAC)
            check(k.UpdateProcThreadAttribute(attribute,0,0x2000F,C.byref(policy),C.sizeof(policy),None,None))
        job=check(k.CreateJobObjectW(None,None));limits=EXTENDED_LIMITS()
        limits.BasicLimitInformation.LimitFlags=0x2000|0x200|0x8;limits.BasicLimitInformation.ActiveProcessLimit=32;limits.JobMemoryLimit=8*1024**3
        check(k.SetInformationJobObject(job,9,C.byref(limits),C.sizeof(limits)))
        with open(stdin,'rb') as source,open(stdout,'wb') as target:
            handles=(W.HANDLE*2)(msvcrt.get_osfhandle(source.fileno()),msvcrt.get_osfhandle(target.fileno()))
            for handle in handles:os.set_handle_inheritable(handle,True)
            check(k.UpdateProcThreadAttribute(attribute,0,0x20002,handles,C.sizeof(handles),None,None))
            startup=STARTUPINFOEX();startup.StartupInfo.cb=C.sizeof(startup);startup.lpAttributeList=C.cast(attribute,C.c_void_p)
            startup.StartupInfo.dwFlags=0x100;startup.StartupInfo.hStdInput=handles[0];startup.StartupInfo.hStdOutput=handles[1];startup.StartupInfo.hStdError=handles[1]
            command=C.create_unicode_buffer(subprocess.list2cmdline([str(v) for v in argv]));environment=C.create_unicode_buffer('\0'.join(k+'='+v for k,v in sorted(env.items()))+'\0\0')
            check(k.CreateProcessW(None,command,None,None,True,0x80000|0x08000000|0x400|0x4,environment,str(cwd),C.byref(startup),C.byref(proc)))
            check(k.AssignProcessToJobObject(job,proc.hProcess));check(k.ResumeThread(proc.hThread)!=0xffffffff)
            deadline=time.monotonic()+timeout
            while k.WaitForSingleObject(proc.hProcess,100)==258:
                if cancel and cancel.is_set():raise InterruptedError('Esecuzione fermata.')
                if time.monotonic()>deadline:raise TimeoutError('Comando oltre il tempo massimo.')
                if Path(stdout).stat().st_size>4*1024**2:raise ValueError('Comando fermato: uscita oltre 4 MB.')
            code=W.DWORD();check(k.GetExitCodeProcess(proc.hProcess,C.byref(code)));return code.value
    finally:
        if job:k.TerminateJobObject(job,1);k.CloseHandle(job)
        elif proc.hProcess:k.TerminateProcess(proc.hProcess,1)
        for handle in (proc.hThread,proc.hProcess):
            if handle:k.CloseHandle(handle)
        if attribute:k.DeleteProcThreadAttributeList(attribute)
        if text:k.LocalFree(text)
        if net:k.LocalFree(net)
        for p in derived:k.LocalFree(C.c_void_p(p) if isinstance(p,int) else C.cast(p,C.c_void_p))
        if sid:a.FreeSid(sid)
        if ticket:cleanup(root,os.getpid())

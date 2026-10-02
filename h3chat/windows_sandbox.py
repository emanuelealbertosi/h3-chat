"""AppContainer + Job Object broker; no fallback to unrestricted execution."""
import ctypes as C
from ctypes import wintypes as W
import hashlib
import json
import re
import shutil
import os
from pathlib import Path
import subprocess
import time
import uuid


class SECURITY_CAPABILITIES(C.Structure):
    _fields_=[('AppContainerSid',C.c_void_p),('Capabilities',C.c_void_p),('CapabilityCount',W.DWORD),('Reserved',W.DWORD)]
class STARTUPINFO(C.Structure):
    _fields_=[('cb',W.DWORD),('lpReserved',W.LPWSTR),('lpDesktop',W.LPWSTR),('lpTitle',W.LPWSTR),
        ('dwX',W.DWORD),('dwY',W.DWORD),('dwXSize',W.DWORD),('dwYSize',W.DWORD),
        ('dwXCountChars',W.DWORD),('dwYCountChars',W.DWORD),('dwFillAttribute',W.DWORD),
        ('dwFlags',W.DWORD),('wShowWindow',W.WORD),('cbReserved2',W.WORD),('lpReserved2',C.c_void_p),
        ('hStdInput',W.HANDLE),('hStdOutput',W.HANDLE),('hStdError',W.HANDLE)]
class STARTUPINFOEX(C.Structure):
    _fields_=[('StartupInfo',STARTUPINFO),('lpAttributeList',C.c_void_p)]
class PROCESS_INFORMATION(C.Structure):
    _fields_=[('hProcess',W.HANDLE),('hThread',W.HANDLE),('dwProcessId',W.DWORD),('dwThreadId',W.DWORD)]
class BASIC_LIMITS(C.Structure):
    _fields_=[('PerProcessUserTimeLimit',C.c_int64),('PerJobUserTimeLimit',C.c_int64),('LimitFlags',W.DWORD),
        ('MinimumWorkingSetSize',C.c_size_t),('MaximumWorkingSetSize',C.c_size_t),('ActiveProcessLimit',W.DWORD),
        ('Affinity',C.c_size_t),('PriorityClass',W.DWORD),('SchedulingClass',W.DWORD)]
class IO_COUNTERS(C.Structure):
    _fields_=[(name,C.c_uint64) for name in ('ReadOperationCount','WriteOperationCount','OtherOperationCount','ReadTransferCount','WriteTransferCount','OtherTransferCount')]
class EXTENDED_LIMITS(C.Structure):
    _fields_=[('BasicLimitInformation',BASIC_LIMITS),('IoInfo',IO_COUNTERS),('ProcessMemoryLimit',C.c_size_t),
        ('JobMemoryLimit',C.c_size_t),('PeakProcessMemoryUsed',C.c_size_t),('PeakJobMemoryUsed',C.c_size_t)]


def run(root,folder,args,environment,timeout=600,memory_gb=4):
    if os.name!='nt':raise ValueError('L’esecuzione Manim libera richiede l’isolamento Windows AppContainer.')
    import msvcrt
    root=Path(root).resolve();folder=Path(folder).resolve()
    if not folder.is_relative_to(root/'runtime/manim-jobs'):raise ValueError('Cartella di rendering isolata non valida.')
    k=C.WinDLL('kernel32',use_last_error=True);u=C.WinDLL('userenv',use_last_error=True);a=C.WinDLL('advapi32',use_last_error=True)
    signatures={
        'InitializeProcThreadAttributeList':([C.c_void_p,W.DWORD,W.DWORD,C.POINTER(C.c_size_t)],W.BOOL),
        'UpdateProcThreadAttribute':([C.c_void_p,W.DWORD,C.c_size_t,C.c_void_p,C.c_size_t,C.c_void_p,C.c_void_p],W.BOOL),
        'DeleteProcThreadAttributeList':([C.c_void_p],None),
        'CreateProcessW':([W.LPCWSTR,W.LPWSTR,C.c_void_p,C.c_void_p,W.BOOL,W.DWORD,C.c_void_p,W.LPCWSTR,C.c_void_p,C.POINTER(PROCESS_INFORMATION)],W.BOOL),
        'CreateJobObjectW':([C.c_void_p,W.LPCWSTR],W.HANDLE),
        'SetInformationJobObject':([W.HANDLE,C.c_int,C.c_void_p,W.DWORD],W.BOOL),
        'AssignProcessToJobObject':([W.HANDLE,W.HANDLE],W.BOOL),
        'ResumeThread':([W.HANDLE],W.DWORD),
        'WaitForSingleObject':([W.HANDLE,W.DWORD],W.DWORD),
        'GetExitCodeProcess':([W.HANDLE,C.POINTER(W.DWORD)],W.BOOL),
        'TerminateProcess':([W.HANDLE,W.UINT],W.BOOL),
        'TerminateJobObject':([W.HANDLE,W.UINT],W.BOOL),
        'CloseHandle':([W.HANDLE],W.BOOL),
        'LocalFree':([C.c_void_p],C.c_void_p),
    }
    for name,(params,result) in signatures.items():f=getattr(k,name);f.argtypes=params;f.restype=result
    u.CreateAppContainerProfile.argtypes=[W.LPCWSTR,W.LPCWSTR,W.LPCWSTR,C.c_void_p,W.DWORD,C.POINTER(C.c_void_p)];u.CreateAppContainerProfile.restype=C.c_long
    u.DeleteAppContainerProfile.argtypes=[W.LPCWSTR];u.DeleteAppContainerProfile.restype=C.c_long
    a.ConvertSidToStringSidW.argtypes=[C.c_void_p,C.POINTER(W.LPWSTR)];a.ConvertSidToStringSidW.restype=W.BOOL
    a.FreeSid.argtypes=[C.c_void_p];a.FreeSid.restype=C.c_void_p
    def check(ok):
        if not ok:raise C.WinError(C.get_last_error())
    def acl(path,action,rights=None):
        value='*'+sid_text+((':'+rights) if rights else '')
        result=subprocess.run(['icacls',str(path),action,value,'/Q'],capture_output=True,creationflags=0x08000000)
        if result.returncode:raise RuntimeError('Non è stato possibile applicare l’isolamento alla cartella '+str(path))
    profile='H3.Manim.'+hashlib.sha256(str(root).encode()).hexdigest()[:10]+'.'+folder.name
    tickets=root/'runtime/manim-jobs/.tickets';tickets.mkdir(exist_ok=True)
    ticket=tickets/(folder.name+'.json')
    sid=C.c_void_p();sid_string=W.LPWSTR();sid_text='';grants=[];denies=[];attribute=None;job=None;process=PROCESS_INFORMATION()
    try:
        hr=u.CreateAppContainerProfile(profile,'H3-Chat Manim','Isolated rendering without network capabilities',None,0,C.byref(sid))
        if hr<0:raise RuntimeError(f'Creazione AppContainer non riuscita (0x{hr&0xffffffff:08X}).')
        check(a.ConvertSidToStringSidW(sid,C.byref(sid_string)));sid_text=sid_string.value
        if not ticket.exists():ticket.write_text(json.dumps({'owner':os.getpid()}),encoding='utf-8')
        # OS/public resources remain available. Private app data, providers and
        # uploaded documents are explicitly denied; only copied job assets enter.
        private=root/'data'
        if private.is_dir():acl(private,'/deny','(OI)(CI)(F)');denies.append(private)
        for path,rights in [(root,'(RX)'),(root/'runtime','(RX)'),(root/'runtime/manim-jobs','(RX)'),(root/'runtime/tools','(RX)'),
                (root/'runtime/python','(OI)(CI)(RX)'),(root/'runtime/tools/lab','(OI)(CI)(RX)'),
                (root/'native','(OI)(CI)(RX)'),(folder,'(OI)(CI)(M)')]:
            acl(path,'/grant',rights);grants.append(path)
        latex=root/'runtime/tools/latex'
        if latex.is_dir():acl(latex,'/grant','(OI)(CI)(RX)');grants.append(latex)
        size=C.c_size_t();k.InitializeProcThreadAttributeList(None,2,0,C.byref(size));attribute=C.create_string_buffer(size.value)
        check(k.InitializeProcThreadAttributeList(attribute,2,0,C.byref(size)))
        security=SECURITY_CAPABILITIES(sid,None,0,0)
        check(k.UpdateProcThreadAttribute(attribute,0,0x20009,C.byref(security),C.sizeof(security),None,None))
        job=k.CreateJobObjectW(None,None);check(job)
        limits=EXTENDED_LIMITS();limits.BasicLimitInformation.LimitFlags=0x2000|0x200|0x8 # kill on close, aggregate memory, child count
        limits.BasicLimitInformation.ActiveProcessLimit=12;limits.JobMemoryLimit=int(memory_gb*1024**3)
        check(k.SetInformationJobObject(job,9,C.byref(limits),C.sizeof(limits)))
        with open(os.devnull,'rb') as null, (folder/'render.log').open('wb') as log:
            handles=(W.HANDLE*2)(msvcrt.get_osfhandle(null.fileno()),msvcrt.get_osfhandle(log.fileno()))
            for handle in handles:os.set_handle_inheritable(handle,True)
            check(k.UpdateProcThreadAttribute(attribute,0,0x20002,handles,C.sizeof(handles),None,None))
            startup=STARTUPINFOEX();startup.StartupInfo.cb=C.sizeof(startup);startup.lpAttributeList=C.cast(attribute,C.c_void_p)
            startup.StartupInfo.dwFlags=0x100;startup.StartupInfo.hStdInput=handles[0];startup.StartupInfo.hStdOutput=handles[1];startup.StartupInfo.hStdError=handles[1]
            command=C.create_unicode_buffer(subprocess.list2cmdline([str(x) for x in args]))
            env=C.create_unicode_buffer('\0'.join(f'{key}={value}' for key,value in sorted(environment.items()))+'\0\0')
            check(k.CreateProcessW(None,command,None,None,True,0x80000|0x08000000|0x400|0x4,env,str(folder),C.byref(startup),C.byref(process)))
            check(k.AssignProcessToJobObject(job,process.hProcess))
            if k.ResumeThread(process.hThread)==0xffffffff:check(False)
            deadline=time.monotonic()+timeout
            while k.WaitForSingleObject(process.hProcess,200)==258:
                if time.monotonic()>deadline:
                    k.TerminateJobObject(job,124);raise TimeoutError('Rendering Manim oltre il tempo massimo configurato.')
            code=W.DWORD();check(k.GetExitCodeProcess(process.hProcess,C.byref(code)))
            return code.value
    finally:
        # The Job Object also kills descendants when the broker is terminated.
        if job:k.TerminateJobObject(job,1);k.CloseHandle(job)
        elif process.hProcess:k.TerminateProcess(process.hProcess,1)
        for handle in (process.hThread,process.hProcess):
            if handle:k.CloseHandle(handle)
        if attribute:k.DeleteProcThreadAttributeList(attribute)
        cleanup_failed=False
        for path in reversed(grants):
            try:acl(path,'/remove:g')
            except Exception:cleanup_failed=True
        for path in denies:
            try:acl(path,'/remove:d')
            except Exception:cleanup_failed=True
        if sid_string:k.LocalFree(sid_string)
        if sid:a.FreeSid(sid)
        u.DeleteAppContainerProfile(profile)
        if cleanup_failed and ticket.exists():
            record=json.loads(ticket.read_text());record['cleanup_pending']=True;ticket.write_text(json.dumps(record))



def cleanup(root,owner):
    """Called by the trusted parent after killing a broker; child cannot edit tickets."""
    if os.name!='nt':return
    root=Path(root).resolve();jobs=root/'runtime/manim-jobs'
    u=C.WinDLL('userenv');a=C.WinDLL('advapi32');k=C.WinDLL('kernel32')
    u.DeriveAppContainerSidFromAppContainerName.argtypes=[W.LPCWSTR,C.POINTER(C.c_void_p)];u.DeriveAppContainerSidFromAppContainerName.restype=C.c_long
    u.DeleteAppContainerProfile.argtypes=[W.LPCWSTR];u.DeleteAppContainerProfile.restype=C.c_long
    a.ConvertSidToStringSidW.argtypes=[C.c_void_p,C.POINTER(W.LPWSTR)];a.ConvertSidToStringSidW.restype=W.BOOL
    a.FreeSid.argtypes=[C.c_void_p];k.LocalFree.argtypes=[C.c_void_p]
    for ticket in (jobs/'.tickets').glob('*.json'):
        if not re.fullmatch('[0-9a-f]{32}',ticket.stem):continue
        try:
            record=json.loads(ticket.read_text())
            if record.get('owner')!=owner:continue
            profile='H3.Manim.'+hashlib.sha256(str(root).encode()).hexdigest()[:10]+'.'+ticket.stem
            sid=C.c_void_p();text=W.LPWSTR()
            if u.DeriveAppContainerSidFromAppContainerName(profile,C.byref(sid))<0:continue
            try:
                if not a.ConvertSidToStringSidW(sid,C.byref(text)):continue
                paths=[root,root/'runtime',jobs,root/'runtime/tools',root/'runtime/python',root/'runtime/tools/lab',root/'native',jobs/ticket.stem,root/'runtime/tools/latex']
                failed=False
                for path,action in [(p,'/remove:g') for p in paths if p.exists()]+([(root/'data','/remove:d')] if (root/'data').exists() else []):
                    if subprocess.run(['icacls',str(path),action,'*'+text.value,'/Q'],capture_output=True,creationflags=0x08000000).returncode:failed=True
                if failed:continue  # keep ticket for cleanup retry
                drive=record.get('drive','')
                if re.fullmatch('[D-Z]:',drive):
                    k.QueryDosDeviceW.argtypes=[W.LPCWSTR,W.LPWSTR,W.DWORD];k.QueryDosDeviceW.restype=W.DWORD
                    buffer=C.create_unicode_buffer(32768)
                    if k.QueryDosDeviceW(drive,buffer,len(buffer)) and buffer.value.casefold()==('\\??\\'+str(root)).casefold():
                        if subprocess.run(['subst',drive,'/D'],capture_output=True,creationflags=0x08000000).returncode:continue
                u.DeleteAppContainerProfile(profile);ticket.unlink()
                folder=jobs/ticket.stem
                if folder.is_dir() and folder.resolve().parent==jobs.resolve():shutil.rmtree(folder)
            finally:
                if text:k.LocalFree(text)
                if sid:a.FreeSid(sid)
        except (OSError,ValueError):continue

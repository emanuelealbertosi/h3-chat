"""Start Chromium suspended inside an owned Windows job before any child runs."""
import os,subprocess


class WindowsBrowserProcess:
    def __init__(self,args,log,cwd):
        import ctypes as C
        from ctypes import wintypes as W
        import msvcrt
        from .computer_process import dlls
        from .windows_sandbox import STARTUPINFOEX,PROCESS_INFORMATION,EXTENDED_LIMITS
        self.C=C;self.W=W;self.k,_,_=dlls();self.job=None;self.proc=PROCESS_INFORMATION();self.returncode=None
        k=self.k;attributes=None
        def check(value):
            if not value:raise C.WinError(C.get_last_error())
            return value
        try:
            self.job=check(k.CreateJobObjectW(None,None));limits=EXTENDED_LIMITS();limits.BasicLimitInformation.LimitFlags=0x2000
            check(k.SetInformationJobObject(self.job,9,C.byref(limits),C.sizeof(limits)))
            size=C.c_size_t();k.InitializeProcThreadAttributeList(None,1,0,C.byref(size));attributes=C.create_string_buffer(size.value)
            check(k.InitializeProcThreadAttributeList(attributes,1,0,C.byref(size)))
            with open(os.devnull,'rb') as source:
                handles=(W.HANDLE*2)(msvcrt.get_osfhandle(source.fileno()),msvcrt.get_osfhandle(log.fileno()))
                for handle in handles:os.set_handle_inheritable(handle,True)
                try:
                    check(k.UpdateProcThreadAttribute(attributes,0,0x20002,handles,C.sizeof(handles),None,None))
                    startup=STARTUPINFOEX();startup.StartupInfo.cb=C.sizeof(startup);startup.lpAttributeList=C.cast(attributes,C.c_void_p)
                    startup.StartupInfo.dwFlags=0x100;startup.StartupInfo.hStdInput=handles[0];startup.StartupInfo.hStdOutput=handles[1];startup.StartupInfo.hStdError=handles[1]
                    command=C.create_unicode_buffer(subprocess.list2cmdline([str(v) for v in args]))
                    check(k.CreateProcessW(None,command,None,None,True,0x80000|0x08000000|0x4,None,str(cwd),C.byref(startup),C.byref(self.proc)))
                    check(k.AssignProcessToJobObject(self.job,self.proc.hProcess));check(k.ResumeThread(self.proc.hThread)!=0xffffffff)
                    self.pid=self.proc.dwProcessId
                finally:
                    for handle in handles:os.set_handle_inheritable(handle,False)
        except BaseException:self.close();raise
        finally:
            if attributes:k.DeleteProcThreadAttributeList(attributes)
            if self.proc.hThread:k.CloseHandle(self.proc.hThread);self.proc.hThread=None

    def poll(self):
        if self.returncode is not None:return self.returncode
        if self.k.WaitForSingleObject(self.proc.hProcess,0)==258:return None
        value=self.W.DWORD();self.k.GetExitCodeProcess(self.proc.hProcess,self.C.byref(value));self.returncode=value.value;return self.returncode

    def wait(self,timeout=None):
        if self.k.WaitForSingleObject(self.proc.hProcess,int(timeout*1000) if timeout is not None else 0xffffffff)==258:raise subprocess.TimeoutExpired('Agent browser',timeout)
        return self.poll()

    def terminate(self):
        if self.job:self.k.TerminateJobObject(self.job,1)
    kill=terminate

    def close(self):
        self.terminate()
        if self.job:self.k.CloseHandle(self.job);self.job=None
        if self.proc.hProcess:
            self.wait(timeout=5);self.k.CloseHandle(self.proc.hProcess);self.proc.hProcess=None


def start(args,log,cwd):
    if os.name=='nt':return WindowsBrowserProcess(args,log,cwd)
    return subprocess.Popen([str(v) for v in args],stdin=subprocess.DEVNULL,stdout=log,stderr=log,cwd=cwd,start_new_session=True)

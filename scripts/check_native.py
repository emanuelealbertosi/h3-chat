"""Verify the CPU DLL ABI and app-local CRT loading, without model weights."""
import ctypes
from ctypes import wintypes
import json
import subprocess
from pathlib import Path

root=Path(__file__).resolve().parents[1]
with subprocess.Popen([str(root/'native/h3-sd-worker.exe')],stdin=subprocess.PIPE,
                      stdout=subprocess.PIPE,stderr=subprocess.PIPE) as process:
    try:
        assert json.loads(process.stdout.readline())=={'event':'hello','protocol':1}
        process.stdin.write((json.dumps({'op':'probe','dll':str(root/'runtime/cpu/sd/stable-diffusion.dll')})+'\n').encode());process.stdin.flush()
        ready=json.loads(process.stdout.readline())
        assert ready.get('event')=='ready' and ready.get('commit')=='7f410a3',ready
        # The build PC may have VC Redist globally installed: verify actual DLL origins.
        kernel=ctypes.WinDLL('kernel32',use_last_error=True);psapi=ctypes.WinDLL('psapi',use_last_error=True)
        kernel.OpenProcess.argtypes=[wintypes.DWORD,wintypes.BOOL,wintypes.DWORD];kernel.OpenProcess.restype=wintypes.HANDLE
        kernel.CloseHandle.argtypes=[wintypes.HANDLE]
        psapi.EnumProcessModules.argtypes=[wintypes.HANDLE,ctypes.POINTER(wintypes.HMODULE),wintypes.DWORD,ctypes.POINTER(wintypes.DWORD)]
        psapi.GetModuleFileNameExW.argtypes=[wintypes.HANDLE,wintypes.HMODULE,wintypes.LPWSTR,wintypes.DWORD]
        handle=kernel.OpenProcess(0x410,False,process.pid)
        assert handle,ctypes.get_last_error()
        try:
            modules=(wintypes.HMODULE*1024)();needed=wintypes.DWORD()
            assert psapi.EnumProcessModules(handle,modules,ctypes.sizeof(modules),ctypes.byref(needed))
            loaded={}
            for module in modules[:needed.value//ctypes.sizeof(wintypes.HMODULE)]:
                name=ctypes.create_unicode_buffer(32768)
                if psapi.GetModuleFileNameExW(handle,module,name,len(name)):
                    path=Path(name.value);loaded[path.name.lower()]=path.resolve()
            for name in ('msvcp140.dll','msvcp140_codecvt_ids.dll','vcruntime140.dll','vcruntime140_1.dll'):
                assert loaded.get(name)==(root/'runtime/cpu/sd'/name).resolve(),(name,loaded.get(name))
        finally:kernel.CloseHandle(handle)
        output,errors=process.communicate(b'{"op":"close"}\n',timeout=30)
        assert process.returncode==0,(process.returncode,errors.decode('utf-8','replace'))
        print('Native ABI 7f410a3 and app-local Microsoft CRT origins verified.')
    finally:
        if process.poll() is None:
            process.kill();process.wait(timeout=10)

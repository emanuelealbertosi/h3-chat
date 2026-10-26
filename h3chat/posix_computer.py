"""POSIX process broker. A Sandbox never falls back to ordinary execution."""
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import time


def sandbox_backend():
    if sys.platform=='darwin':return '/usr/bin/sandbox-exec' if Path('/usr/bin/sandbox-exec').is_file() else None
    if sys.platform.startswith('linux'):return shutil.which('bwrap')
    return None


def mac_profile(reads,writes):
    # Seatbelt is inherited across exec/fork. No network, Mach service access,
    # keychain or user-home access. Web downloads use the host H3 tools.
    quoted=lambda p:json.dumps(str(Path(p).resolve()))
    parts=['(version 1)','(deny default)','(allow process-exec process-fork)',
           '(allow signal (target same-sandbox))','(allow sysctl-read)',
           '(allow file-read-metadata)',
           # libsecinit asks whether its own process expects an App Sandbox
           # container. This permits only that self-query, not Mach services,
           # file access, networking or general mac_syscall operations.
           '(allow system-mac-syscall (require-all (mac-policy-name "Sandbox") (mac-syscall-number 67)))',
           # Explicit human authorization, 2026-10-26; exact reviewed list in
           # docs/macos-sandbox-startup-proposal.md. No general Mach allowance.
           '(allow mach-lookup (global-name "com.apple.secinitd") (global-name "com.apple.system.opendirectoryd.libinfo") (global-name "com.apple.system.logger") (global-name "com.apple.logd"))',
           '(allow file-read-data file-write-data (subpath "/dev/fd"))',
           '(allow file-read* (literal "/"))',
           '(allow file-read* file-map-executable (subpath "/System") (subpath "/usr/lib") (subpath "/usr/share") (subpath "/bin") (subpath "/usr/bin") (subpath "/dev") (literal "/private/etc/localtime"))',
           '(allow file-write* (literal "/dev/null"))']
    for path in reads:parts.append('(allow file-read* file-map-executable (subpath '+quoted(path)+'))')
    for path in writes:parts.append('(allow file-read* file-write* file-map-executable (subpath '+quoted(path)+'))')
    return '\n'.join(parts)


def sandbox_command(root,argv,cwd,env,*,reads=()):
    root=Path(root).resolve();cwd=Path(cwd).resolve();backend=sandbox_backend()
    if not backend:raise PermissionError('Isolamento non disponibile: installa bubblewrap su Linux o usa un macOS con sandbox-exec. Nessun comando avviato senza isolamento.')
    runtime=root/'runtime';runner=root/'native'
    allowed=[runtime/'python',runner/'agent-computer-runner.py',*map(Path,reads)]
    if sys.platform=='darwin':return [backend,'-p',mac_profile(allowed,[cwd]),*map(str,argv)]
    # Empty mount namespace: no host /home, /run, /tmp, credentials or sockets.
    # --unshare-all includes network + PID isolation. No privileged fallback.
    args=[backend,'--die-with-parent','--new-session','--unshare-all','--unshare-user','--cap-drop','ALL','--proc','/proc','--dev','/dev','--tmpfs','/tmp']
    for name in ('/usr','/bin','/sbin','/lib','/lib64'):
        p=Path(name)
        if p.exists():args+=['--ro-bind',name,name]
    for name in ('/etc/ld.so.cache','/etc/localtime','/etc/fonts'):
        if Path(name).exists():args+=['--ro-bind',name,name]
    for p in allowed:
        if p.exists():args+=['--ro-bind',str(p.resolve()),str(p.resolve())]
    args+=['--bind',str(cwd),str(cwd),'--chdir',str(cwd),'--clearenv']
    for key,value in env.items():args+=['--setenv',key,value]
    return [*args,'--',*map(str,argv)]


def run(root,argv,cwd,env,stdin,stdout,timeout=600,*,sandbox=None,reads=(),cancel=None,max_file_mb=64):
    if os.name=='nt':raise ValueError('POSIX broker cannot run on Windows.')
    if sandbox:argv=sandbox_command(root,argv,sandbox,env,reads=reads)
    if sys.platform=='darwin':
        guard=Path(root)/'runtime/tools/h3-process-guard'
        if not guard.is_file():raise PermissionError('Il supervisore processi macOS non è installato: nessun comando avviato.')
        argv=[str(guard),*map(str,argv)]
    elif sys.platform.startswith('linux') and not sandbox:
        backend=sandbox_backend()
        if not backend:raise PermissionError('Installa bubblewrap per supervisionare anche i processi figli in Globale.')
        # Full ordinary-user filesystem/network access, separate PID namespace
        # solely for reliable Stop of detached children. No host root privileges.
        argv=[backend,'--die-with-parent','--new-session','--unshare-pid','--bind','/','/','--proc','/proc','--dev-bind','/dev','/dev','--chdir',str(cwd),'--',*map(str,argv)]
    if sys.platform.startswith('linux'):
        argv=['/usr/bin/prlimit','--core=0','--fsize='+str(max_file_mb*1024**2),'--nofile=256','--as='+str(8*1024**3),'--',*map(str,argv)]
    with open(stdin,'rb') as source,open(stdout,'wb') as output:
        # Do not pass host data/log file descriptors through Seatbelt. Only
        # anonymous pipes cross the boundary; the broker owns the actual files.
        child=subprocess.Popen(list(map(str,argv)),cwd=cwd,env=env,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,start_new_session=True)
        import threading
        overflow=threading.Event()
        def feed():
            try:
                while block:=source.read(65536):child.stdin.write(block);child.stdin.flush()
            except (BrokenPipeError,OSError):pass
            finally:child.stdin.close()
        def collect():
            size=0
            try:
                while block:=child.stdout.read(65536):
                    size+=len(block)
                    if size>4*1024**2:overflow.set();break
                    output.write(block);output.flush()
            except OSError:pass
        feeder=threading.Thread(target=feed,daemon=True);reader=threading.Thread(target=collect,daemon=True)
        feeder.start();reader.start()
        def terminate(*_):
            # Give the Mac kqueue supervisor time to kill children in other
            # sessions; SIGKILL on its process group alone would miss those.
            try:
                os.kill(child.pid,signal.SIGTERM)
                child.wait(timeout=2)
            except subprocess.TimeoutExpired:
                try:os.killpg(child.pid,signal.SIGKILL)
                except ProcessLookupError:pass
            except ProcessLookupError:pass
        previous={}
        # The engine's Stop terminates the broker: always kill its process group.
        if threading.current_thread() is threading.main_thread():
            def interrupted(signum,frame):terminate();raise InterruptedError('Esecuzione fermata.')
            for sig in (signal.SIGTERM,signal.SIGINT):previous[sig]=signal.signal(sig,interrupted)
        try:
            deadline=time.monotonic()+timeout
            while child.poll() is None:
                if cancel and cancel.is_set():raise InterruptedError('Esecuzione fermata.')
                if time.monotonic()>deadline:raise TimeoutError('Comando oltre il tempo massimo.')
                if overflow.is_set():raise ValueError('Uscita oltre 4 MiB.')
                time.sleep(.05)
            return child.returncode
        finally:
            terminate()
            child.wait(timeout=5)
            feeder.join(timeout=2);reader.join(timeout=2);child.stdout.close()
            for sig,handler in previous.items():signal.signal(sig,handler)

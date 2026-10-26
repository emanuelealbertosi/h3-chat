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
           '(allow file-read* (subpath "/System") (subpath "/usr/lib") (subpath "/usr/share") (subpath "/bin") (subpath "/usr/bin") (subpath "/dev") (literal "/private/etc/localtime"))',
           '(allow file-write* (literal "/dev/null"))']
    for path in reads:parts.append('(allow file-read* (subpath '+quoted(path)+'))')
    for path in writes:parts.append('(allow file-read* file-write* (subpath '+quoted(path)+'))')
    return '\n'.join(parts)


def sandbox_command(root,argv,cwd,env,*,reads=()):
    root=Path(root).resolve();cwd=Path(cwd).resolve();backend=sandbox_backend()
    if not backend:raise PermissionError('Isolamento non disponibile: installa bubblewrap su Linux o usa un macOS con sandbox-exec. Nessun comando avviato senza isolamento.')
    runtime=root/'runtime';runner=root/'native'
    allowed=[runtime/'python',runner/'agent-computer-runner.py',*map(Path,reads)]
    if sys.platform=='darwin':return [backend,'-p',mac_profile(allowed,[cwd]),*map(str,argv)]
    # Empty mount namespace: no host /home, /run, /tmp, credentials or sockets.
    # --unshare-all includes network + PID isolation. No privileged fallback.
    args=[backend,'--die-with-parent','--new-session','--unshare-all','--cap-drop','ALL','--proc','/proc','--dev','/dev','--tmpfs','/tmp']
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


def run(root,argv,cwd,env,stdin,stdout,timeout=600,*,sandbox=None,reads=(),cancel=None):
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
    # The broker is single-threaded. Resource limits are inherited by children.
    def limits():
        import resource
        resource.setrlimit(resource.RLIMIT_CORE,(0,0))
        resource.setrlimit(resource.RLIMIT_FSIZE,(64*1024**2,64*1024**2))
        resource.setrlimit(resource.RLIMIT_NOFILE,(256,256))
        if sys.platform.startswith('linux'):resource.setrlimit(resource.RLIMIT_AS,(8*1024**3,8*1024**3))
    with open(stdin,'rb') as source,open(stdout,'wb') as output:
        child=subprocess.Popen(list(map(str,argv)),cwd=cwd,env=env,stdin=source,stdout=output,stderr=output,start_new_session=True,preexec_fn=limits)
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
        import threading
        if threading.current_thread() is threading.main_thread():
            def interrupted(signum,frame):terminate();raise InterruptedError('Esecuzione fermata.')
            for sig in (signal.SIGTERM,signal.SIGINT):previous[sig]=signal.signal(sig,interrupted)
        try:
            deadline=time.monotonic()+timeout
            while child.poll() is None:
                if cancel and cancel.is_set():raise InterruptedError('Esecuzione fermata.')
                if time.monotonic()>deadline:raise TimeoutError('Comando oltre il tempo massimo.')
                if Path(stdout).stat().st_size>4*1024**2:raise ValueError('Uscita oltre 4 MiB.')
                time.sleep(.05)
            return child.returncode
        finally:
            terminate()
            child.wait(timeout=5)
            for sig,handler in previous.items():signal.signal(sig,handler)

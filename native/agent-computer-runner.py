"""File/code endpoint running inside the same restricted token as its children."""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

if os.name=='nt' and 'H3_DRIVE_MAP' in os.environ:
    import ctypes as C
    from ctypes import wintypes as W
    import ntpath
    k=C.WinDLL('kernel32',use_last_error=True)
    k.CreateFileW.argtypes=[W.LPCWSTR,W.DWORD,W.DWORD,C.c_void_p,W.DWORD,W.DWORD,W.HANDLE];k.CreateFileW.restype=W.HANDLE
    k.GetFinalPathNameByHandleW.argtypes=[W.HANDLE,W.LPWSTR,W.DWORD,W.DWORD];k.GetFinalPathNameByHandleW.restype=W.DWORD
    k.CloseHandle.argtypes=[W.HANDLE];k.CloseHandle.restype=W.BOOL
    original_path=ntpath._getfinalpathname
    def canonical_path(path):
        try:return original_path(path)
        except PermissionError:
            handle=k.CreateFileW(path,0,7,None,3,0x02000000,None)
            if handle==C.c_void_p(-1).value:raise C.WinError(C.get_last_error())
            try:
                buffer=C.create_unicode_buffer(32768);length=k.GetFinalPathNameByHandleW(handle,buffer,len(buffer),2)
                if not length or length>=len(buffer):raise C.WinError(C.get_last_error())
                devices=json.loads(os.environ['H3_DRIVE_MAP'])
                for drive,device in devices.items():
                    if buffer.value.casefold().startswith(device.casefold()+'\\'):
                        return '\\\\?\\'+drive+buffer.value[len(device):]
                raise ValueError('Volume canonico non riconosciuto.')
            finally:k.CloseHandle(handle)
    ntpath._getfinalpathname=canonical_path

def digest(path):
    if path.stat().st_size>64*1024**2:raise ValueError('File oltre 64 MB: usa un comando per lavorarlo senza leggerlo nel prompt.')
    return hashlib.sha256(path.read_bytes()).hexdigest()

def run(request):
    args=request['args'];root=Path(request['root']) if request['scope']=='sandbox' else None
    def path(value,default=False):
        if not isinstance(value,str) or '\0' in value or value.startswith(('\\\\?\\','\\\\.\\')):raise ValueError('Percorso non valido.')
        if root:
            if not value and default:return root
            # LPAC is the authority; these checks give precise errors too.
            if Path(value).is_absolute() or ':' in value or '..' in value.replace('\\','/').split('/'):raise PermissionError('Usa percorsi relativi alla cartella Sandbox.')
            p=(root/value).resolve()
            if not p.is_relative_to(root.resolve()):raise PermissionError('Percorso fuori dalla cartella Sandbox.')
            return p
        p=Path(value)
        if not p.is_absolute():raise ValueError('In Globale indica il percorso assoluto.')
        return p
    def protect(p):
        if root and p==root:raise PermissionError('La cartella principale non può essere cancellata o sostituita.')
        if p==p.parent:raise PermissionError('Operazione non consentita sulla radice del disco.')
    def verify(p):
        actual=digest(p)
        if args.get('expected_sha256')!=actual:raise ValueError('Prima leggi il file e usa il suo SHA256 aggiornato. Nessuna modifica applicata.')
    if request['op'] in ('transfer_read','transfer_write'):
        import base64
        p=path(args['path'])
        if request['op']=='transfer_read':
            if p.stat().st_size>20*1024**2:raise ValueError('File oltre 20 MiB.')
            raw=p.read_bytes();return {'name':p.name,'sha256':hashlib.sha256(raw).hexdigest(),'data':base64.b64encode(raw).decode('ascii')}
        protect(p)
        if p.exists():raise ValueError('File di destinazione già presente: nessuna sovrascrittura.')
        raw=base64.b64decode(args['data'],validate=True)
        if len(raw)>20*1024**2:raise ValueError('File oltre 20 MiB.')
        p.parent.mkdir(parents=True,exist_ok=True)
        with p.open('xb') as stream:stream.write(raw)
        return {'exported':True,'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}
    if request['op']=='computer_files':
        p=path(args['path'],True);op=args['operation']
        if op=='list':
            rows=[]
            for item in p.iterdir():
                if len(rows)>=500:break
                try:rows.append({'name':item.name,'directory':item.is_dir(),'size':item.stat().st_size})
                except OSError:continue
            return {'entries':rows,'limit':500}
        if op=='read':return {'text':p.read_bytes()[:32000].decode('utf8',errors='replace'),'sha256':digest(p),'bytes':p.stat().st_size,'truncated':p.stat().st_size>32000}
        if op=='search':
            rows=[];visited=0
            for base,dirs,files in os.walk(p,followlinks=False):
                for name in files:
                    visited+=1
                    if visited>5000 or len(rows)>=100:return {'matches':rows,'truncated':True}
                    candidate=Path(base)/name
                    try:
                        if args.get('find','').casefold() in name.casefold():rows.append({'path':str(candidate.relative_to(root)) if root else str(candidate),'name_match':True});continue
                        if candidate.stat().st_size>1024**2:continue
                        for n,line in enumerate(candidate.read_text(encoding='utf8').splitlines(),1):
                            if args.get('find','').casefold() in line.casefold():rows.append({'path':str(candidate.relative_to(root)) if root else str(candidate),'line':n,'text':line[:300]});break
                    except (OSError,UnicodeError):continue
            return {'matches':rows,'truncated':False}
        protect(p)
        if op=='mkdir':p.mkdir(parents=True,exist_ok=True);return {'created':True}
        if op in ('write','replace'):
            text=args.get('text','')
            if p.exists():
                verify(p)
                if op=='replace':
                    old=p.read_text(encoding='utf8');find=args.get('find')
                    if not find or old.count(find)!=1:raise ValueError('La parte da sostituire deve apparire esattamente una volta.')
                    text=old.replace(find,text,1)
                backup=p.with_name(p.name+'.h3-backup-'+args['expected_sha256'][:12])
                if not backup.exists():shutil.copyfile(p,backup)
            elif op=='replace':raise ValueError('File inesistente.')
            p.parent.mkdir(parents=True,exist_ok=True)
            # Opening under the AppContainer token makes a swapped junction fail closed.
            with p.open('w' if p.exists() else 'x',encoding='utf8',newline='\n') as stream:stream.write(text)
            return {'written':True,'sha256':digest(p),'bytes':p.stat().st_size}
        if op=='remove':
            if p.is_dir():p.rmdir()
            else:verify(p);p.unlink()
            return {'removed':True}
        if op in ('copy','move'):
            target=path(args.get('target',''));protect(target)
            if target.exists():raise ValueError('La destinazione esiste già: nessuna sovrascrittura.')
            if p.is_dir():raise ValueError('Copia/sposta singoli file; nessuna modifica ricorsiva implicita.')
            if op=='move':verify(p);p.rename(target)
            else:shutil.copyfile(p,target)
            return {'completed':True,'sha256':digest(target)}
        raise ValueError('Operazione file sconosciuta.')
    if request['op']=='computer_run':
        engine=args['engine'];cwd=path(args.get('workdir',''),True) if root else path(args.get('workdir') or os.environ['USERPROFILE'])
        if root and engine=='powershell':raise PermissionError('Windows PowerShell 5 non è compatibile con il confine Sandbox senza COM. Usa Python, cmd o un programma nella cartella; PowerShell resta disponibile in Globale.')
        system=Path(os.environ.get('SystemRoot','C:/Windows'))/'System32'
        if engine=='python':argv=[sys.executable,'-I','-X','utf8','-c',args.get('code','')]
        elif engine=='shell':
            if os.name=='nt':raise ValueError('Su Windows usa cmd o PowerShell.')
            argv=['/bin/sh','-c',args.get('code','')]
        elif engine=='powershell':
            if os.name!='nt':raise ValueError('PowerShell è Windows; usa shell su Mac/Linux.')
            argv=[str(system/'WindowsPowerShell/v1.0/powershell.exe'),'-NoProfile','-NonInteractive','-Command',args.get('code','')]
        elif engine=='cmd':
            if os.name!='nt':raise ValueError('cmd è Windows; usa shell su Mac/Linux.')
            argv=[str(system/'cmd.exe'),'/D','/S','/C',args.get('code','')]
        else:argv=[str(path(args.get('executable',''))),*args.get('arguments',[])]
        import time,uuid
        out=cwd/'.h3-tmp'/('command-'+uuid.uuid4().hex+'.log');out.parent.mkdir(exist_ok=True)
        null=cwd/'.h3-tmp'/'stdin-empty';null.touch(exist_ok=True)
        try:
            with null.open('rb') as inp,out.open('wb') as stream:
                process=subprocess.Popen(argv,cwd=cwd,stdin=inp,stdout=stream,stderr=stream)
                deadline=time.monotonic()+args.get('timeout',60)
                try:
                    while process.poll() is None:
                        if time.monotonic()>deadline:raise TimeoutError('Tempo massimo del comando raggiunto.')
                        if out.stat().st_size>4*1024**2:raise ValueError('Uscita del comando oltre 4 MB.')
                        time.sleep(.1)
                finally:
                    if process.poll() is None:process.kill();process.wait()
            with out.open('rb') as stream:raw=stream.read(32000)
            encoding='utf-16-le' if b'\0' in raw[:100] else 'utf8'
            return {'exit_code':process.returncode,'output':raw.decode(encoding,errors='replace'),'truncated':out.stat().st_size>32000,'executed':True}
        finally:out.unlink(missing_ok=True)
    raise ValueError('Operazione computer sconosciuta.')

if __name__=='__main__':
    try:print(json.dumps({'result':run(json.load(sys.stdin))},ensure_ascii=False))
    except Exception as error:print(json.dumps({'error':str(error),'type':type(error).__name__},ensure_ascii=False));sys.exit(1)

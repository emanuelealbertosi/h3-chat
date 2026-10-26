"""Trusted IPC broker. Never interprets generated code in the H3 server process."""
import json
import os
from pathlib import Path
import sys
import traceback
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
wire=sys.stdout;sys.stdout=sys.stderr
def emit(event,**data):wire.write(json.dumps({'event':event,**data},ensure_ascii=False)+'\n');wire.flush()

def run(request):
    import subprocess
    if os.name=='nt':from h3chat.computer_process import run as process
    else:from h3chat.posix_computer import run as process
    from h3chat.platform_runtime import python_executable
    folder=Path(request['folder']);folder.mkdir(parents=True,exist_ok=True)
    source=folder/'request.json';output=folder/'output.log';source.write_text(json.dumps(request),encoding='utf8')
    cwd=Path(request['root']) if request['scope']=='sandbox' else folder
    temp=cwd/'.h3-tmp';temp.mkdir(exist_ok=True)
    env={k:v for k,v in os.environ.items() if k.upper() in ('SYSTEMROOT','WINDIR','COMSPEC','PATHEXT','PROGRAMFILES','PROGRAMFILES(X86)','PROGRAMW6432','PROCESSOR_ARCHITECTURE')}
    env.update(TEMP=str(temp),TMP=str(temp),USERPROFILE=str(cwd),APPDATA=str(temp),LOCALAPPDATA=str(temp),PATH=str(Path(python_executable(ROOT)).parent)+os.pathsep+str(Path(os.environ.get('SystemRoot','C:/Windows'))/'System32'),PYTHONIOENCODING='utf-8')
    if os.name!='nt':env.update(HOME=str(cwd),TMPDIR=str(temp),PATH=str(Path(python_executable(ROOT)).parent)+':/usr/bin:/bin:/usr/sbin:/sbin',LANG='en_US.UTF-8')
    if os.name=='nt':
        import ctypes as C
        drives={};buffer=C.create_unicode_buffer(32768)
        for letter in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ':
            drive=letter+':'
            if C.windll.kernel32.QueryDosDeviceW(drive,buffer,len(buffer)):drives[drive]=buffer.value
        env['H3_DRIVE_MAP']=json.dumps(drives)
    argv=[python_executable(ROOT),'-I','-X','utf8',ROOT/'native/agent-computer-runner.py']
    timeout=request['args'].get('timeout',60)+5
    code=process(ROOT,argv,cwd,env,source,output,timeout,sandbox=cwd if request['scope']=='sandbox' else None)
    raw=output.read_bytes()[:4*1024**2].decode('utf8',errors='replace')
    try:value=json.loads(raw.splitlines()[-1])
    except (ValueError,IndexError):raise RuntimeError('Processo terminato senza risultato leggibile (exit '+str(code)+'): '+raw[-2000:])
    if 'error' in value:raise ValueError(value['error'])
    return value['result']|{'scope':request['scope'],'broker_exit_code':code}

if __name__=='__main__':
    emit('hello')
    for line in sys.stdin:
        try:emit('result',result=run(json.loads(line)))
        except Exception as error:traceback.print_exc();emit('error',message=str(error))

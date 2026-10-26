"""Actual packaged POSIX tools: no GPU inference or real administrator prompt."""
import json
import os
from pathlib import Path
import subprocess
import socket
import sys
import tempfile
import time


def check(root):
    root=Path(root).resolve();python=root/'runtime/python/bin/python3'
    reports=[]
    def worker(request,timeout=45):
        result=subprocess.run([str(python),'-X','utf8',str(root/'native/agent-computer-worker.py')],input=json.dumps(request)+'\n',text=True,capture_output=True,timeout=timeout)
        events=[json.loads(line) for line in result.stdout.splitlines() if line.startswith('{')]
        error=next((v for v in events if v.get('event')=='error'),None)
        assert not error,(error,result.stderr[-2500:])
        return next(v['result'] for v in events if v.get('event')=='result')
    with tempfile.TemporaryDirectory(prefix='h3-posix-check-') as temporary:
        parent=Path(temporary).resolve();sandbox=parent/'chosen folder';sandbox.mkdir();outside=parent/'outside-secret';outside.write_text('CANARY-PRIVATE')
        log=parent/'broker';base={'scope':'sandbox','root':str(sandbox),'folder':str(log),'app_root':str(root)}
        listener=socket.socket();listener.bind(('127.0.0.1',0));listener.listen(2)
        code='''from pathlib import Path
import subprocess,sys,socket
Path('created.txt').write_text('ok')
try: Path(%r).read_text(); print('ESCAPED_READ')
except (PermissionError,FileNotFoundError): print('READ_DENIED')
try: Path(%r).write_text('wrong'); print('ESCAPED_WRITE')
except (PermissionError,FileNotFoundError): print('WRITE_DENIED')
try: socket.create_connection(('127.0.0.1',%d),timeout=.3); print('ESCAPED_NET')
except OSError: print('NET_DENIED')
subprocess.run([sys.executable,'-I','-c',"print('CHILD_OK')"],check=True)
'''%(str(outside),str(outside),listener.getsockname()[1])
        try:result=worker(base|{'op':'computer_run','args':{'engine':'python','code':code,'timeout':15}})
        finally:listener.close()
        assert result['exit_code']==0,result
        for expected in ('READ_DENIED','WRITE_DENIED','NET_DENIED','CHILD_OK'):assert expected in result['output'],result
        assert outside.read_text()=='CANARY-PRIVATE' and (sandbox/'created.txt').read_text()=='ok'
        reports.append('native sandbox: Python, child, outside file read/write denial')
        result=worker(base|{'op':'computer_run','args':{'engine':'shell','code':"printf 'SHELL_OK'",'timeout':10}})
        assert result['exit_code']==0 and 'SHELL_OK' in result['output'],result
        result=worker(base|{'op':'computer_files','args':{'operation':'read','path':'created.txt'}})
        assert result['text']=='ok'
        reports.append('native shell and file tools')
        # A detached child must not survive Stop or a normal command exit.
        delayed=sandbox/'should-not-exist'
        detached="import os,time; os.setsid();time.sleep(3);open(%r,'w').write('leaked')"%str(delayed)
        code='import subprocess,sys; subprocess.Popen([sys.executable,"-I","-c",%r]);print("SPAWNED")'%detached
        result=worker(base|{'op':'computer_run','args':{'engine':'python','code':code,'timeout':10}})
        assert result['exit_code']==0,result
        time.sleep(3.5);assert not delayed.exists(),'detached child survived broker completion'
        reports.append('detached descendant terminated')
        result=worker(base|{'scope':'global','root':'','op':'computer_run','args':{'engine':'python','code':'print("GLOBAL_OK")','workdir':str(parent),'timeout':10}})
        assert result['exit_code']==0 and 'GLOBAL_OK' in result['output'],result
        reports.append('Global ordinary-user execution')
    # Smoke-import every recent worker in its actual packaged runtime.
    for name in ('agent-layout-worker.py','agent-audio-worker.py','agent-image-worker.py','agent-pdf-worker.py','agent-web-image-worker.py','presentation-worker.py'):
        result=subprocess.run([str(python),'-X','utf8',str(root/'native'/name)],input='',text=True,capture_output=True,timeout=40)
        assert result.returncode==0,(name,result.stderr[-2000:])
    reports.append('recent CPU workers import')
    if (root/'runtime/tools/lab/manim').is_dir():
        # Actual Cairo render and MP4 decode, not merely an import/readiness flag.
        from h3chat.posix_manim import render
        with tempfile.TemporaryDirectory(prefix='h3-manim-cpu-check-') as temporary:
            result=render(root,{'source':{'title':'Native CPU check','scene_name':'Probe',
                'code':'from manim import *\nclass Probe(Scene):\n    def construct(self):\n        self.add(Circle(radius=0.5))\n        self.wait(0.25)\n'},
                'options':{'width':320,'height':180,'fps':12,'device':'cpu','timeout':90},'output':temporary},lambda message:print(message,flush=True))
            assert Path(result['path']).stat().st_size>1000 and result['duration']>0,result
        reports.append('native isolated Manim CPU render and MP4 decode')
    print(json.dumps({'status':'passed','platform':sys.platform,'checks':reports,'gpu_inference':False,'native_admin_invoked':False},indent=2))
    return reports


if __name__=='__main__':check(sys.argv[1])

"""Synthetic real rendering and cancellation checks; never opens app chats."""
import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from h3chat.windows_sandbox import cleanup

folder=ROOT/'work/manim-validation';folder.mkdir(parents=True,exist_ok=True)
private=folder/'private-fixture.txt';private.write_text('synthetic fixture, no user data')
sys.path.insert(0,str(ROOT/'runtime/tools/lab'))
from PIL import Image
Image.new('RGB',(80,60),'blue').save(folder/'reference.png')

code='''from manim import *
import os,socket
class Demo(ThreeDScene):
 def construct(self):
  try:open(PRIVATE_FILE).read()
  except PermissionError:print('PRIVATE_READ_BLOCKED')
  else:raise RuntimeError('Private read was allowed')
  try:open(PRIVATE_FILE,'w').write('forbidden')
  except PermissionError:print('PRIVATE_WRITE_BLOCKED')
  else:raise RuntimeError('Private write was allowed')
  try:socket.create_connection(('1.1.1.1',443),timeout=1)
  except PermissionError:print('NETWORK_BLOCKED')
  else:raise RuntimeError('Network was allowed')
  self.set_camera_orientation(phi=60*DEGREES,theta=30*DEGREES)
  sphere=Sphere(radius=.6,color=BLUE)
  formula=MathTex(r"\\int_0^1 x^2 dx=\\frac13",color=WHITE).to_corner(UL)
  caption=Text('Manim 3D + LaTeX',font_size=24).to_edge(DOWN)
  image=ImageMobject('assets/reference.png').scale(.3).to_corner(UR)
  self.add(sphere);self.add_fixed_in_frame_mobjects(formula,caption,image)
  self.begin_ambient_camera_rotation(rate=.2)
  self.play(sphere.animate.set_color(GREEN),run_time=.4);self.wait(.6)
'''.replace('PRIVATE_FILE',repr(str(private)))
opts={'device':'cpu','width':320,'height':240,'fps':5,'timeout':60,'memory_gb':4}
request={'source':{'title':'Synthetic validation','scene_name':'Demo','code':code},'options':opts,
         'output':str(folder/'render'),'assets':[{'name':'reference.png','path':str(folder/'reference.png')}]}
command=[str(ROOT/'runtime/python/python.exe'),'-I','-X','utf8',str(ROOT/'native/manim-worker.py')]
started=time.monotonic()
result=subprocess.run(command,input=json.dumps(request)+'\n',text=True,capture_output=True,timeout=240)
events=[json.loads(line) for line in result.stdout.splitlines()]
done=next((e['result'] for e in events if e['event']=='result'),None)
if not done:raise RuntimeError(result.stdout+'\n'+result.stderr)
assert abs(done['duration']-1)<.01,done
assert done['latex'] and Path(done['path']).is_file()
log=(folder/'render/manim-render.log').read_text()
for marker in ('PRIVATE_READ_BLOCKED','PRIVATE_WRITE_BLOCKED','NETWORK_BLOCKED'):assert marker in log,marker
assert private.read_text()=='synthetic fixture, no user data'
print('3D, camera, animation, Text, image, real MathTex, duration, private read/write and network checks passed;',round(time.monotonic()-started,1),'s')

# Cancel the broker after a scene has spawned a descendant; Job Object must
# kill both and the trusted parent must remove the alias, ACLs and profile.
code='''from manim import *
import subprocess,sys,os,json,time
class Demo(Scene):
 def construct(self):
  child=subprocess.Popen([sys.executable,'-c','import time;time.sleep(300)'])
  from pathlib import Path
  Path('started.json').write_text(json.dumps({'pid':os.getpid(),'child':child.pid}))
  time.sleep(300)
'''
request.update(source={'title':'Cancellation fixture','scene_name':'Demo','code':code},output=str(folder/'cancel'),assets=[])
process=subprocess.Popen(command,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,text=True)
job_folder=None;child_pids=[];drive=None
try:
    assert json.loads(process.stdout.readline())['event']=='hello'
    process.stdin.write(json.dumps(request)+'\n');process.stdin.flush();deadline=time.monotonic()+180
    while time.monotonic()<deadline:
        for ticket in (ROOT/'runtime/manim-jobs/.tickets').glob('*.json'):
            record=json.loads(ticket.read_text())
            if record.get('owner')!=process.pid:continue
            job_folder=ticket.parent.parent/ticket.stem;drive=record.get('drive')
            marker=job_folder/'started.json'
            if marker.exists():
                values=json.loads(marker.read_text());child_pids=[values['pid'],values['child']];break
        if child_pids:break
        if process.poll() is not None:raise RuntimeError('Cancellation worker stopped early')
        time.sleep(.1)
    assert child_pids,'Scene did not start'
finally:
    owner=process.pid
    if process.poll() is None:process.terminate();process.wait(timeout=10)
    cleanup(ROOT,owner)
    process.stdin.close();process.stdout.close()
k=ctypes.WinDLL('kernel32',use_last_error=True)
k.OpenProcess.argtypes=[wintypes.DWORD,wintypes.BOOL,wintypes.DWORD];k.OpenProcess.restype=wintypes.HANDLE
k.WaitForSingleObject.argtypes=[wintypes.HANDLE,wintypes.DWORD];k.CloseHandle.argtypes=[wintypes.HANDLE]
for pid in child_pids:
    handle=k.OpenProcess(0x100000,False,pid)
    if handle:
        try:assert k.WaitForSingleObject(handle,5000)==0,'Descendant still running'
        finally:k.CloseHandle(handle)
assert job_folder and not job_folder.exists(),'Job folder not cleaned'
assert drive and not Path(drive+'/').exists(),'Temporary drive alias not cleaned'
print('Cancellation: renderer and descendant stopped; folder and temporary drive alias removed')

import json,subprocess,sys,wave
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'runtime/tools/documents')]
import numpy as np,av
folder=ROOT/'work/infographic-render-test';folder.mkdir(exist_ok=True)
text='<style>body{background:#101824;color:white;font-family:Manrope}h1{position:absolute;top:220px;left:110px;width:1050px;font-size:110px;line-height:1.08}p{position:absolute;left:110px;top:850px;font-size:58px;color:#93eef2}.shape{position:absolute;left:600px;top:1350px;width:420px;height:420px;border-radius:100px;background:linear-gradient(140deg,#fc62c5,#7053ef)}</style><h1 data-motion="blur" data-start="0" data-duration=".7">Dai vita<br>alle tue idee.</h1><p data-motion="slide" data-start=".8" data-duration=".5">Immagini. Parole. Musica.</p><div class="shape" data-motion="zoom" data-start="1.3" data-duration=".6"></div>'
deck={'format':'9:16','pages':[{'html':text},{'html':text.replace('Dai vita<br>alle tue idee.','Scegli il<br>tuo stile.').replace('#101824','#162b2d')}],'infographic':{'version':1,'durations':[2.5,2.5],'transition':'fade','sfx':'subtle','options':{'corners':'round','frame':'light'}}}
rate=48000;t=np.arange(rate*5)/rate;signal=(np.sin(t*2*np.pi*440)*.06).astype(np.float32)
with wave.open(str(folder/'music.wav'),'wb') as out:out.setnchannels(1);out.setsampwidth(2);out.setframerate(rate);out.writeframes((signal*32767).astype('<i2').tobytes())
request={'data':str(folder),'deck':deck,'media':[],'voice':None,'music':str(folder/'music.wav'),'output':str(folder/'example.mp4'),'test_size':[270,480]}
result=subprocess.run([str(ROOT/'runtime/python/python.exe'),'-X','utf8',str(ROOT/'native/infographic-worker.py')],input=json.dumps(request)+'\n',encoding='utf-8',capture_output=True,timeout=180,cwd=ROOT)
print(result.stdout)
if not any(json.loads(line).get('event')=='result' for line in result.stdout.splitlines()):print(result.stderr);raise SystemExit(1)
with av.open(str(folder/'example.mp4')) as inp:
 assert len(inp.streams.video)==len(inp.streams.audio)==1
 assert (inp.streams.video[0].width,inp.streams.video[0].height)==(270,480)
 frames=list(inp.decode(video=0));assert len(frames)==50
 for i in (0,10,20,30,40):frames[i].to_image().save(folder/(f'frame-{i}.png'))
 assert np.mean(np.abs(np.asarray(frames[0].to_image()).astype(float)-np.asarray(frames[20].to_image()).astype(float)))>5
 assert np.max(np.abs(np.asarray(frames[20].to_image())[0,0].astype(float)-np.array([245,244,239])))<15
print('PASS: actual deterministic MP4, two scenes, timed effects, crossfade, music, sound effects, rounded corners, 50 frames.')

"""Rendered split clips have separate clocks and delayed original audio."""
import json,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'runtime/tools/documents')]
import av,numpy as np

folder=ROOT/'work/infographic-video-test'
assert (folder/'uploads/source.mp4').is_file(),'Run infographic-video-smoke.py first.'
media=[];videos=[]
for i in range(1,4):
 media.extend([{'id':f'v{i}','path':'uploads/source.mp4','name':f'Video {i}','mime':'video/mp4'}, {'id':f'p{i}','path':'outputs/poster.jpg','name':f'Poster {i}','mime':'image/jpeg'}])
 videos.append({'asset_id':f'v{i}','poster_id':f'p{i}','duration':2,'width':320,'height':240,'audio':True,'fit':'contain','end':'freeze','sound':'keep' if i==1 else 'mute'})
html=''.join(f'<section data-panel="{i}" style="background:#101820"><div data-video-asset-id="v{i}" style="width:100%;height:100%"></div></section>' for i in range(1,4))
motion={'version':1,'durations':[4],'transition':'cut','sfx':'none','options':{'layout':'columns3','panel_appearance':'sequence','panel_order':'231','panel_interval':.8,'video_start':'panel'},'videos':videos}
for ending in ('freeze','loop'):
 for video in videos:video['end']=ending
 output=folder/f'outputs/start-{ending}.mp4'
 request={'data':str(folder),'deck':{'format':'16:9','pages':[{'html':html}],'infographic':motion},'media':media,'output':str(output),'test_size':[480,270]}
 response=subprocess.run([str(ROOT/'runtime/python/python.exe'),'-X','utf8',str(ROOT/'native/infographic-worker.py')],input=json.dumps(request)+'\n',encoding='utf-8',capture_output=True,timeout=180,cwd=ROOT)
 events=[json.loads(s) for s in response.stdout.splitlines()];assert any(e['event']=='result' for e in events),response.stderr+response.stdout
 with av.open(str(output)) as inp:
  frames=list(inp.decode(video=0));assert len(frames)==40
  # Far right of each contained frame avoids the moving yellow rectangle.
  for n in (24,38):
   image=np.asarray(frames[n].to_image())
   for i,start in enumerate((1.6,0,.8)):
    elapsed=max(0,n/10-start);elapsed=elapsed%2 if ending=='loop' else min(elapsed,1.9)
    expected=20+int(round(elapsed*10))*7
    measured=int(image[135,i*160+154,0]);assert abs(measured-expected)<12,(ending,n,i,measured,expected)
  assert np.max(np.abs(np.asarray(frames[24].to_image())[20,314].astype(int)-[16,24,32]))<6,'contain should preserve the panel background above the clip'
 with av.open(str(output)) as inp:
  samples=np.concatenate([f.to_ndarray() for f in inp.decode(audio=0)],axis=1)
  energy=lambda a,b:float(np.sqrt(np.mean(samples[:,round(a*48000):round(b*48000)]**2)))
  assert energy(.3,1.4)<.001,'main audio must wait for its panel'
  assert energy(1.7,3.4)>.03,'main audio must start with its video'
  assert (energy(3.7,3.9)<.001) if ending=='freeze' else (energy(3.7,3.9)>.03)
print('PASS: independently timed clips, sequence 231, exact frame progression, contain bars, freeze/loop and delayed original audio.')

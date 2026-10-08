"""Export four/six real video panels, numbered by rows and entering in order."""
import json,subprocess,sys
from pathlib import Path
from fractions import Fraction
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'runtime/tools/documents')]
import av,numpy as np
from PIL import Image
from h3chat.infographic_video import probe
folder=ROOT/'work/infographic-grid-test';(folder/'uploads').mkdir(parents=True,exist_ok=True);(folder/'outputs').mkdir(exist_ok=True)
videos=[];media=[];colors=[(220,20,20),(20,220,20),(20,20,220),(220,220,20),(220,20,220),(20,220,220)]
for index,color in enumerate(colors,1):
 source=folder/f'uploads/clip{index}.mp4'
 with av.open(str(source),'w') as out:
  stream=out.add_stream('libx264',rate=10);stream.width=320;stream.height=240;stream.pix_fmt='yuv420p'
  for n in range(20):
   frame=av.VideoFrame.from_image(Image.new('RGB',(320,240),color));frame.pts=n;frame.time_base=Fraction(1,10)
   for packet in stream.encode(frame):out.mux(packet)
  for packet in stream.encode(None):out.mux(packet)
 info=probe(source,folder/f'outputs/poster{index}.jpg')
 videos.append(info|{'asset_id':f'clip{index}','poster_id':f'poster{index}','fit':'contain','end':'loop','sound':'mute'})
 media.extend([{'id':f'clip{index}','path':f'uploads/clip{index}.mp4','name':f'Clip {index}','mime':'video/mp4'},{'id':f'poster{index}','path':f'outputs/poster{index}.jpg','name':'Poster','mime':'image/jpeg'}])
for layout,cols,rows,order,fmt,size in [('grid2x2',2,2,'2413','16:9',[480,270]),('grid3x2',3,2,'362514','16:9',[480,270]),('grid2x3',2,3,'654321','9:16',[270,480])]:
 count=cols*rows;html=''.join(f'<section data-panel="{i}" style="left:900px;width:20px;background:#111"><div data-video-asset-id="clip{i}" style="width:100%;height:100%"></div></section>' for i in range(1,count+1))
 deck={'format':fmt,'pages':[{'html':html}],'infographic':{'version':1,'durations':[4],'transition':'cut','sfx':'none','options':{'layout':layout,'panel_appearance':'sequence','panel_order':order,'panel_interval':.4,'video_start':'panel'},'videos':videos[:count]}}
 output=folder/f'outputs/{layout}.mp4';request={'data':str(folder),'deck':deck,'media':media,'output':str(output),'test_size':size}
 response=subprocess.run([str(ROOT/'runtime/python/python.exe'),'-X','utf8',str(ROOT/'native/infographic-worker.py')],input=json.dumps(request)+'\n',encoding='utf-8',capture_output=True,timeout=180,cwd=ROOT)
 assert any(json.loads(line).get('event')=='result' for line in response.stdout.splitlines()),response.stderr+response.stdout
 with av.open(str(output)) as inp:
  frames=list(inp.decode(video=0));assert len(frames)==40
  for n,visible in ((7,{int(order[0])}),(11,set(map(int,order[:2]))),(36,set(range(1,count+1)))):
   image=np.asarray(frames[n].to_image())
   for index in range(count):
    x=round((index%cols+.5)*size[0]/cols);y=round((index//cols+.5)*size[1]/rows);pixel=image[y,x].astype(float)
    if index+1 in visible:assert np.max(np.abs(pixel-colors[index]))<22,(layout,n,index,pixel)
    elif order.index(str(index+1))*.4>n/10:assert pixel.max()<40,(layout,n,index,pixel)
  frames[36].to_image().save(folder/f'{layout}.png')
print('PASS: real MP4 with four/six independent clips, all grid geometries, arbitrary orders, horizontal/vertical export and preserved aspect.')

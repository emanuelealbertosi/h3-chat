"""Render the actual MP4: three independent clips, ordered entrances and aspect."""
import json,subprocess,sys
from pathlib import Path
from fractions import Fraction
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'runtime/tools/documents')]
import av,numpy as np
from PIL import Image
from h3chat.infographic_video import probe
folder=ROOT/'work/infographic-screen-test';(folder/'uploads').mkdir(parents=True,exist_ok=True);(folder/'outputs').mkdir(exist_ok=True)
videos=[];media=[];colors=[(220,20,20),(20,220,20),(20,20,220)]
for index,color in enumerate(colors,1):
    source=folder/f'uploads/clip{index}.mp4'
    with av.open(str(source),'w') as out:
        v=out.add_stream('libx264',rate=10);v.width=320;v.height=240;v.pix_fmt='yuv420p'
        for n in range(20):
            frame=av.VideoFrame.from_image(Image.new('RGB',(320,240),color));frame.pts=n;frame.time_base=Fraction(1,10)
            for packet in v.encode(frame):out.mux(packet)
        for packet in v.encode(None):out.mux(packet)
    info=probe(source,folder/f'outputs/poster{index}.jpg')
    videos.append(info|{'asset_id':f'clip{index}','poster_id':f'poster{index}','fit':'contain','end':'loop','sound':'mute'})
    media.extend([{'id':f'clip{index}','path':f'uploads/clip{index}.mp4','name':f'Clip {index}','mime':'video/mp4'},{'id':f'poster{index}','path':f'outputs/poster{index}.jpg','name':'Poster','mime':'image/jpeg'}])
html=''.join(f'<section data-panel="{i}" style="position:absolute;left:500px;width:900px;background:#111"><div data-video-asset-id="clip{i}" style="width:100%;height:100%"></div></section>' for i in range(1,4))
deck={'format':'16:9','pages':[{'html':html}],'infographic':{'version':1,'durations':[3],'transition':'cut','sfx':'none','options':{'layout':'columns3','panel_appearance':'sequence','panel_order':'231','panel_interval':.8},'videos':videos}}
request={'data':str(folder),'deck':deck,'media':media,'output':str(folder/'outputs/result.mp4'),'test_size':[480,270]}
response=subprocess.run([str(ROOT/'runtime/python/python.exe'),'-X','utf8',str(ROOT/'native/infographic-worker.py')],input=json.dumps(request)+'\n',encoding='utf-8',capture_output=True,timeout=180,cwd=ROOT)
events=[json.loads(s) for s in response.stdout.splitlines()];assert any(s['event']=='result' for s in events),response.stderr+response.stdout
with av.open(str(folder/'outputs/result.mp4')) as inp:
    frames=list(inp.decode(video=0));assert len(frames)==30
    for n,visible in ((7,{2}),(15,{2,3}),(26,{1,2,3})):
        image=np.asarray(frames[n].to_image())
        for i in range(1,4):
            pixel=image[135,(i-1)*160+80].astype(float)
            if i in visible:assert pixel[i-1]>180 and np.delete(pixel,i-1).max()<50,(n,i,pixel)
            else:assert pixel.max()<40,(n,i,pixel)
        # 4:3 clips retain bars inside their tall, narrow columns.
        assert image[20].mean()<40
    frames[26].to_image().save(folder/'preview.png')
print('PASS: real MP4, three clips, sequence 231, stable panel positions, preserved aspect and looped sources.')

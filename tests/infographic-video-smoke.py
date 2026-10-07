"""Actual decoded moving background, continuous scenes, audio loop and aspect."""
import json,subprocess,sys,io,base64,math
from pathlib import Path
from fractions import Fraction
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'runtime/tools/documents')]
import av,numpy as np
from PIL import Image,ImageDraw
from h3chat.infographic_video import probe,Frames
folder=ROOT/'work/infographic-video-test';(folder/'uploads').mkdir(parents=True,exist_ok=True);(folder/'outputs').mkdir(exist_ok=True)
with av.open(str(folder/'uploads/source.mp4'),'w') as out:
    v=out.add_stream('libx264',rate=10);v.width=320;v.height=240;v.pix_fmt='yuv420p'
    a=out.add_stream('aac',rate=48000);a.layout='stereo'
    for n in range(20):
        image=Image.new('RGB',(320,240),(20+n*7,40,80));ImageDraw.Draw(image).rectangle((n*10,70,n*10+40,170),fill='#ffe060')
        frame=av.VideoFrame.from_image(image);frame.pts=n;frame.time_base=Fraction(1,10)
        for p in v.encode(frame):out.mux(p)
        t=(np.arange(4800)+n*4800)/48000;sound=np.tile((np.sin(t*2*np.pi*440)*.1).astype(np.float32),(2,1));frame=av.AudioFrame.from_ndarray(sound,format='fltp',layout='stereo');frame.sample_rate=48000;frame.pts=n*4800;frame.time_base=Fraction(1,48000)
        for p in a.encode(frame):out.mux(p)
    for p in v.encode(None):out.mux(p)
    for p in a.encode(None):out.mux(p)
info=probe(folder/'uploads/source.mp4',folder/'outputs/poster.jpg');video=info|{'asset_id':'source','poster_id':'poster','fit':'contain','end':'loop','sound':'keep'}
decoder=Frames(folder/'uploads/source.mp4',video)
try:
    first=np.asarray(decoder.image(.5));loop=np.asarray(decoder.image(2.5));assert np.abs(first.astype(float)-loop.astype(float)).mean()<1
finally:decoder.close()
media=[{'id':'source','path':'uploads/source.mp4','name':'Source','mime':'video/mp4'},{'id':'poster','path':'outputs/poster.jpg','name':'Poster','mime':'image/jpeg'}]
html='<h1 data-motion="fade" data-start="0" data-duration=".3" style="color:white;font:90px Manrope;margin:100px">Video allegato</h1>'
deck={'format':'9:16','pages':[{'html':html},{'html':html}],'infographic':{'version':1,'durations':[3,3],'transition':'cut','sfx':'none','options':{},'video':video}}
request={'data':str(folder),'deck':deck,'media':media,'output':str(folder/'outputs/result.mp4'),'test_size':[270,480]}
response=subprocess.run([str(ROOT/'runtime/python/python.exe'),'-X','utf8',str(ROOT/'native/infographic-worker.py')],input=json.dumps(request)+'\n',encoding='utf-8',capture_output=True,timeout=180,cwd=ROOT)
events=[json.loads(s) for s in response.stdout.splitlines()];assert any(s['event']=='result' for s in events),response.stderr+response.stdout
with av.open(str(folder/'outputs/result.mp4')) as inp:
    frames=list(inp.decode(video=0));assert len(frames)==60
    first=np.asarray(frames[5].to_image());repeat=np.asarray(frames[25].to_image());assert np.abs(first.astype(float)-repeat.astype(float)).mean()<3
    assert np.abs(first.astype(float)-np.asarray(frames[15].to_image()).astype(float)).mean()>3
    # An entire 4:3 source retains black bars in the 9:16 frame.
    assert first[-30:].mean()<40;frames[15].to_image().save(folder/'preview.png')
with av.open(str(folder/'outputs/result.mp4')) as inp:
    samples=np.concatenate([f.to_ndarray() for f in inp.decode(audio=0)],axis=1);assert np.sqrt(np.mean(samples[:,-48000:]**2))>.03
print('PASS: actual moving MP4, preserved aspect, source audio through loops, continuous scene timeline, bounded decoder.')

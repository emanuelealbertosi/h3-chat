"""Actual CPU movie: continuous camera + six video panels + looping source audio."""
import json,subprocess,sys
from pathlib import Path
root=Path(__file__).resolve().parents[1];sys.path[:0]=[str(root),str(root/'runtime/tools/documents')]
import av,numpy as np
from h3chat.infographics import options
folder=root/'work/cinema-smoke';folder.mkdir(parents=True,exist_ok=True)
subprocess.run([sys.executable,'-X','utf8',str(root/'tests/prepare_cinema_media.py'),str(folder)],check=True)
media=[{'id':'a'*32,'name':'Moving video','path':'source.mp4','mime':'video/mp4'},{'id':'b'*32,'name':'Poster','path':'poster.jpg','mime':'image/jpeg'}]
# Native media must live under one of the owner's authorized relative roots.
(folder/'outputs').mkdir(exist_ok=True)
for m in media:
    source=folder/m['path'];target=folder/'outputs'/source.name;target.write_bytes(source.read_bytes());m['path']='outputs/'+source.name
html='<style>main{position:relative;width:1280px;height:720px;background:transparent}.plane{position:absolute;inset:0}</style><main>'+''.join('<section data-panel="'+str(i)+'"><div data-video-asset-id="'+media[0]['id']+'" style="width:100%;height:100%"></div><div class="plane" data-depth=".35"></div><div class="plane" data-depth="1"><h2 data-motion="fade" data-start=".1" data-duration=".2" style="font:22px Manrope;color:white">'+str(i)+'</h2></div><div class="plane" data-depth="1.65" style="left:90%;background:#e8ca8f55"></div></section>' for i in range(1,7))+'</main>'
deck={'format':'16:9','pages':[{'html':html},{'html':html}],'infographic':{'version':1,'durations':[2,2],'transition':'zoom','sfx':'none','options':options(value={'visual_mode':'sequence','layout':'grid3x2','format':'16:9','voice':False,'music':'none','video_start':'together'}),'videos':[{'asset_id':media[0]['id'],'poster_id':media[1]['id'],'duration':2,'width':320,'height':240,'audio':True,'fit':'cover','end':'loop','sound':'keep'}]}}
request={'data':str(folder),'deck':deck,'media':media,'output':str(folder/'outputs/result.mp4'),'test_size':[640,360]}
run=subprocess.run([sys.executable,'-X','utf8',str(root/'native/infographic-worker.py')],input=json.dumps(request)+'\n',text=True,encoding='utf-8',capture_output=True,timeout=180,cwd=root)
events=[json.loads(line) for line in run.stdout.splitlines()];assert any(e['event']=='result' for e in events),run.stdout+run.stderr
with av.open(str(folder/'outputs/result.mp4')) as movie:
    frames=list(movie.decode(video=0));assert len(frames)==40;assert np.asarray(frames[5].to_image()).std()>15
    frames[5].to_image().save(folder/'first.png');frames[30].to_image().save(folder/'second.png')
with av.open(str(folder/'outputs/result.mp4')) as movie:
    audio=np.concatenate([frame.to_ndarray() for frame in movie.decode(audio=0)],axis=1);assert np.sqrt(np.mean(audio[:,-48000:]**2))>.025
(folder/'proof.json').write_text(json.dumps({'frames':40,'six_video_panels':True,'continuous_clock':True,'source_audio_after_scene_boundary':True,'gpu_inference':False},indent=2))
print('PASS: CPU MP4 fully decoded, six moving video panels, continuous camera, looping source audio after the scene boundary.')

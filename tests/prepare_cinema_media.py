"""Small synthetic CPU-only MP4 and poster for the disposable browser fixture."""
import sys,subprocess
from pathlib import Path
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root/'runtime/tools/documents'))
import av
import numpy as np
from fractions import Fraction
from PIL import Image,ImageDraw
folder=Path(sys.argv[1]);folder.mkdir(parents=True,exist_ok=True)
picture=Image.new('RGB',(320,240),'#347d79');ImageDraw.Draw(picture).ellipse((80,40,240,200),fill='#e8ca8f');picture.save(folder/'poster.jpg')
with av.open(str(folder/'source.mp4'),'w') as movie:
    stream=movie.add_stream('libx264',rate=10);stream.width=320;stream.height=240;stream.pix_fmt='yuv420p';audio=movie.add_stream('aac',rate=48000);audio.layout='stereo'
    for i in range(20):
        image=picture.copy();ImageDraw.Draw(image).rectangle((i*8,0,i*8+10,240),fill='#ffffff')
        for packet in stream.encode(av.VideoFrame.from_image(image)):movie.mux(packet)
        t=(np.arange(4800)+i*4800)/48000;sound=np.tile((np.sin(t*2*np.pi*440)*.1).astype(np.float32),(2,1));frame=av.AudioFrame.from_ndarray(sound,format='fltp',layout='stereo');frame.sample_rate=48000;frame.pts=i*4800;frame.time_base=Fraction(1,48000)
        for packet in audio.encode(frame):movie.mux(packet)
    for packet in stream.encode():movie.mux(packet)
    for packet in audio.encode():movie.mux(packet)

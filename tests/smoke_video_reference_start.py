"""CPU-only decoder regression with long-GOP footage and known timed colours."""
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
if os.name=='nt':dll=os.add_dll_directory(str(ROOT/'runtime/vision/dlls'))
sys.path[:0]=[str(ROOT),str(ROOT/'runtime/vision/packages')]
from h3chat.video_reference import decode_source

with tempfile.TemporaryDirectory() as tmp:
    video=Path(tmp)/'timed-colours.mp4'
    subprocess.run([str(ROOT/'runtime/remix/ffmpeg.exe'),'-v','error','-y',
        '-f','lavfi','-i','color=black:s=64x36:r=24:d=330',
        '-vf',"drawbox=c=red:t=fill:enable='gte(t,315)*lt(t,316)',drawbox=c=blue:t=fill:enable='gte(t,316)'",
        '-c:v','libx264','-g','1000','-pix_fmt','yuv420p',str(video)],check=True,capture_output=True)
    frames,thumbnails,info=decode_source({'path':str(video),'start':315,'frames':360,'megapixels':.2})
    for number,channel in ((0,0),(23,0),(24,2),(359,2)):
        pixel=frames[number,18,32]
        assert pixel[channel]>.9,(number,pixel)
        assert pixel[(channel+1)%3]<.1,(number,pixel)
    assert info['start']==315 and info['frames']==360
    assert thumbnails[0,18,32,0]>.9
    print('OK: first second starts exactly at 315; transition at 316; final frame at 329.958; CPU only.')

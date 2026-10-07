"""Exercise the actual streaming mux with deliberately unequal narration timings."""
import ast,json,subprocess,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

class SceneMuxTests(unittest.TestCase):
    @unittest.skipUnless((ROOT/'runtime/python/python.exe').is_file() and (ROOT/'runtime/tools/documents/av/__init__.py').is_file(),'Portable PyAV not installed')
    def test_each_clip_changes_at_its_own_measured_voice_boundary(self):
        # Red and blue clips both last two seconds, but their spoken scenes last
        # one and three seconds. A global retime would cut at the wrong point.
        code=r'''
import ast,json,math,os,sys,wave
from pathlib import Path
from fractions import Fraction
root=Path(sys.argv[1]);folder=Path(sys.argv[2]);sys.path.insert(0,str(root/'runtime/tools/documents'))
dll=os.add_dll_directory(str(root/'runtime/tools/documents')) if os.name=='nt' else None
import av
for name,color in [('red',(240,0,0)),('blue',(0,0,240))]:
    with av.open(str(folder/(name+'.mp4')),'w') as out:
        stream=out.add_stream('libx264',rate=20);stream.width=64;stream.height=64;stream.pix_fmt='yuv420p'
        for i in range(40):
            frame=av.VideoFrame(64,64,'rgb24');frame.planes[0].update(bytes(color)*64*64);frame.pts=i;frame.time_base=Fraction(1,20)
            for packet in stream.encode(frame):out.mux(packet)
        for packet in stream.encode(None):out.mux(packet)
with wave.open(str(folder/'voice.wav'),'wb') as sound:
    sound.setnchannels(1);sound.setsampwidth(2);sound.setframerate(24000);sound.writeframes(bytes(4*24000*2))
tree=ast.parse((root/'native/media-compose-worker.py').read_text());nodes=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in ('probe','compose')]
scope={'Path':Path,'math':math,'Fraction':Fraction,'emit':lambda *a,**k:None}
exec(compile(ast.Module(body=nodes,type_ignores=[]),'media-compose-worker.py','exec'),scope)
clips=[str(folder/(name+'.mp4')) for name in ('red','blue')]
result=scope['compose'](clips,str(folder/'voice.wav'),str(folder/'result.mp4'),durations=[1,3])
assert result['frames']==80 and result['synchronization']=='per-scene'
silent=scope['compose'](clips,None,str(folder/'silent.mp4'),durations=[1,3])
assert silent['frames']==80 and not silent['audio_preserved']
with av.open(str(folder/'silent.mp4')) as source:
    assert not source.streams.audio
    silent_frames=list(source.decode(video=0))
    assert len(silent_frames)==80
    assert bytes(silent_frames[19].reformat(format='rgb24').planes[0])[0]>200
    assert bytes(silent_frames[20].reformat(format='rgb24').planes[0])[2]>200
with av.open(str(folder/'result.mp4')) as source:
    frames=list(source.decode(video=0));assert len(frames)==80
    red_count=0
    for frame in frames:
        rgb=frame.reformat(format='rgb24');pixel=bytes(rgb.planes[0])[:3]
        red_count+=pixel[0]>pixel[2]
    assert red_count==20,red_count
for durations in ([2,1],[1,0],[float('nan'),3],[4]):
    try:scope['compose'](clips,str(folder/'voice.wav'),str(folder/'invalid.mp4'),durations=durations)
    except ValueError:pass
    else:raise AssertionError('Invalid narration timings accepted')
print(json.dumps({'frames':80,'red_frames':red_count,'blue_frames':80-red_count,'scene_boundary_seconds':1,'invalid_timings_rejected':True}))
'''
        with tempfile.TemporaryDirectory() as tmp:
            result=subprocess.run([str(ROOT/'runtime/python/python.exe'),'-X','utf8','-c',code,str(ROOT),tmp],capture_output=True,text=True,encoding='utf-8',timeout=120)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertEqual(json.loads(result.stdout)['red_frames'],20)

if __name__=='__main__':unittest.main()

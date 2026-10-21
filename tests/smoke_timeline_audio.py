"""CPU integration: imported audio tails and cut soundtrack sample boundaries."""
import json,math,struct,subprocess,wave
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
FOLDER=ROOT/'work/timeline-audio-qa';FOLDER.mkdir(parents=True,exist_ok=True)
source=FOLDER/'source.wav';rate=48000
with wave.open(str(source),'wb') as f:
    f.setnchannels(2);f.setsampwidth(2);f.setframerate(rate)
    f.writeframes(b''.join(struct.pack('<hh',*(2*[round(10000*math.sin(2*math.pi*(440 if i<rate else 880)*i/rate))])) for i in range(round(2.96*rate))))
def run(op,**extra):
    body={'op':op,'runtime':{'backend':'cpu','threads':4},'source':str(source),'folder':str(FOLDER),**extra}
    p=subprocess.run([str(ROOT/'runtime/python/python.exe'),'-X','utf8',str(ROOT/'native/video-remix-worker.py')],input=json.dumps(body),text=True,capture_output=True,cwd=ROOT,timeout=90)
    events=[json.loads(line) for line in p.stdout.splitlines() if line.startswith('{')]
    assert p.returncode==0,(events,p.stderr[-2500:])
    return next(x['result'] for x in events if x['event']=='result')
assert abs(run('pad_import_audio',duration=3)['padded_seconds']-.04)<1/rate
with wave.open(str(source),'rb') as f:
    assert f.getnframes()==3*rate
    f.setpos(round(2.96*rate));assert not any(f.readframes(1920))
assert run('pad_import_audio',duration=3)['padded_seconds']==0
output=FOLDER/'cut.wav'
run('timeline_audio',output=str(output),intervals=[{'start':0,'duration':.5},{'start':2,'duration':.5}])
with wave.open(str(output),'rb') as f:
    assert f.getnframes()==rate
    data=struct.unpack('<'+'h'*(f.getnframes()*2),f.readframes(f.getnframes()))[::2]
    def crossings(values):return sum(a<=0<b for a,b in zip(values,values[1:]))
    assert abs(crossings(data[:24000])-220)<=1
    assert abs(crossings(data[24000:])-440)<=1
print('PASS: 40 ms import padding, idempotent repair, exact retained audio ranges and 1-second output.')

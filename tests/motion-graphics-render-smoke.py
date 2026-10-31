"""Actual CPU-only P0 export; no Service/Store, model, credentials or production data."""
import argparse,json,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'runtime/tools/documents')]
from h3chat.platform_runtime import python_executable
from h3chat.slides import encode,validate_content
import av

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output-dir',type=Path,default=ROOT/'work/motion-graphics-p0');parser.add_argument('--deck',type=Path);args=parser.parse_args()
    folder=args.output_dir.resolve();folder.mkdir(parents=True,exist_ok=True)
    graph=json.loads((ROOT/'tests/fixtures/motion-scene-v2.json').read_text(encoding='utf8'))
    deck={'version':1,'engine':'llm','format':'16:9','title':'Motion Graphics P0','theme':'lagoon','typography':'modern','design':'professional','detail':'concise','references':[],
          'pages':[{'title':'Tre oggetti indipendenti','status':'ready','html':'<main style="width:100%;height:100%">Motion Graphics</main>','notes':'Fixture originale, senza inferenza AI e senza voce.','sources':[],'motion_scene':graph}],
          'infographic':{'version':1,'scene_format_version':2,'durations':[10],'transition':'cut','sfx':'none','options':{'format':'16:9','duration':10,'scenes':1,'voice':False,'music':'none','images':'provided'}}}
    if args.deck:deck=json.loads(args.deck.read_text(encoding='utf8'))
    duration=sum(deck['infographic']['durations']);frames=round(duration*30)
    validate_content(encode(deck),[])
    (folder/'deck.json').write_text(json.dumps(deck,ensure_ascii=False,indent=2),encoding='utf8')
    request={'data':str(folder),'deck':deck,'media':[],'voice':None,'music':None,'output':str(folder/'demo.mp4')}
    result=subprocess.run([str(python_executable(ROOT)),'-X','utf8',str(ROOT/'native/infographic-worker.py')],input=json.dumps(request)+'\n',encoding='utf8',capture_output=True,timeout=240,cwd=ROOT)
    (folder/'worker.log').write_text(result.stdout+'\n'+result.stderr,encoding='utf8')
    events=[json.loads(line) for line in result.stdout.splitlines() if line.startswith('{')]
    if result.returncode or not any(e.get('event')=='result' for e in events):raise RuntimeError('Actual motion export failed; inspect '+str(folder/'worker.log'))
    count=0;samples={}
    with av.open(str(folder/'demo.mp4')) as media:
        video=media.streams.video[0];width,height=video.width,video.height;fps=float(video.average_rate)
        for frame in media.decode(video=0):
            if count in (0,135,299,435,735,frames-1):
                path=folder/('frame-'+str(count)+'.png');frame.to_image().save(path);samples[str(count)]=str(path)
            count+=1
    assert (width,height,fps,count)==(1920,1080,30,frames),(width,height,fps,count)
    proof={'passed':True,'native_cpu_render':True,'gpu_models':0,'llm_calls':0,'tts_calls':0,'frames_decoded':count,'duration':count/fps,'width':width,'height':height,'fps':fps,'output':str(folder/'demo.mp4'),'sample_frames':samples}
    (folder/'proof.json').write_text(json.dumps(proof,indent=2),encoding='utf8');print(json.dumps(proof))

if __name__=='__main__':main()

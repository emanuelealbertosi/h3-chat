"""Read H3 status without constructing Service/Store or changing jobs."""
import argparse,json,re,sqlite3,sys,urllib.request,urllib.error
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from h3_root import find_root

def inspect(root=None,job=None):
    root=find_root(root);data=root/'data';result={'root':str(root)}
    try:
        port=json.loads((data/'port.json').read_text(encoding='utf-8'))
        req=urllib.request.Request(f'http://127.0.0.1:{port}/api/maintenance/state',headers={'X-H3-Token':(data/'maintenance-token.txt').read_text(encoding='ascii').strip()})
        with urllib.request.urlopen(req,timeout=5) as r:state=json.load(r)
        result['server']={'available':True,'port':port,'active_jobs':[{k:j.get(k) for k in ('id','status','stage')} for j in state.get('jobs',[]) if j.get('status') in ('queued','running')], 'active_downloads':[{k:d.get(k) for k in ('id','status')} for d in state.get('downloads',[]) if d.get('status') in ('queued','running')]}
    except (OSError,ValueError,urllib.error.URLError) as exc:
        result['server']={'available':False,'reason':type(exc).__name__,'note':'Do not assume the queue is empty when the server cannot be reached.'}
    if job:
        if not re.fullmatch('[a-f0-9]{32}',job):raise ValueError('Expected exact 32-character job ID.')
        dbfile=data/'chat.sqlite'
        with sqlite3.connect(dbfile.as_uri()+'?mode=ro',uri=True) as db:
            db.row_factory=sqlite3.Row
            row=db.execute('SELECT id,chat_id,status,stage FROM jobs WHERE id=?',(job,)).fetchone()
        result['job']=dict(row) if row else {'id':job,'found':False,'note':'Check the correct authenticated workspace; do not resubmit.'}
        folder=data/'outputs'/job;checkpoint=folder/'scenes.json'
        if checkpoint.is_file():
            r=json.loads(checkpoint.read_text(encoding='utf-8'))
            result['checkpoint']={'path':str(checkpoint),'clip_count':len(r.get('timeline',[])),'base_completed':r.get('completed'),'note':'For a revision, base_completed describes the inherited timeline; new progress is revision_completed.','revision_completed':r.get('revision_completed'),'source':r.get('revision_source'),'final_frames':list(r.get('revision_end_frames',{})), 'revision_generated':{n:{'path':v.get('path'),'memory':v.get('generation',{}).get('visual_memory_recovered'),'width':v.get('generation',{}).get('width'),'height':v.get('generation',{}).get('height'),'duration':v.get('generation',{}).get('duration')} for n,v in r.get('revision_generated',{}).items()}}
        result['movie']={'path':str(folder/'video.mp4'),'exists':(folder/'video.mp4').is_file()}
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',help='Cartella H3-Chat; altrimenti H3_CHAT_ROOT, skill inclusa o progetto corrente.');p.add_argument('--job');a=p.parse_args()
    try:print(json.dumps(inspect(a.root,a.job),ensure_ascii=False,indent=2))
    except Exception as exc:raise SystemExit(type(exc).__name__+': '+str(exc))

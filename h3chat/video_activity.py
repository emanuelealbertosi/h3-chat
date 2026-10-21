"""Read-only, bounded activity summaries; never expose raw model logs/prompts."""
import json
import re
import time
from pathlib import Path


def tail(path,limit=2_000_000):
    try:
        with Path(path).open('rb') as stream:
            stream.seek(0,2);size=stream.tell();stream.seek(max(0,size-limit))
            return stream.read().decode('utf-8','replace')
    except OSError:return ''


def snapshot(data,job,*,server_log):
    payload=json.loads(job['payload']);settings=payload.get('settings',{});edit=settings.get('_video_edit',{})
    selected=[p['clip'] for p in edit.get('patches',[])];folder=Path(data)/'outputs'/job['id']
    try:record=json.loads((folder/'scenes.json').read_text(encoding='utf-8'))
    except (OSError,ValueError):record={}
    events=[];planning=None;generating=None
    pattern=re.compile(r'^(\d{2}:\d{2}:\d{2}) \[(?:INFO|WARNING|ERROR)\] Lavoro '+re.escape(job['id'][:8])+r' · (.+)$')
    for line in tail(server_log).splitlines():
        match=pattern.match(line)
        if not match:continue
        clock,label=match.groups()
        if not label.startswith(('Post-produzione','Assistant','Video','LongTakeNoCuts','Generazione video','Riutilizzo modello','Caricamento','Motore','Richiesta')):continue
        plan=re.search(r'istruzioni clip (\d+)',label)
        clip=re.search(r'Post-produzione · clip (\d+)',label)
        if plan:planning=int(plan[1]);generating=None
        if clip:generating=int(clip[1])
        if not events or events[-1]['label']!=label:events.append({'time':clock,'label':label[:400]})
    complete=record.get('revision_completed',[]) if 'revision_request' in record else list(range(1,record.get('completed',0)+1))
    total=len(selected) or len(record.get('timeline',[]))
    display=job['stage'];phase='preparation';active=generating or planning
    if job['status'] in ('done','failed','cancelled','interrupted'):phase=job['status']
    elif generating:
        phase='generation';display=f'Generazione · clip {generating}'+(f' di {total}' if selected==list(range(1,total+1)) else '')
    elif planning:
        phase='instructions';display=f'Preparazione istruzioni · clip {planning}'+(f' di {total}' if selected==list(range(1,total+1)) else '')
    if 'rimont' in job['stage'].lower() or 'montaggio' in job['stage'].lower():phase='assembly';display=job['stage']
    signals=[]
    for path in [Path(data)/'logs'/(job['id']+'.log'),*folder.glob('scene-*/engine.log')]:
        try:signals.append(path.stat().st_mtime)
        except OSError:pass
    return {'job_id':job['id'],'status':job['status'],'stage':display,'detail':job['stage'],'phase':phase,
        'active_clip':active,'clips_total':total,'clips_completed':len(complete),
        'instructions_saved':len(record.get('revision_plans',{})),
        'created_at':job['created'],'updated_at':time.time(),'last_signal_at':max(signals,default=None),
        'error':job.get('error',''),'events':events[-80:]}


def describe(app,chat_id,ident):
    app.store.chat(chat_id)
    if not isinstance(ident,str) or not re.fullmatch('[a-f0-9]{32}',ident):raise ValueError('Lavoro non valido.')
    job=app.store.one('SELECT id,status,stage,error,created,payload FROM jobs WHERE id=? AND chat_id=?',(ident,chat_id))
    if not job:raise ValueError('Lavoro non trovato in questa chat.')
    return snapshot(app.data,dict(job),server_log=app.data/'server.log')

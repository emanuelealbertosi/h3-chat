"""Owner-requested, queued single-block diagnosis of a saved edit recipe."""
import copy
import json
import re
from .downloads import safe_join


def original(app, chat_id, ident):
    app.store.chat(chat_id)
    if not isinstance(ident,str) or not re.fullmatch('[a-f0-9]{32}',ident):raise ValueError('Richiesta video diagnostica non valida.')
    row=app.store.one('SELECT id,payload FROM jobs WHERE id=? AND chat_id=?',(ident,chat_id))
    if not row:raise ValueError('La richiesta video non appartiene a questa chat.')
    payload=json.loads(row['payload']);command=payload.get('settings',{}).get('_video_edit',{})
    patches=command.get('patches',[])
    if len(patches)!=1 or patches[0].get('mode')!='video':raise ValueError('La diagnosi richiede una singola modifica video salvata.')
    number=patches[0]['clip'];path=safe_join(app.data,f'outputs/{ident}/scene-{number:03d}/video-plan.json')
    saved=json.loads(path.read_text(encoding='utf-8'))
    if saved.get('parameters',{}).get('attention')!='veda':raise ValueError('La richiesta originale non utilizzava VEDA.')
    return payload,saved


def request(app, chat_id, body):
    if not isinstance(body,dict) or set(body)!={'source_job','head_chunks'} or type(body['head_chunks']) is not int or body['head_chunks'] not in (8,56):
        raise ValueError('Scegli una richiesta salvata e 8 oppure 56 gruppi VEDA.')
    payload,_=original(app,chat_id,body['source_job'])
    settings=copy.deepcopy(payload['settings'])
    for key in ('_video_edit','_video_resume','_video_recreate','_video_resume_origin'):settings.pop(key,None)
    settings['_video_probe']=dict(body)
    with app.lock:
        ident=app.store.enqueue(chat_id,f'Diagnostica VEDA · un blocco · {body["head_chunks"]} gruppi',payload['media'],settings,False,[])
        app.wake.set()
    return {'job_id':ident,'intent':'video'}


def render(app, job, payload, settings, cancel, stage, log_path):
    command=settings['_video_probe'];source_payload,saved=original(app,job['chat_id'],command['source_job'])
    original_edit=source_payload['settings']['_video_edit'];patch=original_edit['patches'][0]
    from .video_edit import source,source_interval
    from . import video_versions
    value=source(app,job['chat_id'],original_edit['source'],original_edit.get('segment_seconds'))
    versions=video_versions.choices(app,job['chat_id'],original_edit['source'],value,original_edit.get('versions'))
    video_versions.apply(value,versions,app.data)
    source_video=source_interval(value,patch)
    images=[x for x in source_payload['media'] if x['mime'].startswith('image/')]
    refs=[images[n-1] for n in patch['images']]
    audios=[x for x in source_payload['media'] if x['mime'].startswith('audio/')]
    for ordinal in sorted({a['index'] for a in saved['plan']['audios']}):
        if ordinal!=1 or not audios:raise ValueError('La traccia originale diagnostica non è disponibile.')
    model=app.engine.require_model(source_payload['settings']['video_model'],'video')
    options=copy.deepcopy(saved['parameters']);options['attention_chunks']=command['head_chunks']
    folder=app.data/'outputs'/job['id'];folder.mkdir(parents=True,exist_ok=True)
    (folder/'sampling-diagnostics.json').write_text(json.dumps({'first_block_probe':True}),encoding='utf-8')
    request={'op':'generate','output':str(folder/'probe-not-a-video.mp4'),'plan':saved['plan'],'options':options,
             'format_prompt':options['aspect'],'forced_aspect':options['aspect'],
             'images':[str(safe_join(app.data,x['path'])) for x in refs],
             'audios':[str(safe_join(app.data,x['path'])) for x in audios],
             'source_video':source_video|{'path':str(safe_join(app.data,source_video['path']))},
             'sequence':job['id'],'scene_index':0,'audio_tail_padding':True}
    meta={'intent':'video','model':model['name'],'execution_mode':'Diagnostica GPU · solo primo blocco',
          'video_probe':command,'references':refs+audios}
    app.store.update_answer(job,'',meta=meta)
    stage('Diagnostica VEDA · caricamento e condizionamento')
    try:
        session=app.engine.start_video(model,source_payload['settings'],log_path,cancel,stage=stage)
        session.send(request)
        result=session.wait('diagnostic_done',cancel,1200,stage)
    finally:
        app.engine.stop()
    meta['video_probe_result']=result['parameters']
    app.store.update_answer(job,'Diagnostica VEDA completata sul primo blocco. Nessun filmato è stato generato.','done',[],meta)
    app.store.execute("UPDATE jobs SET status='done',stage='Diagnostica primo blocco completata' WHERE id=?",(job['id'],))

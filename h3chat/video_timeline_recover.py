"""Recover pre-timeline clip-only revisions using their saved footage, without AI."""
import copy
import json
import re
from .downloads import Cancelled, safe_join
from .video_edit import source, validate_edits, install_clip, finish_segments
from .video_resume import checkpoint, save


def legacy(app,chat_id,ident):
    app.store.chat(chat_id)
    if not isinstance(ident,str) or not re.fullmatch(r'[a-f0-9]{32}',ident):
        raise ValueError('Timeline da recuperare non valida.')
    row=app.store.one("SELECT j.payload,m.meta FROM jobs j JOIN messages m ON m.id=j.message_id WHERE j.id=? AND j.chat_id=? AND j.status='done' AND m.status='done'",(ident,chat_id))
    if not row:raise ValueError('Scegli gli spezzoni completati in questa chat.')
    saved=checkpoint(app.data,ident)
    if saved.get('working_timeline'):return {'ready':ident}
    if saved.get('revision_remount') is not False:raise ValueError('Questa richiesta non contiene spezzoni separati da recuperare.')
    value=source(app,chat_id,saved.get('revision_source'))
    payload=json.loads(row['payload']);meta=json.loads(row['meta'])
    refs=meta.get('references',payload['media'])
    for item in refs:
        if not safe_join(app.data,item['path']).is_file():raise ValueError('Un riferimento della timeline non è più disponibile.')
    value['images']=[r for r in refs if r['mime'].startswith('image/')]
    patches=validate_edits(saved.get('revision_request'),value)
    if set(saved.get('revision_completed',[]))!={p['clip'] for p in patches}:
        raise ValueError('Gli spezzoni della richiesta non sono tutti completati.')
    for patch in patches:
        key=str(patch['clip'])
        if key not in saved.get('revision_generated',{}) or key not in saved.get('revision_plans',{}):
            raise ValueError('Manca il file o la regia di uno spezzone da recuperare.')
    return {'value':value,'saved':saved,'patches':patches,'refs':refs,'meta':meta}


def request(app,chat_id,body):
    ident=body.get('source');value=legacy(app,chat_id,ident)
    if value.get('ready'):return {'timeline_id':value['ready']}
    # A repeated click reuses the existing recovery instead of queuing a duplicate.
    existing=app.store.one("SELECT id,status FROM jobs WHERE chat_id=? AND json_extract(payload,'$.settings._video_timeline_recover')=? AND status IN ('done','queued','running') ORDER BY created DESC LIMIT 1",(chat_id,ident))
    if existing:
        if existing['status']=='done':
            source(app,chat_id,existing['id']);return {'timeline_id':existing['id']}
        return {'job_id':existing['id'],'canvas':False}
    settings=app.store.settings()|{'_video_timeline_recover':ident,'_assistant':False,'_rag':False}
    queued=app.store.enqueue(chat_id,'Recupero della timeline dagli spezzoni già generati',[],settings,False)
    app.wake.set();return {'job_id':queued,'canvas':False}


def render(app,job,payload,settings,cancel,stage,log):
    ident=settings['_video_timeline_recover'];loaded=legacy(app,job['chat_id'],ident)
    if loaded.get('ready'):raise ValueError('La timeline è già pronta: usa Riprendi timeline sul risultato originale.')
    value=loaded['value'];saved=loaded['saved'];patches=loaded['patches']
    from .video_versions import catalog
    catalog(app,job['chat_id'],saved['revision_source'],value)
    from .video_import import prepare
    prepare(app,value,cancel,stage,log,clips=[p['clip'] for p in patches if 'start' in p])
    folder=app.data/'outputs'/job['id'];folder.mkdir(parents=True,exist_ok=True)
    record=copy.deepcopy(value['record'])
    record.update(working_timeline=True,recovered_revision=ident,model=saved['model'],
        revision_source=saved['revision_source'],revision_request=patches,revision_remount=False,
        revision_plans=copy.deepcopy(saved['revision_plans']),revision_generated=copy.deepcopy(saved['revision_generated']),revision_completed=[])
    if settings.get('_video_resume'):
        resumed=checkpoint(app.data,settings['_video_resume'])
        if resumed.get('recovered_revision')!=ident:raise ValueError('Il recupero salvato appartiene a una timeline diversa.')
        record=resumed
    save(folder,record)
    for patch in patches:
        if cancel.is_set():raise Cancelled()
        number=patch['clip']
        if number in record['revision_completed']:continue
        stage(f'Timeline · recupero dello spezzone {number}, senza generazione AI')
        item=copy.deepcopy(saved['revision_generated'][str(number)])
        path=safe_join(app.data,item['path']);p=value['record']['parameters'][number-1]
        shape=value.get('source_size') or p
        if value.get('source_size') or (item['generation'].get('width'),item['generation'].get('height'))!=(shape['width'],shape['height']):
            fitted=folder/f'fitted-{number:03d}.mp4'
            app.engine.tool_call('video-remix-worker.py',{'op':'fit_video','runtime':{'backend':'cpu','threads':4},
                'folder':str(folder),'source':str(path),'output':str(fitted),
                'width':shape['width']//2*2,'height':shape['height']//2*2},cancel,stage,log,timeout=600)
            path=fitted;item['path']=fitted.relative_to(app.data).as_posix()
            if not value.get('source_size'):item['generation'].update({k:p[k] for k in ('width','height','canvas_width','canvas_height','aspect') if k in p})
        install_clip(app,value,record,patch,item,path,folder,cancel,stage,log)
    finish_segments(app,job,payload,settings,value,record,patches,loaded['refs'],
        {'name':loaded['meta'].get('model','MiniMax H3')},folder,cancel,stage,log,recovered=True)

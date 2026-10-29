"""Import public pages, YouTube captions or an attached audio into this project."""
import re
from .downloads import safe_join,Cancelled
from .store import uid

def origin(app,project_id,source_id):
    app.knowledge.project(project_id)
    if not app.store.one("SELECT name FROM sqlite_master WHERE type='table' AND name='rag_media_origins'"):return {'media':None}
    row=app.store.one('SELECT media_id FROM rag_media_origins WHERE project_id=? AND source_id=?',(project_id,source_id))
    if not row:return {'media':None}
    try:item=app.validate_media([{'id':row['media_id']}],canvas=True)[0]
    except ValueError:return {'media':None}
    return {'media':{k:item[k] for k in ('id','name','path','mime')}}

def has_origin(app,project_id,source_id):
    if not app.store.one("SELECT name FROM sqlite_master WHERE type='table' AND name='rag_media_origins'"):return False
    return bool(app.store.one('SELECT source_id FROM rag_media_origins WHERE project_id=? AND source_id=?',(project_id,source_id)))

def enqueue_project(app,project_id,body):
    project=app.knowledge.project(project_id);chat_id=body.get('chat_id')
    if chat_id:
        if app.store.chat(chat_id).get('project_id')!=project_id:raise ValueError('La chat non appartiene a questo progetto.')
    else:
        row=app.store.one('SELECT id FROM chats WHERE project_id=? AND title=? AND archived=0 ORDER BY created LIMIT 1',(project_id,'Fonti · '+project['name']))
        chat_id=row['id'] if row else app.store.create_chat('Fonti · '+project['name'],project_id=project_id)['id']
    return enqueue(app,chat_id,body)|{'chat_id':chat_id}

def enqueue(app,chat_id,body):
    chat=app.store.chat(chat_id);project=chat.get('project_id')
    if not project:raise ValueError('Sposta la chat in un progetto prima di importare una fonte Studio.')
    app.knowledge.project(project);kind=body.get('kind');settings=app.effective_settings(app.store.settings());media=[]
    if kind not in ('web','youtube','audio'):raise ValueError('Tipo di fonte Studio non valido.')
    spec={'kind':kind,'project_id':project,'name':body.get('name','Fonte Studio')}
    if not isinstance(spec['name'],str) or not 1<=len(spec['name'].strip())<=150:raise ValueError('Nome della fonte: da 1 a 150 caratteri.')
    if kind=='audio':
        from .execution_mode import guard_intent
        guard_intent(settings,'transcribe')
        ids=body.get('asset_ids',[body.get('asset_id')])
        if not isinstance(ids,list) or not 1<=len(ids)<=10:raise ValueError('Importa da uno a dieci audio/video per volta.')
        media=app.validate_media([{'id':ident} for ident in ids],canvas=True)
        if any(not m['mime'].startswith(('audio/','video/')) for m in media):raise ValueError('Seleziona un audio o video allegato. Il video viene letto solo per la traccia audio.')
    else:
        url=body.get('url')
        if not isinstance(url,str) or not 1<=len(url)<=4096:raise ValueError('URL fonte non valido.')
        if kind=='youtube':
            from .agent_online_video import youtube_url
            url=youtube_url(url)
        else:
            from urllib.parse import urlsplit
            parsed=urlsplit(url)
            if parsed.scheme not in ('http','https') or not parsed.hostname or parsed.username or parsed.password:raise ValueError('Indica un URL Internet pubblico.')
        spec['url']=url
        if app.store.one('SELECT id FROM project_sources WHERE project_id=? AND source_url=?',(project,url)):raise ValueError('Questo URL è già importato nel progetto. Per acquisire una nuova versione, scollega prima la fonte precedente e poi reimportala; non sostituisco il testo in silenzio.')
    settings=settings|{'_study_import':spec,'_rag':False,'_assistant':False}
    job_id=app.store.enqueue(chat_id,'Importa fonte Studio · '+spec['name'],media,settings,False,[]);app.wake.set()
    return {'job_id':job_id,'intent':'study_import','canvas':False}

def ingest(app,job,payload,settings,cancel,stage,log_path,active_job=None):
    spec=settings['_study_import'];project=spec['project_id'];app.knowledge.project(project)
    if spec.get('url') and app.store.one('SELECT id FROM project_sources WHERE project_id=? AND source_url=?',(project,spec['url'])):raise ValueError('URL già importato nel progetto: scollega la fonte precedente prima di reimportarla. Nessun testo aggiornato è stato scartato o dichiarato indicizzato.')
    stage('Studio · lettura della fonte')
    if spec['kind']=='web':
        from .web_search import fetch,Text
        parser=Text();parser.feed(fetch(spec['url'],cancel));value=parser.text()
        if len(value)<40:raise ValueError('La pagina non contiene testo sufficiente. Per pagine dinamiche usa il browser dell’Agente.')
        content='# '+spec['name']+'\n\nFonte: '+spec['url']+'\n\n'+value
    elif spec['kind']=='youtube':
        result=app.engine.tool_call('study-captions-worker.py',{'url':spec['url'],'data':str(app.data),'id':job['id']},cancel,stage,log_path,timeout=240)
        content='# '+result['title']+'\n\nFonte: '+spec['url']+'\n\nTrascrizione sottotitoli ('+result['language']+'); può contenere errori.\n\n'+result['text']
    else:
        item=payload['media'][0];result=app.engine.transcribe(item,settings,cancel,stage,log_path)
        parts=[f"[{s['start']:.1f}–{s['end']:.1f} s] {s['text']}" for s in result['segments']]
        if not parts:raise ValueError('Nessun parlato riconosciuto; nessuna fonte vuota importata.')
        content='# '+spec['name']+'\n\nOriginale: '+item['name']+'\nTrascrizione automatica: può contenere errori.\n\n'+'\n'.join(parts)
    if cancel.is_set():raise Cancelled()
    if len(content)>1000000:raise ValueError('La fonte testuale supera un milione di caratteri.')
    name=re.sub(r'[^\w .-]','_',spec['name']).strip()[:100]+'.md'
    path=safe_join(app.data,'outputs/'+job['id']+'/source.md');path.parent.mkdir(parents=True,exist_ok=True);path.write_text(content,encoding='utf8')
    existing=app.store.one('SELECT id FROM project_sources WHERE project_id=? AND source_url=?',(project,spec['url'])) if spec.get('url') else None
    if existing:source=existing['id']
    else:
        entry=app.knowledge.register_import(project,{'name':name,'defer':True},path,active_job=active_job or job['id'],queued_readers=True);source=entry['id']
        if spec.get('url'):app.store.execute('UPDATE project_sources SET source_url=? WHERE id=? AND project_id=?',(spec['url'],source,project))
    if spec['kind']=='audio':
        app.store.execute('CREATE TABLE IF NOT EXISTS rag_media_origins (source_id TEXT PRIMARY KEY,project_id TEXT,media_id TEXT,media_path TEXT,media_name TEXT)')
        item=payload['media'][0];app.store.execute('INSERT OR REPLACE INTO rag_media_origins VALUES (?,?,?,?,?)',(source,project,item['id'],item['path'],item['name']))
    if cancel.is_set():raise Cancelled()
    stage('Studio · indicizzazione della fonte nel progetto')
    with app.knowledge.resource(settings,cancel),app.knowledge.index_lock:app.knowledge.index(project,settings,cancel,stage)
    row=app.store.one('SELECT status,error FROM project_sources WHERE id=? AND project_id=?',(source,project))
    if not row or row['status']!='ready':raise ValueError('Fonte conservata ma indice non pronto: '+str(row.get('error','') if row else 'fonte mancante'))
    return {'project_id':project,'source_id':source,'source_url':spec.get('url',''),'indexed':True}

def run(app,job,payload,settings,cancel,stage,log_path):
    results=[]
    items=payload['media'] if settings['_study_import']['kind']=='audio' else [None]
    for item in items:
        local=settings
        if item and len(items)>1:local=settings|{'_study_import':settings['_study_import']|{'name':item['name']}}
        results.append(ingest(app,job if len(items)==1 else job|{'id':uid()},payload if item is None else payload|{'media':[item]},local,cancel,stage,log_path,active_job=job['id']))
        app.store.update_answer(job,f'Fonti importate e indicizzate: {len(results)}/{len(items)}.',meta={'intent':'study_import','project_id':settings['_study_import']['project_id'],'imported_sources':results})
    app.store.update_answer(job,'Fonti importate e indicizzate nel RAG del progetto. Ora sono selezionabili da tutti gli strumenti.','done',[],{'intent':'study_import','project_id':settings['_study_import']['project_id'],'imported_sources':results})
    app.store.execute("UPDATE jobs SET status='done',stage='Fonte Studio pronta' WHERE id=?",(job['id'],))

"""Human-confirmed multi-lot removal; only selected image files may be unlinked."""
import hashlib
import json
import re
import time
from pathlib import Path
from .downloads import safe_join
from .store import uid

def hidden_ids(app):
    return {p.stem for p in (app.data/'image-collections-hidden').glob('*.json') if re.fullmatch('[a-f0-9]{32}',p.stem)}

def ids(value):
    if not isinstance(value,list) or not 1<=len(value)<=100 or any(not isinstance(v,str) or not re.fullmatch('[a-f0-9]{32}',v) for v in value) or len(set(value))!=len(value):raise ValueError('Seleziona da 1 a 100 lotti distinti.')
    return value

def _plan(app,selected,db):
    from .image_collections import listing
    selected=ids(selected);all_lots=listing(app,limit=None)['items'];by_id={v['id']:v for v in all_lots}
    if any(i not in by_id for i in selected):raise ValueError('Un lotto non è più disponibile: aggiorna la raccolta.')
    lots=[by_id[i] for i in selected];files={};signature=[]
    active_jobs=list(db.execute("SELECT id,payload FROM jobs WHERE status IN ('queued','running','cancelling')"))
    active=bool(active_jobs) or any(t.get('status')=='running' for t in app.knowledge.tasks.values())
    in_use=any(ident in row['payload'] or ident==row['id'] for ident in selected for row in active_jobs)
    can_remove=not in_use and all(l.get('status') not in ('queued','running','cancelling') for l in lots)
    for lot in lots:
        signature.append([lot['id'],hashlib.sha256(json.dumps(lot,sort_keys=True).encode()).hexdigest()])
        for item in lot['images']:
            media=item['media'];path=safe_join(app.data,media['path']);relative=path.relative_to(app.data.resolve()).as_posix()
            if relative.split('/')[0] not in ('uploads','outputs','project-imports','exports'):raise ValueError('File del lotto fuori dalle cartelle gestite di H3.')
            if relative in files or not path.is_file():continue
            stat=path.stat();files[relative]={'path':relative,'name':media['name'],'bytes':stat.st_size,'references':set()}
            signature.append([relative,stat.st_dev,stat.st_ino,stat.st_size,stat.st_mtime_ns])
    for lot in all_lots:
        if lot['id'] in selected:continue
        for image in lot['images']:
            try:relative=safe_join(app.data,image['media']['path']).relative_to(app.data.resolve()).as_posix()
            except (ValueError,OSError):continue
            if relative in files:files[relative]['references'].add('Altro lotto: '+lot['name'])
    for row in db.execute('SELECT title,media,source_key FROM canvas_artifacts'):
        key=row['source_key'] or ''
        if any(key in ('job:'+i,'agent:'+i) or key.endswith(':'+i) for i in selected):continue
        for media in json.loads(row['media']):
            try:relative=safe_join(app.data,media['path']).relative_to(app.data.resolve()).as_posix()
            except (ValueError,OSError,KeyError):continue
            if relative in files:files[relative]['references'].add('Artefatto: '+row['title'])
    for row in db.execute('SELECT s.path,p.name FROM project_sources s JOIN projects p ON p.id=s.project_id'):
        try:relative=Path(row['path']).resolve().relative_to(app.data.resolve()).as_posix()
        except ValueError:continue
        if relative in files:files[relative]['references'].add('Progetto RAG: '+row['name'])
    values=[v|{'references':sorted(v['references'])[:20]} for v in files.values()]
    signature.append([[v['path'],v['references']] for v in values]);signature.append([active,can_remove])
    return {'lots':[{'id':v['id'],'name':v['name'],'images':v['available']} for v in lots],'count':len(lots),'files':values,'file_count':len(values),
            'bytes':sum(v['bytes'] for v in values),'referenced_files':sum(bool(v['references']) for v in values),'can_remove':can_remove,
            'can_delete_files':can_remove and not active,'reason':'Attendi la fine delle generazioni o dell’indicizzazione prima di eliminare file dal disco.' if active else 'Un lotto selezionato è ancora in lavorazione.' if not can_remove else '',
            'snapshot':hashlib.sha256(json.dumps(signature,sort_keys=True).encode()).hexdigest()}

def plan(app,body):
    if not isinstance(body,dict) or set(body)!={'ids'}:raise ValueError('Selezione lotti non valida.')
    with app.store.connect() as db:return _plan(app,body['ids'],db)

def remove(app,body):
    if not isinstance(body,dict) or set(body)-{'ids','delete_files','confirmed','snapshot'}:raise ValueError('Rimozione lotti non valida.')
    delete=body.get('delete_files',False)
    if type(delete) is not bool:raise ValueError('Scegli se eliminare anche i file dal disco.')
    if body.get('confirmed') is not True or not isinstance(body.get('snapshot'),str):raise ValueError('Conferma la rimozione nella modale.')
    with app.store.connect() as db:
        db.execute('BEGIN IMMEDIATE');value=_plan(app,body.get('ids'),db)
        if value['snapshot']!=body['snapshot']:raise ValueError('I lotti o i file sono cambiati. Riapri la conferma di eliminazione.')
        if not value['can_remove']:raise ValueError('Attendi la fine dei lotti selezionati.')
        if delete and not value['can_delete_files']:raise ValueError(value['reason'])
        from .image_collections import get
        contents={lot['id']:get(app,lot['id']) for lot in value['lots']}
        failed=set();errors=[];deleted=0
        if delete:
            for item in value['files']:
                try:
                    path=safe_join(app.data,item['path']);path.unlink();deleted+=1
                    db.execute('INSERT OR IGNORE INTO gallery_hidden(path) VALUES (?)',(item['path'],))
                    db.execute("UPDATE project_sources SET status='error',error='File eliminato dal disco con conferma esplicita' WHERE path=?",(str(path),))
                except OSError:
                    failed.add(item['path']);errors.append({'name':item['name'],'message':'File non eliminato: il sistema non consente la cancellazione. Il lotto interessato resta disponibile.'})
        removed=[]
        folder=app.data/'image-collections-hidden';folder.mkdir(exist_ok=True)
        for lot in value['lots']:
            current=contents[lot['id']]
            if any(safe_join(app.data,item['media']['path']).relative_to(app.data.resolve()).as_posix() in failed for item in current['images']):continue
            target=folder/(lot['id']+'.json');temporary=target.with_suffix('.'+uid()+'.tmp')
            try:
                temporary.write_text(json.dumps({'id':lot['id'],'name':lot['name'],'removed':time.time(),'files_deleted':delete}),encoding='utf8');temporary.replace(target)
                for base in ('image-collections','slide-backgrounds'):(app.data/base/(lot['id']+'.json')).unlink(missing_ok=True)
                removed.append(lot['id'])
            finally:temporary.unlink(missing_ok=True)
        return {'removed':removed,'files_deleted':deleted,'files_preserved':not delete,'errors':errors}

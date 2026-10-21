"""Explicit batch removal with optional deletion of selected workspace files.

Only the selected file is deleted, never a parent directory or linked assets.
Active jobs and saved timeline metadata cannot be deleted from disk here.
"""
import hashlib,json,re
from pathlib import Path
from .downloads import safe_join
from .gallery_timelines import MIME as TIMELINE_MIME


def _ids(ids):
    if not isinstance(ids,list) or not 1<=len(ids)<=200 or any(not isinstance(i,str) or not re.fullmatch(r'[0-9a-f]{32}',i) for i in ids) or len(set(ids))!=len(ids):raise ValueError('Seleziona da 1 a 200 file distinti della tua galleria.')
    return ids


def _plan(gallery,ids,db):
    active=[dict(r) for r in db.execute("SELECT id,payload FROM jobs WHERE status IN ('queued','running','cancelling')")]
    items=[];signature=[]
    for ident in _ids(ids):
        row=db.execute('SELECT * FROM gallery WHERE id=?',(ident,)).fetchone()
        if row is None:raise ValueError('Un file non appartiene alla tua galleria o non è più disponibile.')
        row=dict(row);file=safe_join(gallery.root,row['path'])
        relative=file.relative_to(gallery.root.resolve())
        if not relative.parts or relative.parts[0] not in ('uploads','outputs','project-imports','exports'):raise ValueError('Percorso del file non consentito.')
        if not file.is_file():raise ValueError('Un file non è più disponibile sul disco.')
        stat=file.stat();tokens={ident,row['path'],str(file),row['path'].replace('/','\\')}
        if len(relative.parts)>2 and relative.parts[0]=='outputs' and re.fullmatch(r'[a-f0-9]{32}',relative.parts[1]):tokens.add(relative.parts[1])
        in_use=any(any(token in job['payload'] for token in tokens) or relative.parts[:2]==('outputs',job['id']) for job in active)
        reason=('Una generazione attiva o in coda usa questo file.' if in_use else 'È una timeline salvata: qui puoi rimuoverla dalla galleria, conservando timeline e clip.' if row['mime']==TIMELINE_MIME else '')
        items.append({'id':ident,'name':row['name'],'bytes':stat.st_size,'file_deletion_allowed':not bool(reason),'reason':reason})
        signature.append([ident,row['path'],stat.st_size,stat.st_mtime_ns])
    snapshot=hashlib.sha256(json.dumps(signature,sort_keys=True).encode()).hexdigest()
    return {'items':items,'count':len(items),'bytes':sum(i['bytes'] for i in items),'can_delete_files':all(i['file_deletion_allowed'] for i in items),'snapshot':snapshot}


def plan(gallery,body):
    if not isinstance(body,dict) or set(body)!={'ids'}:raise ValueError('Selezione non valida.')
    with gallery.store.connect() as db:return _plan(gallery,body['ids'],db)


def remove(gallery,body):
    if not isinstance(body,dict) or set(body)-{'ids','delete_files','confirmed','snapshot'}:raise ValueError('Rimozione non valida.')
    delete=body.get('delete_files',False)
    if type(delete) is not bool:raise ValueError('Scegli se conservare o cancellare i file.')
    if delete and (body.get('confirmed') is not True or not isinstance(body.get('snapshot'),str)):raise ValueError('Conferma la cancellazione dal disco nella modale.')
    removed=[];errors=[]
    with gallery.store.connect() as db:
        db.execute('BEGIN IMMEDIATE')
        value=_plan(gallery,body.get('ids'),db)
        if delete:
            if value['snapshot']!=body['snapshot']:raise ValueError('I file sono cambiati: riapri la conferma di eliminazione.')
            if not value['can_delete_files']:raise ValueError('Un file è in uso o è una timeline salvata. Puoi rimuoverlo dalla galleria conservando i file.')
        for item in value['items']:
            row=db.execute('SELECT path FROM gallery WHERE id=?',(item['id'],)).fetchone()
            try:
                if delete:safe_join(gallery.root,row['path']).unlink()
            except OSError:
                errors.append({'id':item['id'],'name':item['name'],'message':'Il sistema non permette di cancellare questo file. È rimasto nella galleria.'});continue
            db.execute('INSERT OR IGNORE INTO gallery_hidden VALUES (?)',(row['path'],))
            removed.append(item['id'])
    return {'removed':removed,'files_deleted':len(removed) if delete else 0,'files_preserved':not delete,'errors':errors}

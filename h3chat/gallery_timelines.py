"""First-class gallery entries for saved edits without an exported movie."""
import json
import math
from .downloads import safe_join
from .video_resume import checkpoint

MIME='application/x-h3-timeline'
TERMINAL=('done','cancelled','failed','interrupted')


def sync(gallery,ids):
    if not ids:return
    marks=','.join('?' for _ in ids)
    rows=gallery.store.all(f'''SELECT j.id,j.chat_id,j.status,j.created,c.title,
        CASE WHEN json_valid(m.meta) THEN json_extract(m.meta,'$.timing') END AS timing
        FROM jobs j JOIN messages m ON m.id=j.message_id AND m.chat_id=j.chat_id
        JOIN chats c ON c.id=j.chat_id WHERE j.id IN ({marks})''',ids)
    for row in rows:
        if row['status'] not in TERMINAL:continue
        ident=row['id'];path=f'outputs/{ident}/scenes.json'
        try:
            file=safe_join(gallery.root,path)
            if not file.is_file():continue
            # An exported full movie already represents this same timeline.
            if gallery.store.one("SELECT 1 FROM gallery g JOIN gallery_details d ON d.path=g.path WHERE d.timeline_id=? AND d.video_kind='timeline' AND g.mime LIKE 'video/%'",(ident,)):
                gallery.store.execute('DELETE FROM gallery WHERE id=? AND mime=?',(ident,MIME))
                continue
            saved=checkpoint(gallery.root,ident);count=len(saved['timeline'])
            if not saved.get('working_timeline') or saved['completed']!=count:continue
            requested=saved.get('revision_request',[]);ready=saved.get('revision_completed',[])
            if not isinstance(requested,list) or not isinstance(ready,list):continue
            requested_ids={p['clip'] for p in requested if isinstance(p,dict) and type(p.get('clip')) is int and 1<=p['clip']<=count}
            if any(type(n) is not int or n not in requested_ids for n in ready):continue
            timing=json.loads(row['timing'] or '{}')
            finished=timing.get('finished_at') if timing.get('job_id')==ident else None
            modified=max(file.stat().st_mtime,row['created'],finished if type(finished) in (int,float) and math.isfinite(finished) else 0)
            gallery.register([{'id':ident,'path':path,'name':row['title']+' · timeline','mime':MIME}],created=row['created'])
            with gallery.store.connect() as db:
                db.execute('UPDATE gallery_details SET modified=max(modified,?) WHERE path=?',(modified,path))
                db.execute('''INSERT INTO gallery_timeline_state VALUES (?,?,?,?) ON CONFLICT(id) DO UPDATE SET
                    status=excluded.status,completed=excluded.completed,requested=excluded.requested''',
                    (ident,row['status'],len(set(ready)),len(requested_ids)))
        except (OSError,ValueError,TypeError,KeyError,AttributeError):continue


def touch(gallery,ident,stamp):
    """Saving an editor draft also modifies its library timeline, without rendering."""
    gallery.store.execute('UPDATE gallery_details SET modified=max(modified,?) WHERE timeline_id=?',(stamp,ident))

"""Durable change queue: gallery searches never walk the complete chat history."""
import json
from pathlib import Path


def initialize(store):
    with store.connect() as db:
        db.executescript('''
            CREATE TABLE IF NOT EXISTS gallery_pending (
                source TEXT NOT NULL, id TEXT NOT NULL, version INTEGER NOT NULL DEFAULT 1,
                PRIMARY KEY(source,id));
            CREATE TABLE IF NOT EXISTS gallery_details (
                path TEXT PRIMARY KEY, modified REAL NOT NULL, video_kind TEXT NOT NULL DEFAULT '',
                timeline_id TEXT NOT NULL DEFAULT '', clip_count INTEGER NOT NULL DEFAULT 0);
            CREATE INDEX IF NOT EXISTS gallery_created ON gallery(created DESC,id);
            CREATE INDEX IF NOT EXISTS gallery_modified ON gallery_details(modified DESC,path);
            CREATE TABLE IF NOT EXISTS gallery_timeline_state (
                id TEXT PRIMARY KEY,status TEXT NOT NULL,completed INTEGER NOT NULL,requested INTEGER NOT NULL);
            CREATE INDEX IF NOT EXISTS gallery_jobs_message ON jobs(message_id,status);
            CREATE TABLE IF NOT EXISTS gallery_chat_media(path TEXT NOT NULL,chat_id TEXT NOT NULL,PRIMARY KEY(path,chat_id));
            CREATE TABLE IF NOT EXISTS gallery_project_media(path TEXT NOT NULL,project_id TEXT NOT NULL,PRIMARY KEY(path,project_id));
            CREATE TABLE IF NOT EXISTS gallery_internal(path TEXT PRIMARY KEY);
        ''')
        for table,source,columns in [('messages','message','media,meta'),('canvas_artifacts','canvas','media'),('project_sources','project','path,name,updated'),('jobs','job','status')]:
            for event in ('INSERT','UPDATE OF '+columns):
                name='gallery_dirty_'+table+('_insert' if event=='INSERT' else '_update')
                unchanged='' if event=='INSERT' else 'WHEN '+ ' OR '.join('NEW.'+c+' IS NOT OLD.'+c for c in columns.split(','))
                db.execute(f'''CREATE TRIGGER IF NOT EXISTS {name} AFTER {event} ON {table} {unchanged}
                    BEGIN INSERT INTO gallery_pending(source,id) VALUES ('{source}',NEW.id)
                    ON CONFLICT(source,id) DO UPDATE SET version=version+1; END''')
        db.execute('''CREATE TRIGGER IF NOT EXISTS gallery_dirty_timeline_message AFTER UPDATE OF meta ON messages
            WHEN NEW.meta IS NOT OLD.meta BEGIN
            INSERT INTO gallery_pending(source,id) SELECT 'job',id FROM jobs
                WHERE message_id=NEW.id AND status IN ('done','cancelled','failed','interrupted')
            ON CONFLICT(source,id) DO UPDATE SET version=version+1; END''')
        # One backfill per workspace, including unattached files already registered
        # by old app versions. Triggers catch subsequent inserts and edits.
        if not db.execute("SELECT 1 FROM gallery_sync WHERE key='incremental-v1'").fetchone():
            for source,table in [('message','messages'),('canvas','canvas_artifacts'),('project','project_sources'),('file','gallery')]:
                db.execute('INSERT OR IGNORE INTO gallery_pending(source,id) SELECT ?,id FROM '+table,(source,))
            db.execute("INSERT INTO gallery_sync VALUES ('incremental-v1')")
        if not db.execute("SELECT 1 FROM gallery_sync WHERE key='timelines-v1'").fetchone():
            db.execute("INSERT OR IGNORE INTO gallery_pending(source,id) SELECT 'job',id FROM jobs WHERE status IN ('done','cancelled','failed','interrupted')")
            db.execute("INSERT INTO gallery_sync VALUES ('timelines-v1')")
        if not db.execute("SELECT 1 FROM gallery_sync WHERE key='project-links-v1'").fetchone():
            for source,table in [('message','messages'),('canvas','canvas_artifacts'),('project','project_sources')]:
                db.execute('INSERT OR IGNORE INTO gallery_pending(source,id) SELECT ?,id FROM '+table,(source,))
            db.execute("INSERT INTO gallery_sync VALUES ('project-links-v1')")


def array(value):
    try:
        result=json.loads(value or '[]')
        return result if isinstance(result,list) else []
    except (ValueError,TypeError):return []


def reconcile(gallery):
    store=gallery.store
    pending=store.all('SELECT source,id,version FROM gallery_pending')
    for source in ('message','canvas','project','file','job'):
        group=[p for p in pending if p['source']==source]
        # Keep statements below SQLite's parameter limit, even on large libraries.
        for start in range(0,len(group),300):
            batch=group[start:start+300];ids=[p['id'] for p in batch]
            marks=','.join('?' for _ in ids)
            if source=='message':
                # Project only media arrays; plans/prompts in meta can be huge.
                rows=store.all(f'''SELECT chat_id,media,created,role,
                    CASE WHEN json_valid(meta) THEN json_extract(meta,'$.artifact.media') END AS artifact_media,
                    CASE WHEN json_valid(meta) THEN json_extract(meta,'$.slide_generated_images') END AS slide_media
                    FROM messages WHERE id IN ({marks})''',ids)
                for row in rows:
                    gallery.register(array(row['media'])+array(row['artifact_media'])+array(row['slide_media']),
                        'uploaded' if row['role']=='user' else 'generated',row['created'],chat_id=row['chat_id'])
            elif source=='canvas':
                for row in store.all(f'SELECT chat_id,media,updated FROM canvas_artifacts WHERE id IN ({marks})',ids):
                    gallery.register(array(row['media']),'generated',row['updated'],chat_id=row['chat_id'])
            elif source=='project':
                for row in store.all(f'SELECT id,project_id,path,name,updated FROM project_sources WHERE id IN ({marks})',ids):
                    try:
                        path=Path(row['path']).resolve().relative_to((gallery.root/'project-imports').resolve())
                        gallery.register([row|{'path':(Path('project-imports')/path).as_posix()}],'uploaded',row['updated'] or None,project_id=row['project_id'])
                    except (ValueError,OSError):continue
            elif source=='file':
                gallery.register(store.all(f'SELECT * FROM gallery WHERE id IN ({marks})',ids))
            else:
                from .gallery_timelines import sync
                sync(gallery,ids)
            # Do not lose a newer update committed while these files were checked.
            with store.connect() as db:
                db.executemany('DELETE FROM gallery_pending WHERE source=? AND id=? AND version=?',
                    [(p['source'],p['id'],p['version']) for p in batch])

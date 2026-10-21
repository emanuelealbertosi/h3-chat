"""Workspace-scoped reusable media, retaining references without copying assets."""
import json
import hashlib
import mimetypes
import re
import time
import threading
from pathlib import Path
from .downloads import safe_join
from .gallery_timelines import MIME as TIMELINE_MIME


class Gallery:
    def __init__(self, store):
        self.store=store;self.root=store.root
        store.execute('CREATE TABLE IF NOT EXISTS gallery (id TEXT PRIMARY KEY,path TEXT UNIQUE NOT NULL,name TEXT NOT NULL,mime TEXT NOT NULL,origin TEXT NOT NULL,created REAL NOT NULL)')
        store.execute('CREATE TABLE IF NOT EXISTS gallery_sync (key TEXT PRIMARY KEY)')
        store.execute('CREATE TABLE IF NOT EXISTS gallery_exports (hash TEXT PRIMARY KEY,id TEXT NOT NULL)')
        store.execute('CREATE TABLE IF NOT EXISTS gallery_hidden (path TEXT PRIMARY KEY)')
        from .gallery_index import initialize
        from .gallery_video import VideoSummaries
        initialize(store)
        self._reconcile_lock=threading.Lock()
        self._videos=VideoSummaries(self.root)

    def rename(self, ident, name):
        item=self.get(ident)
        if not isinstance(name,str) or not name.strip() or len(name.strip())>150 or any(ord(c)<32 for c in name):
            raise ValueError('Scegli un nome da 1 a 150 caratteri.')
        with self.store.connect() as db:
            db.execute('UPDATE gallery SET name=? WHERE path=?',(name.strip(),item['path']))
            db.execute('INSERT INTO gallery_details(path,modified) VALUES (?,?) ON CONFLICT(path) DO UPDATE SET modified=max(modified,excluded.modified)',(item['path'],time.time()))
        return self.get(ident)

    def remove(self, ident):
        item=self.get(ident)
        # A library removal must not destroy inputs used by chats or queued jobs.
        self.store.execute('INSERT OR IGNORE INTO gallery_hidden VALUES (?)',(item['path'],))
        return {'removed':True,'files_preserved':True}

    def register(self, items, origin='generated', created=None,*,chat_id=None,project_id=None,internal=False):
        records=[];details=[]
        for item in items or []:
            if not isinstance(item,dict) or not re.fullmatch(r'[0-9a-f]{32}',str(item.get('id',''))):continue
            path=str(item.get('path',''))
            try:
                file=safe_join(self.root,path)
                normalized=file.relative_to(self.root.resolve()).as_posix()
                if not normalized.startswith(('uploads/','outputs/','project-imports/','exports/')):continue
                stat=file.stat()
                if not file.is_file():continue
                path=normalized
            except (OSError,ValueError,PermissionError):continue
            name=str(item.get('name') or file.name)[:150];mime=str(item.get('mime') or mimetypes.guess_type(name)[0] or mimetypes.guess_type(file.name)[0] or 'application/octet-stream')[:150]
            stamp=created if created is not None else time.time()
            records.append((item['id'],path,name,mime,origin,stamp))
            video=self._videos.describe(path,item.get('generation')) if mime.startswith('video/') or mime==TIMELINE_MIME else {}
            details.append((path,max(stat.st_mtime,video.get('modified',0),created or 0),video.get('video_kind',''),video.get('timeline_id',''),video.get('clip_count',0)))
        if not records:return
        # One commit for a batch, instead of a new connection and disk flush per file.
        with self.store.connect() as db:
            for ident,path,name,mime,source,stamp in records:
                if mime.startswith('video/'):
                    # A later export may use the job ID previously representing a
                    # saved timeline. Keep a hidden entry hidden when upgrading it.
                    db.execute('''INSERT OR IGNORE INTO gallery_hidden(path) SELECT ? FROM gallery g
                        JOIN gallery_hidden h ON h.path=g.path WHERE g.id=? AND g.mime=?''',(path,ident,TIMELINE_MIME))
                    db.execute('DELETE FROM gallery WHERE id=? AND mime=?',(ident,TIMELINE_MIME))
            db.executemany('INSERT OR IGNORE INTO gallery VALUES (?,?,?,?,?,?)',records)
            if internal:db.executemany('INSERT OR IGNORE INTO gallery_internal VALUES (?)',[(r[1],) for r in records])
            if chat_id:db.executemany('INSERT OR IGNORE INTO gallery_chat_media VALUES (?,?)',[(r[1],chat_id) for r in records])
            if project_id:db.executemany('INSERT OR IGNORE INTO gallery_project_media VALUES (?,?)',[(r[1],project_id) for r in records])
            db.executemany('''INSERT INTO gallery_details VALUES (?,?,?,?,?) ON CONFLICT(path) DO UPDATE SET
                modified=max(gallery_details.modified,excluded.modified),video_kind=excluded.video_kind,
                timeline_id=excluded.timeline_id,clip_count=excluded.clip_count
                WHERE excluded.modified>gallery_details.modified OR excluded.video_kind!=gallery_details.video_kind
                    OR excluded.timeline_id!=gallery_details.timeline_id OR excluded.clip_count!=gallery_details.clip_count''',details)

    def exported(self,result):
        url=result.get('url','')
        if url.startswith('/exports/') or url.startswith('/media/'):
            path=url[len('/media/'):] if url.startswith('/media/') else url[1:]
            self.register([{'id':hashlib.sha256(path.encode()).hexdigest()[:32],'path':path,'name':result.get('name'),'mime':result.get('mime') or mimetypes.guess_type(path)[0]}])
        return result

    def reconcile(self):
        from .gallery_index import reconcile
        with self._reconcile_lock:
            reconcile(self)
            # Older unattached uploads have sidecars; import once per database.
            if not self.store.one("SELECT 1 FROM gallery_sync WHERE key='uploads'"):
                for path in (self.root/'uploads').glob('*.json'):
                    try:self.register([json.loads(path.read_text(encoding='utf-8'))],'uploaded',path.stat().st_mtime)
                    except (OSError,ValueError):continue
                self.store.execute("INSERT OR IGNORE INTO gallery_sync VALUES ('uploads')")

    def get(self, ident):
        if not isinstance(ident,str) or not re.fullmatch(r'[0-9a-f]{32}',ident):raise ValueError('File della galleria non valido.')
        item=self.store.one('SELECT * FROM gallery WHERE id=?',(ident,))
        if not item:raise ValueError('File non trovato nella tua galleria.')
        file=safe_join(self.root,item['path'])
        if not file.is_file():raise ValueError('Questo file non è più disponibile sul disco.')
        return item|{'timeline_only':True} if item['mime']==TIMELINE_MIME else item

    def listing(self, query='', kind='all', origin='all', offset=0, sort='modified_desc',project_id=''):
        orders={'modified_desc':'modified DESC','modified_asc':'modified ASC','added_desc':'g.created DESC','added_asc':'g.created ASC',
            'name_asc':'g.name COLLATE NOCASE ASC','name_desc':'g.name COLLATE NOCASE DESC',
            'type_asc':"CASE WHEN g.mime='application/x-h3-timeline' THEN 'video/mp4' ELSE g.mime END ASC,g.name COLLATE NOCASE ASC",'type_desc':"CASE WHEN g.mime='application/x-h3-timeline' THEN 'video/mp4' ELSE g.mime END DESC,g.name COLLATE NOCASE ASC"}
        if not isinstance(query,str) or len(query)>200 or kind not in ('all','image','audio','video','document','other','model') or origin not in ('all','uploaded','generated') or type(offset) is not int or not 0<=offset<=100000:raise ValueError('Ricerca galleria non valida.')
        if not isinstance(sort,str) or sort not in orders:raise ValueError('Ordinamento galleria non valido.')
        if not isinstance(project_id,str) or (project_id and not re.fullmatch(r'[0-9a-f]{32}',project_id)):raise ValueError('Progetto non valido.')
        self.reconcile();clauses=['g.name LIKE ? ESCAPE \'\\\''];args=['%'+query.replace('\\','\\\\').replace('%','\\%').replace('_','\\_')+'%']
        if kind=='video':clauses.append("(g.mime LIKE 'video/%' OR g.mime='application/x-h3-timeline')")
        if kind in ('image','audio','model'):clauses.append('g.mime LIKE ?');args.append(kind+'/%')
        if kind=='document':clauses.append("(g.mime='application/pdf' OR g.mime LIKE '%officedocument%' OR g.mime LIKE 'text/%')")
        if kind=='other':clauses.append("g.mime NOT LIKE 'model/%' AND g.mime NOT LIKE 'image/%' AND g.mime NOT LIKE 'audio/%' AND g.mime NOT LIKE 'video/%' AND g.mime NOT LIKE 'text/%' AND g.mime NOT IN ('application/pdf','application/x-h3-timeline') AND g.mime NOT LIKE '%officedocument%'")
        if origin!='all':clauses.append('g.origin=?');args.append(origin)
        clauses.append('g.path NOT IN (SELECT path FROM gallery_hidden)')
        clauses.append('g.path NOT IN (SELECT path FROM gallery_internal)')
        # Internal video references remain addressable by their IDs, but are
        # working material rather than user images in the library.
        clauses.append("NOT (g.mime LIKE 'image/%' AND (g.path LIKE 'outputs/video-imports/%' OR g.path GLOB 'outputs/*/auto-guides/*' OR g.path GLOB 'outputs/*/guide-frames/*' OR g.path GLOB 'outputs/*/guide-[0-9]*/*' OR g.path GLOB 'outputs/*/context/frame-*.png' OR g.path GLOB 'outputs/*/first-anchor.png' OR g.path GLOB 'outputs/*/last-anchor.png' OR g.path GLOB 'outputs/*/first/frame-*' OR g.path GLOB 'outputs/*/last/frame-*'))")
        if project_id:
            clauses.append('''(EXISTS (SELECT 1 FROM gallery_chat_media gm JOIN chats c ON c.id=gm.chat_id WHERE gm.path=g.path AND c.project_id=?)
                OR EXISTS (SELECT 1 FROM gallery_project_media pm WHERE pm.path=g.path AND pm.project_id=?)
                OR EXISTS (SELECT 1 FROM jobs pj JOIN chats pc ON pc.id=pj.chat_id WHERE pj.id=substr(g.path,9,32) AND g.path LIKE 'outputs/%' AND pc.project_id=?))''')
            args.extend([project_id]*3)
        clauses.append("(g.mime!='application/x-h3-timeline' OR EXISTS (SELECT 1 FROM jobs owned WHERE owned.id=g.id AND owned.status IN ('done','cancelled','failed','interrupted')))")
        where=' AND '.join(clauses)
        rows=self.store.all('''SELECT g.*,COALESCE(d.modified,g.created) AS modified,
            d.video_kind,d.timeline_id,d.clip_count,j.chat_id,t.status AS timeline_status,
            t.completed AS completed_clips,t.requested AS requested_clips
            FROM gallery g LEFT JOIN gallery_details d ON d.path=g.path
            LEFT JOIN jobs j ON j.id=substr(g.path,9,32) AND g.path LIKE 'outputs/%'
                AND (j.status='done' OR g.mime='application/x-h3-timeline')
            LEFT JOIN gallery_timeline_state t ON t.id=g.id AND g.mime='application/x-h3-timeline'
            WHERE '''+where+' ORDER BY '+orders[sort]+',g.id LIMIT 49 OFFSET ?',(*args,offset))
        items=[]
        for row in rows[:48]:
            try:
                file=safe_join(self.root,row['path'])
                if not file.is_file():continue
                only=row['mime']==TIMELINE_MIME
                items.append(row|{'mime':'video/mp4' if only else row['mime'],'timeline_only':only,
                    'size':0 if only else file.stat().st_size,'url':None if only else '/gallery-file/'+row['id']})
            except (OSError,ValueError,PermissionError):continue
        return {'items':items,'more':len(rows)>48,'offset':offset+48,'total':self.store.one('SELECT count(*) AS n FROM gallery g WHERE '+where,args)['n'],'manage':True,'sorting':True,'sort':sort,
            'projects':self.store.all('SELECT id,name FROM projects ORDER BY name COLLATE NOCASE'),'project_id':project_id}

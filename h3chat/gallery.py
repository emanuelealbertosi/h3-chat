"""Workspace-scoped reusable media, retaining references without copying assets."""
import json
import hashlib
import mimetypes
import re
import time
from pathlib import Path
from .downloads import safe_join


class Gallery:
    def __init__(self, store):
        self.store=store;self.root=store.root
        store.execute('CREATE TABLE IF NOT EXISTS gallery (id TEXT PRIMARY KEY,path TEXT UNIQUE NOT NULL,name TEXT NOT NULL,mime TEXT NOT NULL,origin TEXT NOT NULL,created REAL NOT NULL)')
        store.execute('CREATE TABLE IF NOT EXISTS gallery_sync (key TEXT PRIMARY KEY)')
        store.execute('CREATE TABLE IF NOT EXISTS gallery_exports (hash TEXT PRIMARY KEY,id TEXT NOT NULL)')

    def register(self, items, origin='generated', created=None):
        for item in items or []:
            if not isinstance(item,dict) or not re.fullmatch(r'[0-9a-f]{32}',str(item.get('id',''))):continue
            path=str(item.get('path',''))
            try:
                file=safe_join(self.root,path)
                normalized=file.relative_to(self.root.resolve()).as_posix()
                if not file.is_file() or not normalized.startswith(('uploads/','outputs/','project-imports/','exports/')):continue
                path=normalized
            except (OSError,ValueError,PermissionError):continue
            name=str(item.get('name') or file.name)[:150];mime=str(item.get('mime') or mimetypes.guess_type(name)[0] or mimetypes.guess_type(file.name)[0] or 'application/octet-stream')[:150]
            self.store.execute('INSERT OR IGNORE INTO gallery VALUES (?,?,?,?,?,?)',(item['id'],path,name,mime,origin,created or time.time()))

    def exported(self,result):
        url=result.get('url','')
        if url.startswith('/exports/') or url.startswith('/media/'):
            path=url[len('/media/'):] if url.startswith('/media/') else url[1:]
            self.register([{'id':hashlib.sha256(path.encode()).hexdigest()[:32],'path':path,'name':result.get('name'),'mime':result.get('mime') or mimetypes.guess_type(path)[0]}])
        return result

    def reconcile(self):
        # JSON references, not a recursive filesystem scan. Include canvas-only
        # results and completed images retained during a cancelled batch.
        rows=self.store.all("SELECT media,meta,created,role FROM messages UNION ALL SELECT media,'{}' AS meta,updated AS created,'assistant' AS role FROM canvas_artifacts")
        for row in rows:
            try:
                meta=json.loads(row['meta']);items=json.loads(row['media'])
                if not isinstance(meta,dict):meta={}
                if not isinstance(items,list):items=[]
                items+=meta.get('artifact',{}).get('media',[])
                items+=meta.get('slide_generated_images',[])
                self.register(items,'uploaded' if row['role']=='user' else 'generated',row['created'])
            except (ValueError,TypeError,AttributeError):continue
        for row in self.store.all("SELECT id,path,name,updated FROM project_sources WHERE path LIKE ?",(str(self.root/'project-imports')+'%',)):
            try:
                path=Path(row['path']).resolve().relative_to(self.root).as_posix()
                self.register([{'id':row['id'],'path':path,'name':row['name']}],'uploaded',row['updated'] or None)
            except (ValueError,OSError):continue
        # Older unattached uploads have sidecars; import them once per database.
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
        return item

    def listing(self, query='', kind='all', origin='all', offset=0):
        if not isinstance(query,str) or len(query)>200 or kind not in ('all','image','audio','video','document','other') or origin not in ('all','uploaded','generated') or type(offset) is not int or not 0<=offset<=100000:raise ValueError('Ricerca galleria non valida.')
        self.reconcile();clauses=['name LIKE ? ESCAPE \'\\\''];args=['%'+query.replace('\\','\\\\').replace('%','\\%').replace('_','\\_')+'%']
        if kind in ('image','audio','video'):clauses.append('mime LIKE ?');args.append(kind+'/%')
        if kind=='document':clauses.append("(mime='application/pdf' OR mime LIKE '%officedocument%' OR mime LIKE 'text/%')")
        if kind=='other':clauses.append("mime NOT LIKE 'image/%' AND mime NOT LIKE 'audio/%' AND mime NOT LIKE 'video/%' AND mime NOT LIKE 'text/%' AND mime!='application/pdf' AND mime NOT LIKE '%officedocument%'")
        if origin!='all':clauses.append('origin=?');args.append(origin)
        where=' AND '.join(clauses);rows=self.store.all('SELECT * FROM gallery WHERE '+where+' ORDER BY created DESC,id LIMIT 49 OFFSET ?',(*args,offset))
        items=[]
        for row in rows[:48]:
            try:
                file=safe_join(self.root,row['path'])
                if not file.is_file():continue
                items.append(row|{'size':file.stat().st_size,'url':'/gallery-file/'+row['id']})
            except (OSError,ValueError,PermissionError):continue
        return {'items':items,'more':len(rows)>48,'offset':offset+48,'total':self.store.one('SELECT count(*) AS n FROM gallery WHERE '+where,args)['n']}

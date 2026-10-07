"""Separate user databases/files, with a single shared queue for local compute."""
import json
import threading
import time
from .service import Service
from .llm_options import merge as merge_llm_settings

GUEST_PREFERENCES={'chat_model','think_level','vision_enabled','vision_device','chat_advanced','rag_device','rag_visual'}


class Workspaces:
    def __init__(self,owner,start_workers=True):
        self.owner=owner;self.start_workers=start_workers;self.items={};self.lock=threading.RLock();self.synced={}
        self.compute=owner.compute_lock
        self.queue=threading.Condition();self.pending=[]
        self.wrap(owner)

    def wrap(self,app):
        original=app.execute_job
        app.compute_lock=self.compute;app.knowledge.compute_lock=self.compute
        for name in ('enqueue','regenerate'):
            submit=getattr(app.store,name,None)
            if callable(submit):
                def queued(*args,_submit=submit,**kwargs):
                    with self.queue:
                        ident=_submit(*args,**kwargs)
                        self.pending.append((app,ident));self.queue.notify_all()
                    return ident
                setattr(app.store,name,queued)
        stop=getattr(app,'cancel',None)
        if callable(stop):
            def cancel_job(ident):
                result=stop(ident)
                if app.current_id!=ident:
                    with self.queue:
                        self.pending=[t for t in self.pending if t!=(app,ident)];self.queue.notify_all()
                return result
            app.cancel=cancel_job
        def execute(job,cancel):
            ticket=(app,job['id']);acquired=False
            with self.queue:
                if ticket not in self.pending:self.pending.append(ticket)
                while not cancel.is_set():
                    if self.pending[0]==ticket and self.compute.acquire(blocking=False):
                        self.pending.remove(ticket);acquired=True;break
                    position=self.pending.index(ticket)+1
                    app.store.execute("UPDATE jobs SET status='queued',stage=? WHERE id=?",(f'In coda · posizione {position} · attesa motore',job['id']))
                    self.queue.wait(.2)
                if not acquired:
                    if ticket in self.pending:self.pending.remove(ticket)
                    self.queue.notify_all()
            if not acquired:return original(job,cancel)
            app.store.execute("UPDATE jobs SET status='running' WHERE id=?",(job['id'],))
            try:
                self.release_others(app)
                return original(job,cancel)
            finally:
                self.compute.release()
                with self.queue:self.queue.notify_all()
        app.execute_job=execute
        def release():
            self.release_others(app);app.engine.stop()
        app.knowledge.release_gpu=release

    def release_others(self,app):
        with self.lock:others=[self.owner,*self.items.values()]
        for other in others:
            if other is not app:
                other.engine.stop()
                # GPU embedding indexing owns the same lock. CPU workers are
                # independent and their embedding process must not be aborted.
                if other.store.settings().get('rag_device')=='gpu':other.knowledge.embeddings.close()

    def get(self,identity):
        if identity['role']=='owner':return self.owner
        with self.lock:
            ident=identity['id']
            if ident not in self.items:
                app=Service(self.owner.root,self.owner.data/'workspaces'/ident,start_worker=False)
                self.items[ident]=app;self.wrap(app)
                self.sync(ident,app)
                if self.start_workers:app.worker.start()
            app=self.items[ident]
            if time.monotonic()-self.synced.get(ident,0)>15:self.sync(ident,app)
            return app

    def sync(self,ident,app):
        # Share configured model links and provider credentials only. Chat,
        # projects, indexes, attachments, outputs and canvases stay separate.
        with app.store.connect() as db:
            for table in ('external_models','api_providers','media_providers'):
                rows=self.owner.store.all('SELECT * FROM '+table)
                db.execute('DELETE FROM '+table)
                for row in rows:
                    db.execute('INSERT INTO '+table+' VALUES ('+','.join('?' for _ in row)+')',tuple(row.values()))
        if not app.current_id:
            path=app.data/'workspace-preferences.json'
            try:prefs=json.loads(path.read_text(encoding='utf-8'))
            except (OSError,ValueError):prefs={}
            prefs={k:v for k,v in prefs.items() if k in GUEST_PREFERENCES}
            settings=merge_llm_settings(self.owner.store.settings(),prefs)|{'setup_done':True,'memory_policy':'on_demand','ram_cache_gb':0}
            app.store.save_settings(settings)
        self.synced[ident]=time.monotonic()

    def preferences(self,identity,body,rag=False):
        allowed={'rag_device','rag_visual'} if rag else GUEST_PREFERENCES
        if not isinstance(body,dict) or set(body)-allowed:raise PermissionError('Queste impostazioni sono riservate all’amministratore.')
        app=self.get(identity)
        result=app.save_rag_options(body) if rag else app.save_settings(body)
        with self.lock:
            prefs={k:app.store.settings()[k] for k in GUEST_PREFERENCES}
            path=app.data/'workspace-preferences.json';temp=path.with_suffix('.tmp')
            temp.write_text(json.dumps(prefs),encoding='utf-8');temp.replace(path)
        return result

    def deactivate(self,ident):
        with self.lock:app=self.items.pop(ident,None);self.synced.pop(ident,None)
        if app:app.close()
        with self.queue:
            self.pending=[ticket for ticket in self.pending if ticket[0] is not app or ticket[1]==app.current_id];self.queue.notify_all()

    def maintenance_state(self):
        with self.lock:apps=[self.owner,*self.items.values()]
        return {'jobs':[j for app in apps for j in app.store.all('SELECT id,status FROM jobs WHERE status IN (\'queued\',\'running\')')],
                'downloads':[d for app in apps for d in app.downloads.snapshot()]}

    def close(self):
        with self.lock:apps=list(self.items.values());self.items.clear()
        for app in apps:app.close()


def guest_allowed(path,method):
    if method=='GET':return path.startswith(('/api/chats/','/api/canvas/','/api/projects/','/media/','/exports/')) or path in ('/','/access','/login','/api/state','/api/health') or path.startswith('/static/')
    if path in ('/api/chats','/api/collections','/api/uploads','/api/export/pdf','/api/export/html','/api/export/audio','/api/loras','/api/projects','/api/settings','/api/knowledge/options'):return True
    if path.startswith(('/api/chats/','/api/canvas/','/api/collections/','/api/jobs/','/api/slides/images/')):return True
    parts=path.strip('/').split('/')
    if parts[:2]==['api','projects']:
        # Browser uploads carry bytes. Server filesystem path selection is
        # reserved for the administrator, including the legacy sources API.
        if len(parts)==3:return method in ('PATCH','DELETE')
        if len(parts)>=4 and parts[3] in ('import','refresh','web-sources'):return True
        if len(parts)==5 and parts[3]=='sources':return method=='DELETE'
    return False


def guest_state(state):
    # No provider management metadata or host filesystem paths in the guest UI.
    import copy
    result=copy.deepcopy(state)
    for model in result['models']:
        model['files']=[]
        model.pop('external_problems',None)
        if isinstance(model.get('identity'),dict):model['identity'].pop('path',None)
        if isinstance(model.get('vision'),dict):model['vision'].pop('projector',None)
    result['api_providers']=[];result['media_providers']=[];result['downloads']=[]
    result['media_server']={};result['network']={};result['settings']['setup_done']=True
    return result

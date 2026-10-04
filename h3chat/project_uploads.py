"""Bounded binary transfers for browser-selected books; no base64 whole files."""
from pathlib import Path
import threading
import uuid
from .document_limits import RAG_FILE_BYTES,IMPORT_CHUNK_BYTES

class ProjectUploads:
    def __init__(self,knowledge):
        self.knowledge=knowledge;self.folder=knowledge.data/'project-upload-cache'
        self.lock=threading.RLock();self.pending={}
        self.folder.mkdir(parents=True,exist_ok=True)
        # Only our own incomplete transfers can be removed on a fresh start.
        for p in self.folder.glob('*.partial'):
            if len(p.stem)==32 and all(c in '0123456789abcdef' for c in p.stem):p.unlink()

    def start(self,project,body):
        from .rag import import_metadata
        name,label,extension,defer=import_metadata(body)
        size=body.get('size')
        if type(size) is not int or not 0<size<=RAG_FILE_BYTES:raise ValueError('Documento vuoto o oltre 512 MB.')
        with self.knowledge.index_lock,self.lock:
            if self.knowledge.closed.is_set():raise ValueError('Applicazione in chiusura.')
            self.knowledge.mutable(project)
            if len(self.pending)>=8:raise ValueError('Attendi il completamento degli altri caricamenti.')
            ident=uuid.uuid4().hex;path=self.folder/(ident+'.partial');path.touch(exist_ok=False)
            self.pending[ident]={'project':project,'name':name,'relative_path':label,'extension':extension,
                                 'defer':defer,'size':size,'received':0,'path':path}
            return {'id':ident,'chunk_bytes':IMPORT_CHUNK_BYTES,'received':0}

    def entry(self,project,ident):
        value=self.pending.get(ident)
        if not value or value['project']!=project:raise ValueError('Caricamento non trovato in questo progetto.')
        return value

    def append(self,project,ident,offset,raw):
        with self.lock:
            entry=self.entry(project,ident)
            if self.knowledge.closed.is_set():raise ValueError('Applicazione in chiusura.')
            if type(offset) is not int or offset!=entry['received']:raise ValueError('Ordine dei blocchi non valido.')
            if not isinstance(raw,bytes) or not 0<len(raw)<=IMPORT_CHUNK_BYTES or entry['received']+len(raw)>entry['size']:raise ValueError('Dimensione del blocco non valida.')
            if entry['path'].stat().st_size!=entry['received']:raise ValueError('Il caricamento temporaneo è stato modificato.')
            with entry['path'].open('ab') as out:out.write(raw)
            entry['received']+=len(raw)
            return {'received':entry['received'],'size':entry['size']}

    def finish(self,project,ident):
        with self.knowledge.index_lock,self.lock:
            entry=self.entry(project,ident)
            if entry['received']!=entry['size'] or entry['path'].stat().st_size!=entry['size']:raise ValueError('Caricamento incompleto: mancano blocchi del documento.')
            result=self.knowledge.register_import(project,entry,entry['path'])
            self.pending.pop(ident);entry['path'].unlink(missing_ok=True)
            return result

    def cancel(self,project,ident):
        with self.lock:
            entry=self.entry(project,ident);entry['path'].unlink(missing_ok=True);self.pending.pop(ident)
            return {'ok':True}

    def close(self):
        with self.lock:
            for entry in self.pending.values():entry['path'].unlink(missing_ok=True)
            self.pending.clear()

    def cancel_project(self,project):
        with self.lock:
            for ident,entry in list(self.pending.items()):
                if entry['project']==project:
                    entry['path'].unlink(missing_ok=True);self.pending.pop(ident)

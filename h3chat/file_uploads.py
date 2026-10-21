"""Private, bounded transfers with no total file-size or format restriction."""
import base64
import json
import hashlib
import mimetypes
import re
import threading
import uuid
from pathlib import Path

CHUNK_BYTES = 2 * 1024**2


def identify(path, name):
    """Inspect only a small header; parsing belongs to the consuming engine."""
    suffix = Path(name).suffix.lower()
    if not re.fullmatch(r'\.[a-z0-9_-]{1,20}', suffix): suffix = ''
    mime = mimetypes.guess_type(name)[0] or 'application/octet-stream'
    mime = {'.mkv':'video/x-matroska', '.webm':'video/webm', '.mov':'video/quicktime',
            '.avi':'video/x-msvideo', '.m4a':'audio/mp4', '.aac':'audio/aac',
            '.glb':'model/gltf-binary', '.md':'text/markdown'}.get(suffix, mime)
    with Path(path).open('rb') as stream: head = stream.read(512)
    signatures = [(b'\x89PNG\r\n\x1a\n','.png','image/png'), (b'\xff\xd8\xff','.jpg','image/jpeg'),
                  (b'GIF8','.gif','image/gif'), (b'%PDF-','.pdf','application/pdf'),
                  (b'fLaC','.flac','audio/flac'), (b'ID3','.mp3','audio/mpeg'),
                  (b'OggS','.ogg','audio/ogg')]
    if head[:4] == b'RIFF':
        signatures += [(head[:12], *{b'WAVE':('.wav','audio/wav'), b'WEBP':('.webp','image/webp'),
                                      b'AVI ':('.avi','video/x-msvideo')}.get(head[8:12], (suffix,mime)))]
    for magic, ext, detected in signatures:
        if head.startswith(magic):
            # Store an extension that agrees with the detected MIME for serving.
            suffix, mime = ext, detected
            break
    if len(head)>12 and head[4:8]==b'ftyp' and mime=='application/octet-stream':
        suffix, mime = ('.m4a','audio/mp4') if head[8:12] in (b'M4A ',b'M4B ') else ('.mp4','video/mp4')
    return suffix or '.bin', mime


class FileUploads:
    def __init__(self, app):
        self.app=app; self.lock=threading.RLock(); self.pending={}
        self.folder=app.data/'upload-cache'; self.folder.mkdir(parents=True,exist_ok=True)
        for path in self.folder.glob('*.partial'):
            if re.fullmatch(r'[a-f0-9]{32}',path.stem): path.unlink()

    def start(self, body):
        name=body.get('name','File'); size=body.get('size'); origin=body.get('origin','uploaded')
        if not isinstance(name,str) or not name or len(name)>1000 or '\0' in name: raise ValueError('Nome file non valido.')
        if type(size) is not int or size<0: raise ValueError('Dimensione file non valida.')
        if origin not in ('uploaded','generated'): raise ValueError('Origine file non valida.')
        with self.lock:
            if self.app.closed.is_set(): raise ValueError('Applicazione in chiusura.')
            if len(self.pending)>=8: raise ValueError('Attendi il completamento degli altri caricamenti.')
            ident=uuid.uuid4().hex; path=self.folder/(ident+'.partial'); path.touch(exist_ok=False)
            self.pending[ident]={'name':name,'size':size,'received':0,'path':path,'origin':origin}
            return {'id':ident,'chunk_bytes':CHUNK_BYTES,'received':0}

    def entry(self, ident):
        entry=self.pending.get(ident)
        if not entry: raise ValueError('Caricamento non trovato nella tua area.')
        return entry

    def append(self, ident, body):
        with self.lock:
            if self.app.closed.is_set():raise ValueError('Applicazione in chiusura.')
            entry=self.entry(ident); offset=body.get('offset'); encoded=body.get('data')
            if type(offset) is not int or offset!=entry['received']: raise ValueError('Ordine dei blocchi non valido.')
            if not isinstance(encoded,str) or len(encoded)>4*((CHUNK_BYTES+2)//3): raise ValueError('Blocco file non valido.')
            try: raw=base64.b64decode(encoded,validate=True)
            except (ValueError,TypeError): raise ValueError('Blocco file non valido.')
            if not 0<len(raw)<=CHUNK_BYTES or offset+len(raw)>entry['size']: raise ValueError('Dimensione del blocco non valida.')
            if entry['path'].stat().st_size!=offset: raise ValueError('Caricamento temporaneo modificato.')
            with entry['path'].open('ab') as stream: stream.write(raw)
            entry['received']+=len(raw)
            return {'received':entry['received'],'size':entry['size']}

    def finish(self, ident):
        with self.lock:
            if self.app.closed.is_set():raise ValueError('Applicazione in chiusura.')
            entry=self.entry(ident)
            if entry['received']!=entry['size'] or entry['path'].stat().st_size!=entry['size']: raise ValueError('Caricamento incompleto.')
            digest=None
            if entry['origin']=='generated':
                hasher=hashlib.sha256()
                with entry['path'].open('rb') as stream:
                    for chunk in iter(lambda:stream.read(CHUNK_BYTES),b''):hasher.update(chunk)
                digest=hasher.hexdigest()
                previous=self.app.store.one('SELECT id FROM gallery_exports WHERE hash=?',(digest,))
                if previous:
                    try: result=self.app.store.gallery.get(previous['id'])
                    except ValueError: pass
                    else:
                        self.cancel(ident)
                        return result
            result=self.publish(ident,entry['path'],entry['name'],entry['origin'])
            self.pending.pop(ident)
            if digest:self.app.store.execute('INSERT OR REPLACE INTO gallery_exports VALUES (?,?)',(digest,result['id']))
            return result

    def publish(self, ident, path, name, origin='uploaded'):
        ext,mime=identify(path,name)
        relative=f'uploads/{ident}/asset{ext}'; target=self.app.data/relative
        target.parent.mkdir(parents=True,exist_ok=True); path.replace(target)
        result={'id':ident,'name':name[:150],'path':relative,'mime':mime,'size':target.stat().st_size}
        try:
            (self.app.data/'uploads'/(ident+'.json')).write_text(json.dumps(result),encoding='utf-8')
            self.app.store.gallery.register([result],origin)
        except Exception:
            (self.app.data/'uploads'/(ident+'.json')).unlink(missing_ok=True)
            target.unlink(missing_ok=True);target.parent.rmdir()
            raise
        return result

    def cancel(self, ident):
        with self.lock:
            self.entry(ident)['path'].unlink(missing_ok=True); self.pending.pop(ident)
            return {'ok':True}

    def close(self):
        with self.lock:
            for entry in self.pending.values(): entry['path'].unlink(missing_ok=True)
            self.pending.clear()

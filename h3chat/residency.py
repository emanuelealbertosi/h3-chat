"""Process ownership and bounded, reclaimable mappings of recently used model files."""
from __future__ import annotations
import json
import mmap
import os
import queue
import subprocess
import threading
import time
from collections import OrderedDict
from pathlib import Path
from .downloads import Cancelled


class FileCache:
    def __init__(self):
        self.entries=OrderedDict();self.lock=threading.RLock();self.limit=0

    def configure(self, gib):
        with self.lock:
            self.limit=int(gib*1024**3)
            self._trim()

    def _trim(self):
        while self.entries and sum(v[1] for v in self.entries.values())>self.limit:
            _,(mapping,_,_)=self.entries.popitem(last=False);mapping.close()

    def remember(self, paths):
        # File-backed pages remain reclaimable: never mlock/VirtualLock or copy weights.
        with self.lock:
            if not self.limit:return
            for path in paths:
                try:
                    p=Path(path).resolve();st=p.stat();key=str(p)
                    if not st.st_size:continue
                    old=self.entries.pop(key,None)
                    if old:
                        if old[2]==st.st_mtime_ns:
                            self.entries[key]=old;continue
                        old[0].close()
                    length=min(st.st_size,self.limit)
                    while self.entries and sum(v[1] for v in self.entries.values())+length>self.limit:
                        _,(mapping,_,_)=self.entries.popitem(last=False);mapping.close()
                    with p.open('rb') as stream:mapping=mmap.mmap(stream.fileno(),length,access=mmap.ACCESS_READ)
                    self.entries[key]=(mapping,length,st.st_mtime_ns)
                except (OSError,ValueError,MemoryError):continue

    def forget(self, paths):
        with self.lock:
            for path in paths:
                value=self.entries.pop(str(Path(path).resolve()),None)
                if value:value[0].close()

    def clear(self):
        with self.lock:
            for mapping,_,_ in self.entries.values():mapping.close()
            self.entries.clear()

    def snapshot(self):
        with self.lock:return {'mapped_bytes':sum(v[1] for v in self.entries.values()),'limit_bytes':self.limit,'files':len(self.entries)}


class Session:
    def __init__(self, key, kind, model, files, settings, log_path):
        self.key,self.kind,self.model,self.files=key,kind,model,files
        self.settings=dict(settings);self.log_path=Path(log_path)
        self.process=None;self.log=None;self.port=None;self.api_key=None
        self.ready=False;self.events=queue.Queue();self.started=time.time();self.uses=0
        self.reader=None

    def alive(self):return self.process is not None and self.process.poll() is None

    def start(self,args,*,ipc=False,cwd=None):
        self.log_path.parent.mkdir(parents=True,exist_ok=True)
        self.log=self.log_path.open('wb')
        try:
            self.process=subprocess.Popen([str(a) for a in args],stdin=subprocess.PIPE if ipc else subprocess.DEVNULL,
                stdout=subprocess.PIPE if ipc else self.log,stderr=self.log,cwd=str(cwd or Path(args[0]).parent),
                creationflags=0x08000000 if os.name=='nt' else 0)
        except Exception:self.log.close();self.log=None;raise
        if ipc:
            def read():
                try:
                    while line:=self.process.stdout.readline(1024*1024):
                        try:self.events.put(json.loads(line))
                        except (ValueError,UnicodeDecodeError):self.events.put({'event':'error','message':'Risposta IPC del motore non valida.'});break
                except (OSError,ValueError):pass
                finally:self.events.put({'event':'exit'})
            self.reader=threading.Thread(target=read,daemon=True);self.reader.start()

    def send(self, value):
        if not self.alive():raise RuntimeError('Il processo del modello non è attivo.')
        raw=(json.dumps(value,ensure_ascii=False)+'\n').encode('utf-8')
        self.process.stdin.write(raw);self.process.stdin.flush()

    def wait(self, target, cancel, timeout, stage=None):
        deadline=time.monotonic()+timeout
        while time.monotonic()<deadline:
            if cancel.is_set():raise Cancelled()
            try:event=self.events.get(timeout=.15)
            except queue.Empty:
                if not self.alive():raise RuntimeError('Il motore immagini si è arrestato. Consulta il registro.')
                continue
            if event.get('event')==target:return event
            if event.get('event') in ('exit','error'):raise RuntimeError(event.get('message','Il motore immagini si è arrestato.'))
            if event.get('event')=='progress' and stage:
                stage(f"Generazione immagine · {event.get('step',0)}/{event.get('steps',0)} passi")
        raise RuntimeError('Tempo massimo del motore immagini superato.')

    def stop(self):
        self.ready=False
        if self.alive():
            self.process.terminate()
            try:self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:self.process.kill();self.process.wait(timeout=5)
        if self.process:
            for stream in (self.process.stdin,self.process.stdout):
                if stream:
                    try:stream.close()
                    except (OSError,ValueError):pass
        if self.reader:self.reader.join(timeout=2)
        if self.log:self.log.close();self.log=None

    def snapshot(self):
        gpu=self.settings['profile']!='cpu' and self.settings['backend']!='cpu'
        return {'id':self.model['id'],'name':self.model['name'],'kind':self.kind,
                'ready':self.ready and self.alive(),'pid':self.process.pid if self.alive() else None,
                'location':'VRAM' if gpu and self.settings.get('memory_policy')=='resident' else 'RAM / VRAM' if gpu else 'RAM',
                'mtp_tokens':next((v for k,v in self.key[2] if k=='mtp_tokens'),0) if self.ready else 0,
                'loras':getattr(self,'active_loras',[]),
                'uses':self.uses,'started':self.started}

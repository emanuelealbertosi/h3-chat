"""Project knowledge on local SQLite; optional GGUF semantic retrieval."""
from __future__ import annotations
import hashlib
import base64
import binascii
import json
import math
import os
import re
import secrets
import socket
import threading
import time
import urllib.request
from pathlib import Path
from .downloads import Cancelled, safe_join
from .residency import Session
from .store import uid

TEXT_EXTENSIONS={'.txt','.md','.csv','.json','.py','.js','.ts','.html','.css','.tex'}
EXTENSIONS=TEXT_EXTENSIONS|{'.pdf','.docx'}

def scan_folder(path):
    root=Path(path).resolve();files=[];seen=0
    for parent,dirs,names in os.walk(root,followlinks=False):
        directory=Path(parent)
        if len(directory.relative_to(root).parts)>=4:dirs[:]=[]
        else:dirs[:]=[n for n in dirs if not (directory/n).is_symlink() and (directory/n).resolve().is_relative_to(root) and n not in ('.git','node_modules','__pycache__','.venv')]
        for name in names:
            seen+=1
            if seen>10000:raise ValueError('Cartella troppo grande; scegli una sottocartella.')
            p=directory/name
            if p.suffix.lower() in EXTENSIONS and p.is_file() and not p.is_symlink() and p.resolve().is_relative_to(root):files.append(p)
            if len(files)>500:raise ValueError('Massimo 500 documenti per cartella.')
    return files

def validate(settings):
    if type(settings['rag_enabled']) is not bool:raise ValueError('RAG: scegli On oppure Off.')
    if type(settings['rag_top_k']) is not int or not 1<=settings['rag_top_k']<=12:raise ValueError('RAG: scegli da 1 a 12 estratti.')
    if settings['rag_embedding_profile'] not in ('embeddinggemma','plain','e5','nomic','ovis'):raise ValueError('Profilo embedding non valido.')
    model=settings['rag_embedding_model']
    if not isinstance(model,str) or len(model)>2000:raise ValueError('Percorso embedding non valido.')
    if model:
        p=Path(model)
        if settings['rag_embedding_profile']=='ovis':
            from .ovis import checkpoint
            checkpoint(p)
        elif not p.is_absolute() or p.suffix.lower()!='.gguf' or not p.is_file():raise ValueError('Scegli un file embedding GGUF esistente.')

def normalize(vector):
    if not isinstance(vector,list) or not 8<=len(vector)<=8192 or any(type(x) not in (int,float) or not math.isfinite(x) for x in vector):raise ValueError('Vettore embedding non valido.')
    norm=math.sqrt(sum(x*x for x in vector))
    if norm<=0:raise ValueError('Il modello ha prodotto un embedding nullo.')
    return [x/norm for x in vector]

class Embeddings:
    def __init__(self,root,data):self.root,self.data=Path(root),Path(data);self.lock=threading.RLock();self.session=None
    def key(self,settings):
        if settings['rag_embedding_profile']=='ovis':
            from .ovis import checkpoint,FORMAT_VERSION
            folder,files=checkpoint(settings['rag_embedding_model'])
            return hashlib.sha256(json.dumps([str(folder),[(p.name,p.stat().st_size,p.stat().st_mtime_ns) for p in files],FORMAT_VERSION,settings.get('rag_device','cpu')]).encode()).hexdigest()
        p=Path(settings['rag_embedding_model']);st=p.stat()
        return hashlib.sha256(json.dumps([str(p.resolve()),st.st_size,st.st_mtime_ns,settings['rag_embedding_profile'],settings.get('rag_device','cpu')]).encode()).hexdigest()
    def close(self):
        with self.lock:
            if self.session:self.session.stop();self.session=None
    def encode(self,texts,settings,cancel,stage,query=False):
        if settings['rag_embedding_profile']=='ovis':return self.encode_ovis(texts,settings,cancel,stage,query)
        from .engine import runtime_executable
        with self.lock:
            key=self.key(settings)
            if not self.session or self.session.key!=key or not self.session.alive():
                device='cuda' if settings.get('rag_device')=='gpu' else 'cpu'
                self.close();exe=runtime_executable(self.root,device,'llama')
                if not exe:raise ValueError('Installa il motore '+('CUDA' if device=='cuda' else 'CPU')+' dal Setup per la ricerca semantica.')
                s=Session(key,'embedding',{}, {},settings,self.data/'logs/embeddings.log');self.session=s
                with socket.socket() as sock:sock.bind(('127.0.0.1',0));s.port=sock.getsockname()[1]
                s.api_key=secrets.token_hex(24)
                stage('RAG · caricamento embedding · '+device.upper())
                s.start([exe,'--model',settings['rag_embedding_model'],'--host','127.0.0.1','--port',s.port,'--api-key',s.api_key,'--embedding','--n-gpu-layers',999 if device=='cuda' else 0,'--ctx-size',2048,'--batch-size',2048,'--ubatch-size',2048,'--parallel',1,'--threads',min(settings['threads'],8),'--no-webui'])
                deadline=time.monotonic()+120
                while True:
                    if cancel.is_set():self.close();raise Cancelled()
                    if not s.alive():self.close();raise ValueError('Avvio embedding fallito. Scegli un GGUF dedicato agli embedding; consulta logs/embeddings.log.')
                    try:
                        with self.exchange('/health',None,3) as r:
                            if r.status==200:break
                    except OSError:pass
                    if time.monotonic()>deadline:self.close();raise ValueError('Caricamento embedding scaduto.')
                    cancel.wait(.15)
            profile=settings['rag_embedding_profile'];result=[]
            for start in range(0,len(texts),8):
                if cancel.is_set():raise Cancelled()
                stage(f'RAG · embedding {'GPU' if settings.get('rag_device')=='gpu' else 'CPU'} {min(start+8,len(texts))}/{len(texts)}')
                batch=texts[start:start+8]
                if profile=='embeddinggemma':batch=[('task: search result | query: ' if query else 'title: none | text: ')+t for t in batch]
                elif profile=='e5':batch=[('query: ' if query else 'passage: ')+t for t in batch]
                elif profile=='nomic':batch=[('search_query: ' if query else 'search_document: ')+t for t in batch]
                with self.exchange('/v1/embeddings',{'input':batch},60) as r:value=json.load(r)
                rows=sorted(value['data'],key=lambda x:x['index'])
                if [r['index'] for r in rows]!=list(range(len(batch))):raise ValueError('Risposta embedding incompleta.')
                result.extend(normalize(r['embedding']) for r in rows)
            return result
    def encode_ovis(self,texts,settings,cancel,stage,query):
        from .ovis import runtime_ready
        with self.lock:
            if not runtime_ready(self.root):raise ValueError('Installa i componenti Ovis / Vision nelle Preferenze per usare questo embedding.')
            key=self.key(settings);device='cuda' if settings.get('rag_device')=='gpu' else 'cpu'
            try:
                if not self.session or self.session.key!=key or not self.session.alive():
                    self.close();s=Session(key,'embedding-ovis',{}, {},settings,self.data/'logs/embeddings.log');self.session=s
                    stage('RAG · avvio motore Ovis · '+device.upper())
                    s.start([self.root/'runtime/python/python.exe','-X','utf8',self.root/'native/embedding-worker.py'],ipc=True,cwd=self.root)
                    s.wait('hello',cancel,90,stage)
                    s.send({'op':'load','path':settings['rag_embedding_model'],'device':device,'threads':settings['threads']})
                    s.wait('loaded',cancel,600,stage)
                result=[]
                for start in range(0,len(texts),8):
                    if cancel.is_set():raise Cancelled()
                    stage(f'RAG · Ovis · {device.upper()} · estratti {start+1}–{min(start+8,len(texts))}/{len(texts)}')
                    self.session.send({'op':'encode','texts':texts[start:start+8],'query':query})
                    vectors=self.session.wait('result',cancel,600,stage).get('vectors',[])
                    if len(vectors)!=len(texts[start:start+8]) or any(not isinstance(v,list) or len(v)!=2048 for v in vectors):raise ValueError('Risposta Ovis incompleta.')
                    result.extend(normalize(v) for v in vectors)
                return result
            except BaseException:
                self.close();raise
    def exchange(self,path,body,timeout):
        s=self.session;req=urllib.request.Request(f'http://127.0.0.1:{s.port}'+path,data=json.dumps(body).encode() if body is not None else None,headers={'Authorization':'Bearer '+s.api_key,'Content-Type':'application/json'})
        return urllib.request.build_opener(urllib.request.ProxyHandler({})).open(req,timeout=timeout)

class Knowledge:
    def __init__(self,root,store):
        self.root,self.store,self.data=Path(root),store,store.root
        self.embeddings=Embeddings(root,self.data);self.index_lock=threading.RLock();self.tasks={};self.lock=threading.RLock();self.closed=threading.Event();self.readers=set()
    def list(self):return self.store.all('SELECT p.*, (SELECT COUNT(*) FROM project_sources s WHERE s.project_id=p.id) AS source_count FROM projects p ORDER BY name')
    def project(self,ident):
        p=self.store.one('SELECT * FROM projects WHERE id=?',(ident,))
        if not p:raise ValueError('Progetto non trovato.')
        p['sources']=self.store.all('SELECT s.*, (SELECT COUNT(*) FROM rag_chunks c WHERE c.source_id=s.id) AS chunks FROM project_sources s WHERE project_id=? ORDER BY name',(ident,))
        for source in p['sources']:source['imported']=Path(source['path']).is_relative_to(self.data/'project-imports')
        p['roots']=self.store.all('SELECT * FROM project_roots WHERE project_id=?',(ident,))
        with self.lock:p['indexing']=self.tasks.get(ident,{}).get('status')=='running';p['progress']=dict(self.tasks.get(ident,{}))
        return p
    def save(self,body,ident=None):
        if ident:self.project(ident)
        name=body.get('name','');instructions=body.get('instructions','');only=body.get('sources_only',False)
        if not isinstance(name,str) or not name.strip() or len(name)>80:raise ValueError('Nome progetto: da 1 a 80 caratteri.')
        if not isinstance(instructions,str) or len(instructions)>8000:raise ValueError('Istruzioni progetto: massimo 8000 caratteri.')
        if type(only) is not bool:raise ValueError('Solo fonti: scegli attivo o disattivo.')
        if ident:self.store.execute('UPDATE projects SET name=?,instructions=?,sources_only=? WHERE id=?',(name.strip(),instructions,int(only),ident))
        else:
            ident=uid();self.store.execute('INSERT INTO projects VALUES (?,?,?,?,?)',(ident,name.strip(),instructions,int(only),time.time()))
        return self.project(ident)
    def mutable(self,ident):
        self.project(ident)
        if self.tasks.get(ident,{}).get('status')=='running':raise ValueError('Attendi il completamento dell’indicizzazione.')
        if self.store.one("SELECT j.id FROM jobs j JOIN chats c ON c.id=j.chat_id WHERE c.project_id=? AND j.status IN ('queued','running')",(ident,)):raise ValueError('Attendi o interrompi i lavori nel progetto.')
    def delete(self,ident):
        with self.index_lock:self.mutable(ident);self.store.execute('DELETE FROM projects WHERE id=?',(ident,))
        return {'ok':True}
    def import_file(self,ident,body):
        """Browser-selected files have no trustworthy original filesystem path."""
        name=body.get('name','');encoded=body.get('data','');defer=body.get('defer',False)
        if not isinstance(name,str) or not 1<=len(name)<=200 or any(x in name for x in ('/','\\','\0')):
            raise ValueError('Nome documento non valido.')
        extension=Path(name).suffix.lower()
        label=body.get('relative_path') or name
        if not isinstance(label,str) or len(label)>1200 or label.startswith('/') or any(x in label for x in ('\\',':','\0')) or any(part in ('','..','.') for part in label.split('/')) or label.split('/')[-1]!=name:
            raise ValueError('Nome della cartella importata non valido.')
        if extension not in EXTENSIONS:raise ValueError('Usa PDF, Word .docx oppure file di testo/codice.')
        if not isinstance(encoded,str) or len(encoded)>35*1024**2 or type(defer) is not bool:raise ValueError('Documento non valido o oltre 25 MB.')
        try:raw=base64.b64decode(encoded,validate=True)
        except (ValueError,binascii.Error):raise ValueError('Contenuto documento non valido.')
        if not raw or len(raw)>25*1024**2:raise ValueError('Documento vuoto o oltre 25 MB.')
        if extension=='.pdf' and not raw.startswith(b'%PDF-'):raise ValueError('Il file non è un PDF valido.')
        if extension=='.docx':
            import io,zipfile
            try:
                with zipfile.ZipFile(io.BytesIO(raw)) as z:
                    items=z.infolist();names={x.filename for x in items}
                    if not {'[Content_Types].xml','word/document.xml'}<=names or len(items)>10000 or sum(x.file_size for x in items)>100*1024**2 or any('vbaproject' in n.lower() for n in names):
                        raise ValueError('Documento Word non valido, troppo grande o con macro.')
            except zipfile.BadZipFile:raise ValueError('Documento Word non valido.')
        digest=hashlib.sha256(label.encode('utf-8')+b'\0'+raw).hexdigest()
        with self.index_lock:
            self.mutable(ident)
            target=safe_join(self.data,'project-imports/'+ident+'/'+digest+'/document'+extension)
            existing=self.store.one('SELECT id FROM project_sources WHERE project_id=? AND path=?',(ident,str(target)))
            duplicate=bool(existing)
            if not duplicate and self.store.one('SELECT COUNT(*) AS n FROM project_sources WHERE project_id=?',(ident,))['n']>=500:raise ValueError('Massimo 500 documenti per progetto.')
            target.parent.mkdir(parents=True,exist_ok=True)
            if not duplicate or not target.is_file():
                temporary=target.with_name(uid()+'.writing')
                try:temporary.write_bytes(raw);temporary.replace(target)
                finally:temporary.unlink(missing_ok=True)
            source_id=existing['id'] if existing else uid()
            self.store.execute('INSERT OR IGNORE INTO project_sources(id,project_id,path,name) VALUES (?,?,?,?)',(source_id,ident,str(target),label))
        if not defer:self.refresh(ident)
        return {'id':source_id,'name':name,'duplicate':duplicate}
    def add(self,ident,body):
        paths=body.get('paths',[])
        if not isinstance(paths,list) or not 1<=len(paths)<=30 or any(not isinstance(p,str) or len(p)>2000 for p in paths):raise ValueError('Scegli fino a trenta file o cartelle.')
        files=[];roots=[]
        for raw in paths:
            p=Path(raw)
            if not p.is_absolute() or not p.exists():raise ValueError('File o cartella non trovati: '+raw)
            if p.is_dir():
                roots.append(p.resolve());files.extend(scan_folder(p))
            elif p.suffix.lower() in EXTENSIONS:files.append(p)
            else:raise ValueError('Formato non supportato. Usa PDF, DOCX o file di testo/codice.')
        if not files:raise ValueError('Nessun documento supportato nella selezione.')
        with self.index_lock:
            self.mutable(ident)
            with self.store.connect() as db:
                for p in roots:db.execute('INSERT OR IGNORE INTO project_roots VALUES (?,?,?)',(uid(),ident,str(p)))
                for p in files:
                    if p.stat().st_size>25*1024**2:raise ValueError('Documento oltre 25 MB: '+p.name)
                    db.execute('INSERT OR IGNORE INTO project_sources(id,project_id,path,name) VALUES (?,?,?,?)',(uid(),ident,str(p.resolve()),p.name))
                    db.execute('DELETE FROM project_exclusions WHERE project_id=? AND path=?',(ident,str(p.resolve())))
                if db.execute('SELECT COUNT(*) FROM project_sources WHERE project_id=?',(ident,)).fetchone()[0]>500:raise ValueError('Massimo 500 documenti per progetto.')
        return self.refresh(ident)
    def remove(self,ident,source):
        with self.index_lock:
            self.mutable(ident)
            row=self.store.one('SELECT path FROM project_sources WHERE id=? AND project_id=?',(source,ident))
            if row:self.store.execute('INSERT OR IGNORE INTO project_exclusions VALUES (?,?)',(ident,row['path']))
            self.store.execute('DELETE FROM project_sources WHERE id=? AND project_id=?',(source,ident))
        return self.project(ident)
    def refresh(self,ident):
        self.project(ident)
        with self.lock:
            if self.closed.is_set():raise ValueError('Applicazione in chiusura.')
            if self.tasks.get(ident,{}).get('status')=='running':return {'ok':True,'status':'running'}
            self.tasks[ident]={'status':'running','stage':'Indicizzazione in attesa','error':''}
        def work():
            try:
                with self.index_lock:self.index(ident,self.store.settings(),self.closed,lambda s:self.progress(ident,s))
                with self.lock:self.tasks[ident].update(status='done',stage='Indice aggiornato')
            except Exception as e:
                with self.lock:self.tasks[ident].update(status='failed',error=str(e),stage='Indicizzazione interrotta')
        threading.Thread(target=work,daemon=True).start()
        return {'ok':True,'status':'running'}
    def progress(self,ident,stage):
        with self.lock:self.tasks[ident]['stage']=stage
    def read(self,source,cancel,stage):
        path=Path(source['path'])
        if path.stat().st_size>25*1024**2:raise ValueError('Documento oltre 25 MB.')
        if path.suffix.lower() in TEXT_EXTENSIONS:
            text=path.read_text(encoding='utf-8-sig',errors='replace')
            if len(text)>2000000:raise ValueError('Massimo due milioni di caratteri per documento.')
            blocks=[];lines=text.splitlines(keepends=True);current='';first=1
            for n,line in enumerate(lines,1):
                if current and len(current)+len(line)>1600:blocks.append({'location':f'righe {first}–{n-1}','page':None,'text':current});current='';first=n
                current+=line
            if current:blocks.append({'location':f'righe {first}–{len(lines)}','page':None,'text':current})
            return blocks,[]
        from .tools_runtime import status
        if not status(self.root)['documents']['ready']:raise ValueError('Installa i componenti PDF/Word dal Setup.')
        output=safe_join(self.data,'project-cache/'+source['id']+'.json');session=Session(('project-read',source['id']),'documents',{}, {},{},self.data/'logs'/('project-'+source['id']+'.log'))
        with self.lock:self.readers.add(session)
        try:
            session.start([self.root/'runtime/python/python.exe','-X','utf8',self.root/'native/document-worker.py'],ipc=True,cwd=self.root)
            session.wait('hello',cancel,30,stage);session.send({'op':'read','path':str(path),'output':str(output)});session.wait('result',cancel,90,stage)
            document=json.loads(output.read_text(encoding='utf-8'));return document['blocks'],document['warnings']
        finally:
            session.stop()
            with self.lock:self.readers.discard(session)
    def index(self,ident,settings,cancel,stage,*,release=True):
        model_key=self.embeddings.key(settings) if settings['rag_embedding_model'] else ''
        excluded={r['path'] for r in self.store.all('SELECT path FROM project_exclusions WHERE project_id=?',(ident,))}
        with self.store.connect() as db:
            for row in db.execute('SELECT path FROM project_roots WHERE project_id=?',(ident,)).fetchall():
                if not Path(row['path']).is_dir():continue
                for path in scan_folder(row['path']):
                    if str(path.resolve()) not in excluded:db.execute('INSERT OR IGNORE INTO project_sources(id,project_id,path,name) VALUES (?,?,?,?)',(uid(),ident,str(path.resolve()),path.name))
            if db.execute('SELECT COUNT(*) FROM project_sources WHERE project_id=?',(ident,)).fetchone()[0]>500:raise ValueError('Massimo 500 documenti per progetto.')
        sources=self.project(ident)['sources']
        try:
            for n,source in enumerate(sources,1):
                if cancel.is_set():raise Cancelled()
                stage(f"RAG · documento {n}/{len(sources)} · {source['name']}")
                try:
                    path=Path(source['path']);st=path.stat();fingerprint=f'{st.st_mtime_ns}:{st.st_size}'
                    if source['fingerprint']!=fingerprint or source['status']!='ready':
                        self.store.execute("UPDATE project_sources SET status='indexing',error='' WHERE id=?",(source['id'],))
                        blocks,warnings=self.read(source,cancel,stage)
                        # Bound pathological single lines and preserve the original location.
                        chunks=[b|{'text':b['text'][j:j+1600]} for b in blocks for j in range(0,len(b['text']),1600) if b['text'][j:j+1600].strip()]
                        if len(chunks)>5000:raise ValueError('Troppi estratti nel documento.')
                        vectors=self.embeddings.encode([b['text'] for b in chunks],settings,cancel,stage) if model_key and chunks else [None]*len(chunks)
                        if path.stat().st_mtime_ns!=st.st_mtime_ns or path.stat().st_size!=st.st_size:raise ValueError('Documento modificato durante la lettura; aggiorna l’indice.')
                        with self.store.connect() as db:
                            db.execute('DELETE FROM rag_chunks WHERE source_id=?',(source['id'],))
                            db.executemany('INSERT INTO rag_chunks(source_id,location,page,text,embedding,embedding_key) VALUES (?,?,?,?,?,?)',[(source['id'],b['location'],b.get('page'),b['text'],json.dumps(v) if v else None,model_key) for b,v in zip(chunks,vectors)])
                            db.execute("UPDATE project_sources SET status='ready',fingerprint=?,error=?,updated=? WHERE id=?",(fingerprint,' '.join(warnings),time.time(),source['id']))
                    elif model_key:
                        chunks=self.store.all('SELECT id,text FROM rag_chunks WHERE source_id=? AND embedding_key!=?',(source['id'],model_key))
                        for start in range(0,len(chunks),32):
                            part=chunks[start:start+32];vectors=self.embeddings.encode([b['text'] for b in part],settings,cancel,stage)
                            with self.store.connect() as db:db.executemany('UPDATE rag_chunks SET embedding=?,embedding_key=? WHERE id=?',[(json.dumps(v),model_key,b['id']) for b,v in zip(part,vectors)])
                except Cancelled:raise
                except Exception as e:
                    self.store.execute("UPDATE project_sources SET status='error',error=? WHERE id=?",(str(e),source['id']))
        finally:
            if release:self.embeddings.close()
    def retrieve(self,ident,query,settings,cancel,stage,source_ids=None):
        with self.index_lock:
            try:return self._retrieve(ident,query,settings,cancel,stage,source_ids)
            finally:self.embeddings.close()
    def _retrieve(self,ident,query,settings,cancel,stage,source_ids=None):
        project=self.project(ident)
        self.index(ident,settings,cancel,stage,release=False)
        if source_ids is not None and (not isinstance(source_ids,list) or any(not isinstance(x,str) for x in source_ids)):raise ValueError('Selezione fonti non valida.')
        where="s.project_id=? AND s.status='ready'";args=[ident]
        if source_ids is not None:
            if not source_ids:return [],'nessuna fonte selezionata'
            valid={s['id'] for s in project['sources']}
            if set(source_ids)-valid:raise ValueError('La fonte non appartiene al progetto.')
            where+=' AND s.id IN ('+','.join('?' for _ in source_ids)+')';args+=source_ids
        pages={int(n) for n in re.findall(r'\b(?:pagina|page)\s+(\d+)',query,re.I)}
        if pages:where+=' AND (c.page IS NULL OR c.page IN ('+','.join('?' for _ in pages)+'))';args+=sorted(pages)
        base='SELECT c.*,s.name,s.path,s.source_url FROM rag_chunks c JOIN project_sources s ON s.id=c.source_id WHERE '+where
        terms=list(dict.fromkeys(re.findall(r'\w{2,}',query.lower())))[:40];rank={};mode='lessicale'
        if terms:
            match=' OR '.join('"'+t+'"' for t in terms)
            rows=self.store.all(base+' AND c.id IN (SELECT rowid FROM rag_fts WHERE rag_fts MATCH ?) ORDER BY (SELECT bm25(rag_fts) FROM rag_fts WHERE rowid=c.id AND rag_fts MATCH ?) LIMIT 80',args+[match,match])
            for i,row in enumerate(rows):rank[row['id']]=[1/(60+i),row]
        if settings['rag_embedding_model']:
            try:
                key=self.embeddings.key(settings);vector=self.embeddings.encode([query],settings,cancel,stage,query=True)[0]
                rows=self.store.all(base+' AND c.embedding_key=? AND c.embedding IS NOT NULL',args+[key])
                scored=[]
                for row in rows:
                    values=json.loads(row['embedding'])
                    if len(values)==len(vector):scored.append((sum(a*b for a,b in zip(vector,values)),row))
                for i,(_,row) in enumerate(sorted(scored,key=lambda x:-x[0])[:80]):
                    entry=rank.setdefault(row['id'],[0,row]);entry[0]+=1/(60+i)
                mode='ibrida · '+('GPU' if settings.get('rag_device')=='gpu' else 'CPU')
            finally:self.embeddings.close()
        selected=[r for _,r in sorted(rank.values(),key=lambda x:-x[0])[:settings['rag_top_k']]]
        # Explicit summaries can sample the document; unrelated questions never receive fake relevant hits.
        if not selected and (settings.get('_rag_overview') or re.search(r'riassum|sintesi|summary|summariz|panoramica|\bmanim\b',query,re.I)):
            selected=self.store.all(base+' ORDER BY row_number() OVER (PARTITION BY s.id ORDER BY c.id),s.name,c.id LIMIT ?',args+[settings['rag_top_k']])
        return selected,mode
    def close(self):
        self.closed.set()
        with self.lock:
            for s in list(self.readers):s.stop()
        self.embeddings.close()

def grounded(text,sources):
    """Only real retrieved references become clickable. Claims are not fact-checked."""
    ids={s['citation'] for s in sources};unknown=[]
    def replace(m):
        key=m[1]
        if key in ids:return f'[{key}](#rag-{key})'
        unknown.append(key);return '[riferimento non disponibile]'
    # Skip fenced code: citation syntax can be legitimate program data.
    parts=re.split(r'(```[\s\S]*?```)',text)
    for i in range(0,len(parts),2):parts[i]=re.sub(r'\[(R\d+)\](?:\([^\n)]*\))?',replace,parts[i])
    return ''.join(parts),list(dict.fromkeys(unknown))

def quote_warnings(text,sources):
    by_id={s['citation']:s for s in sources};warnings=[]
    normalize_text=lambda s:re.sub(r'\s+',' ',s).strip()
    parts=re.split(r'(```[\s\S]*?```)',text)
    for part in parts[::2]:
        for match in re.finditer(r'["“]([^"”]{8,})["”]\s*\[(R\d+)\]',part):
            quote,key=match.groups();source=by_id.get(key)
            if source and normalize_text(quote) not in normalize_text(source['text']):warnings.append(key+': il testo tra virgolette non coincide con l’estratto recuperato.')
        for match in re.finditer(r'^>\s+(?!\[!)(.+?)\s*\[(R\d+)\]',part,re.M):
            quote,key=match.groups();source=by_id.get(key)
            if source and normalize_text(quote.strip('"“”')) not in normalize_text(source['text']):warnings.append(key+': la citazione nel riquadro non coincide con l’estratto recuperato.')
    return list(dict.fromkeys(warnings))

"""Explicit canvas image selection: project visuals and Wikimedia Commons."""
import base64
import json
import re
import subprocess
import tempfile
from pathlib import Path
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from .downloads import safe_join
from .web_search import Redirects,public_url
from .engine import CREATE_NO_WINDOW

USER_AGENT='H3-Chat/0.16 (https://github.com/emanuelealbertosi/h3-chat)'

def download(url,limit=12*1024**2):
    p=urllib.parse.urlsplit(url)
    if p.scheme!='https' or p.hostname not in ('commons.wikimedia.org','upload.wikimedia.org'):raise ValueError('Scegli un risultato di Wikimedia Commons.')
    public_url(url)
    req=urllib.request.Request(url,headers={'User-Agent':USER_AGENT,'Accept-Encoding':'identity'})
    with urllib.request.build_opener(Redirects()).open(req,timeout=25) as response:
        if urllib.parse.urlsplit(response.url).hostname not in ('commons.wikimedia.org','upload.wikimedia.org'):raise ValueError('Redirect immagine non consentito.')
        raw=response.read(limit+1)
    if len(raw)>limit:raise ValueError('Immagine troppo grande (massimo 12 MB).')
    return raw

def raster(app,raw,thumbnail=False):
    if len(raw)>32*1024**2:raise ValueError('Immagine troppo grande.')
    cache=app.data/'document-cache';cache.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(dir=cache,prefix='slide-image-') as folder:
        source=safe_join(Path(folder),'input');target=safe_join(Path(folder),'output.jpg');source.write_bytes(raw)
        result=subprocess.run([str(app.root/'runtime/python/python.exe'),'-X','utf8',str(app.root/'native/slide-image-worker.py')],input=json.dumps({'path':str(source),'output':str(target),'thumbnail':thumbnail}),text=True,capture_output=True,timeout=45,creationflags=CREATE_NO_WINDOW)
        if result.returncode:raise ValueError('Immagine non decodificabile. Verifica che il motore Documenti sia installato.')
        return target.read_bytes()

def thumb(app,raw):
    return 'data:image/jpeg;base64,'+base64.b64encode(raster(app,raw,True)).decode()

def project_row(app,chat_id,chunk_id):
    return app.store.one('SELECT c.id,c.image_path,c.location,s.name FROM rag_chunks c JOIN project_sources s ON s.id=c.source_id JOIN chats h ON h.project_id=s.project_id WHERE h.id=? AND c.id=? AND c.image_path!=\'\'',(chat_id,chunk_id))

def request(app,operation,body):
    chat_id=body.get('chat_id');chat=app.store.chat(chat_id)
    if operation=='rag':
        query=body.get('query','')
        if not isinstance(query,str) or len(query)>200:raise ValueError('Ricerca immagini non valida.')
        offset=body.get('offset',0)
        if type(offset) is not int or not 0<=offset<=20000:raise ValueError('Pagina immagini non valida.')
        rows=app.store.all("SELECT c.id,c.image_path,c.location,s.name FROM rag_chunks c JOIN project_sources s ON s.id=c.source_id WHERE s.project_id=? AND c.image_path!='' AND (s.name LIKE ? OR c.text LIKE ?) ORDER BY s.name,c.page,c.id LIMIT 25 OFFSET ?",(chat.get('project_id'),'%'+query+'%','%'+query+'%',offset))
        items=[]
        for row in rows[:24]:
            path=safe_join(app.data,row['image_path'])
            if path.is_file():items.append({'id':row['id'],'name':row['name']+' · '+row['location'],'thumbnail':thumb(app,path.read_bytes())})
        return {'items':items,'more':len(rows)>24}
    if operation=='search':
        query=body.get('query','')
        if not isinstance(query,str) or not 1<=len(query.strip())<=200:raise ValueError('Scrivi cosa cercare.')
        params={'action':'query','format':'json','generator':'search','gsrsearch':query+' filetype:bitmap','gsrnamespace':6,'gsrlimit':8,'prop':'imageinfo','iiprop':'url|extmetadata','iiurlwidth':320,'iiextmetadatafilter':'Artist|LicenseShortName|Credit'}
        payload=json.loads(download('https://commons.wikimedia.org/w/api.php?'+urllib.parse.urlencode(params),2*1024**2))
        rows=[]
        for page in payload.get('query',{}).get('pages',{}).values():
            info=page.get('imageinfo',[{}])[0];url=info.get('thumburl') or info.get('url','');metadata=info.get('extmetadata',{})
            if not url or urllib.parse.urlsplit(url).hostname!='upload.wikimedia.org':continue
            plain=lambda key:re.sub('<[^>]*>','',metadata.get(key,{}).get('value',''))[:300]
            rows.append({'name':page['title'].removeprefix('File:'),'url':url,'source_url':info.get('descriptionurl',''),'credit':plain('Artist'),'license':plain('LicenseShortName')})
        def preview(row):
            try:return row|{'thumbnail':thumb(app,download(row['url'],2*1024**2))}
            except (OSError,ValueError):return None
        with ThreadPoolExecutor(max_workers=4) as pool:items=[x for x in pool.map(preview,rows) if x]
        return {'items':items,'provider':'Wikimedia Commons'}
    if operation=='import':
        if body.get('source')=='rag':
            row=project_row(app,chat_id,body.get('id'))
            if not row:raise ValueError('Figura non presente nel progetto della chat.')
            raw=safe_join(app.data,row['image_path']).read_bytes();name=row['name']+' · '+row['location'];provenance={'kind':'rag','chunk_id':row['id'],'label':name}
        elif body.get('source')=='web':
            raw=download(body.get('url',''));name=str(body.get('name','Immagine web'))[:150]
            provenance={'kind':'web','url':body.get('source_url',''),'credit':str(body.get('credit',''))[:300],'license':str(body.get('license',''))[:150]}
        else:raise ValueError('Origine immagine non valida.')
        media=app.upload({'name':name,'data':base64.b64encode(raster(app,raw)).decode()});media['provenance']=provenance
        safe_join(app.data,media['path']).with_suffix('.json').write_text(json.dumps(media),encoding='utf-8')
        return media
    raise ValueError('Operazione immagini sconosciuta.')

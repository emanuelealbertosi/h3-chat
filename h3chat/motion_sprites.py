"""Explicit, account-local reusable vector artwork. Projects embed their own copy."""
import copy,hashlib,json,re,threading,time,unicodedata
from pathlib import Path
from uuid import uuid4
from .downloads import safe_join
from .infographic_scene import validate

_lock=threading.RLock()

def folder(app):return app.data/'motion-sprites'

def index(app):
    path=folder(app)/'index.json'
    if path.exists():return json.loads(path.read_text(encoding='utf8'))
    return [{k:v for k,v in json.loads(p.read_text(encoding='utf8')).items() if k not in ('scene','media')} for p in folder(app).glob('*.json') if re.fullmatch('[0-9a-f]{32}',p.stem)]

def write_index(app,rows):
    path=folder(app)/'index.json';temp=path.with_suffix('.tmp');temp.write_text(json.dumps(rows,ensure_ascii=False),encoding='utf8');temp.replace(path)

def words(text):return set(re.findall(r'[^\W_]+',unicodedata.normalize('NFKC',text).casefold()))

def listing(app,query=''):
    if not isinstance(query,str) or len(query)>200:raise ValueError('Ricerca sprite non valida.')
    terms=words(query);rows=[]
    for item in index(app):
        tokens=words(' '.join([item['name'],item['description'],item['style'],*item['tags'],*item['palette']]))
        score=len(terms&tokens)
        if terms and not terms<=tokens:continue
        rows.append(item|{'search_score':score})
    return [selected(app,[r['id']])[0]|{'search_score':r['search_score']} for r in sorted(rows,key=lambda x:(-x['search_score'],-x['created']))[:100]]

def selected(app,ids):
    if not isinstance(ids,list) or len(ids)>12 or any(not isinstance(i,str) for i in ids) or len(set(ids))!=len(ids):raise ValueError('Scegli al massimo dodici sprite distinti.')
    rows=[]
    for ident in ids:
        if not isinstance(ident,str) or not re.fullmatch('[0-9a-f]{32}',ident):raise ValueError('Sprite non valido.')
        path=safe_join(folder(app),ident+'.json')
        if not path.is_file():raise ValueError('Sprite non disponibile: seleziona di nuovo dalla raccolta.')
        item=json.loads(path.read_text(encoding='utf8'));validate(item['scene'])
        if item.get('rig'):
            from .motion_rigs import validate_rig
            validate_rig(item['scene'],item['rig'])
        for media in item.get('media',[]):
            if not re.fullmatch(r'outputs/motion-sprite-assets/[0-9a-f]{64}\.(png|jpg|webp)',media['path']) or not safe_join(app.data,media['path']).is_file():raise ValueError('Immagine dello sprite non disponibile.')
        rows.append(item)
    return rows

def save(app,body):
    if not isinstance(body,dict) or body.get('confirmed') is not True:raise ValueError('Conferma il salvataggio e la catalogazione dello sprite.')
    scene=validate(body.get('scene'));meta={}
    images={o['assetId'] for o in scene['objects'] if o['type']=='image'};media=[]
    if images:
        if len(images)>12:raise ValueError('Uno sprite può contenere al massimo dodici immagini.')
        source=app.store.canvas_history.get(body.get('chat_id'),body.get('artifact_id'));allowed={m['id']:m for m in source['media'] if m.get('mime') in ('image/png','image/jpeg','image/webp')};total=0
        for ident in images:
            if ident not in allowed:raise ValueError('Immagine non presente nel progetto selezionato.')
            m=allowed[ident];path=safe_join(app.data,m['path']);size=path.stat().st_size;total+=size
            if size>16*1024**2 or total>64*1024**2:raise ValueError('Immagini sprite oltre il budget di64MB complessivi o16MB per immagine.')
            data=path.read_bytes();digest=hashlib.sha256(data).hexdigest();ext={'image/png':'.png','image/jpeg':'.jpg','image/webp':'.webp'}[m['mime']];relative='outputs/motion-sprite-assets/'+digest+ext;target=safe_join(app.data,relative);target.parent.mkdir(parents=True,exist_ok=True)
            if not target.exists():
                temp=target.with_name(target.name+'.'+uuid4().hex+'.tmp');temp.write_bytes(data);temp.replace(target)
            new_id=uuid4().hex;media.append({'id':new_id,'name':m['name'],'path':relative,'mime':m['mime']})
            for o in scene['objects']:
                if o.get('assetId')==ident:o['assetId']=new_id
    for key,limit in [('name',100),('description',1200),('style',160)]:
        value=body.get(key,'')
        if not isinstance(value,str) or not value.strip() or len(value)>limit:raise ValueError('Compila nome, descrizione e stile dello sprite.')
        meta[key]=value.strip()
    tags=body.get('tags',[])
    if not isinstance(tags,list) or len(tags)>30 or any(not isinstance(t,str) or not 1<=len(t.strip())<=60 for t in tags):raise ValueError('Tag sprite non validi.')
    if any(o.get('tracks') for o in scene['objects']) or scene['camera']['keyframes']:raise ValueError('Salva una posa statica dello sprite, senza tracce o camera.')
    palette=sorted({o[k] for o in scene['objects'] for k in ('fill','stroke') if o[k]!='none'})
    digest=hashlib.sha256(json.dumps(scene,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    item=meta|{'version':1,'id':uuid4().hex,'created':time.time(),'metadata_origin':'user-confirmed','tags':list(dict.fromkeys(t.strip() for t in tags)),'palette':palette,'sha256':digest,'scene':scene,'media':media}
    if body.get('rig'):
        from .motion_rigs import validate_rig
        item['rig']=validate_rig(scene,body['rig'])
    with _lock:
        folder(app).mkdir(parents=True,exist_ok=True)
        rows=index(app)
        if len(rows)>=1000:raise ValueError('Raccolta piena: elimina gli sprite non usati prima di salvarne altri.')
        path=folder(app)/(item['id']+'.json');temp=path.with_suffix('.tmp');temp.write_text(json.dumps(item,ensure_ascii=False,indent=2),encoding='utf8');temp.replace(path)
        write_index(app,rows+[{k:v for k,v in item.items() if k not in ('scene','media')}])
    return item

def remove(app,ident,body):
    selected(app,[ident])
    if body.get('confirmed') is not True:raise ValueError('Conferma l’eliminazione dalla raccolta e dal disco.')
    with _lock:
        rows=index(app);safe_join(folder(app),ident+'.json').unlink();write_index(app,[r for r in rows if r['id']!=ident])
    return {'deleted':True,'saved_projects_unchanged':True}

def expand(scene,sprites):
    """Instantiate only explicitly selected library items, without another model."""
    out=copy.deepcopy(scene);lookup={s['id']:s for s in sprites};objects=[]
    for obj in out.get('objects',[]):
        ident=obj.pop('spriteId',None)
        if ident is None:objects.append(obj);continue
        if ident not in lookup or obj.get('type')!='group':raise ValueError('La scena usa uno sprite non selezionato.')
        if lookup[ident].get('rig'):
            from .motion_rigs import instantiate
            objects.extend(instantiate(lookup[ident],obj,scene['duration']));continue
        if any(k in obj for k in ('gesture','actionStart','actionEnd')):raise ValueError('Questo sprite non contiene articolazioni animabili.')
        objects.append(obj);sprite=lookup[ident]['scene'];mapping={o['id']:obj['id'][:54]+'_'+str(i) for i,o in enumerate(sprite['objects'])}
        for child in copy.deepcopy(sprite['objects']):
            child['parentId']=mapping[child['parentId']] if child.get('parentId') else obj['id'];child['parallax']=1;child['id']=mapping[child['id']];objects.append(child)
    out['objects']=objects
    return validate(out)

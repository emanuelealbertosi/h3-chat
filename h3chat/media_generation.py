"""Creation recipes: read workspace history and preserve portable PNG metadata."""
import json,re,struct,time,zlib
from pathlib import Path
from .downloads import safe_join
from .image_options import OVERRIDE_KEYS,validate_overrides

PNG=b'\x89PNG\r\n\x1a\n'
KEY=b'h3_creation'


def asset(value):
    return {k:value[k] for k in ('id','name','mime') if k in value}


def clean(value,key=''):
    if isinstance(value,dict):
        return {k:clean(v,k) for k,v in value.items() if not re.search(r'password|token|secret|api_key|authorization',k,re.I)}
    if isinstance(value,list):return [clean(v,key) for v in value[:512]]
    if isinstance(value,str):
        if key in ('path','directory') or re.match(r'^(?:[A-Za-z]:[\\/]|[/\\])',value):return value.replace('\\','/').rsplit('/',1)[-1]
        return value[:32000]
    return value if value is None or type(value) in (bool,int,float) else str(value)


def png_recipe(path):
    with path.open('rb') as stream:
        if stream.read(8)!=PNG:return None
        while header:=stream.read(8):
            if len(header)!=8:return None
            size,kind=struct.unpack('>I4s',header)
            if size>128*1024**2:return None
            if kind==b'tEXt' and size<=1024**2:
                raw=stream.read(size);stream.read(4)
                if raw.startswith(KEY+b'\0'):
                    value=json.loads(raw[len(KEY)+1:].decode('ascii'))
                    return value if isinstance(value,dict) else None
            else:stream.seek(size+4,1)
            if kind==b'IEND':return None


def embed_png(path,recipe):
    """Insert text chunks without decoding, resampling or recompressing pixels."""
    raw=path.read_bytes()
    if not raw.startswith(PNG):return False
    data=KEY+b'\0'+json.dumps(recipe,ensure_ascii=True,separators=(',',':')).encode('ascii')
    if len(data)>1024**2:raise ValueError('Ricetta troppo grande per i metadati PNG.')
    chunk=struct.pack('>I',len(data))+b'tEXt'+data+struct.pack('>I',zlib.crc32(b'tEXt'+data)&0xffffffff)
    chunks=[PNG];offset=8;finished=False;inserted=False
    while offset+12<=len(raw):
        size,kind=struct.unpack('>I4s',raw[offset:offset+8]);end=offset+12+size
        if end>len(raw):raise ValueError('PNG incompleto.')
        if kind in (b'IDAT',b'IEND') and not inserted:chunks.append(chunk);inserted=True
        if kind==b'IEND':finished=True
        if not (kind==b'tEXt' and raw[offset+8:offset+8+len(KEY)+1]==KEY+b'\0'):chunks.append(raw[offset:end])
        offset=end
        if finished:chunks.append(raw[offset:]);break
    if not finished:raise ValueError('PNG senza chiusura.')
    part=path.with_name(path.name+'.metadata.tmp')
    try:part.write_bytes(b''.join(chunks));part.replace(path)
    finally:part.unlink(missing_ok=True)
    return True


def record_image(app,media,model,parameters,prompt,references,loras):
    from .loras import public
    generation=dict(media.get('generation') or {})|dict(parameters)
    generation.update(image_model_id=model['id'],model=model['name'],prompt=prompt,
                      reference_assets=[asset(r) for r in references],loras=public(loras),completed_at=time.time())
    media['generation']=generation
    recipe={'version':1,'kind':'image','model':{'id':model['id'],'name':model['name']},
            'prompt':prompt,'parameters':clean(generation),'references':[asset(r) for r in references],
            'loras':public(loras),'created_at':generation['completed_at']}
    try:
        path=safe_join(app.data,media['path'])
        if path.is_file():
            generation['metadata_embedded']=embed_png(path,recipe)
            sidecar=path.with_name(path.name+'.h3.json');part=sidecar.with_name(sidecar.name+'.tmp')
            try:part.write_text(json.dumps(recipe,ensure_ascii=False,indent=2),encoding='utf-8');part.replace(sidecar)
            finally:part.unlink(missing_ok=True)
    except (OSError,ValueError):
        generation['metadata_embedded']=False
        generation['metadata_note']='Ricetta conservata nella chat; impossibile salvarla nel file immagine.'
    return media


def get(app,ident):
    media=app.validate_media([{'id':ident}],canvas=True)[0]
    kind='image' if media['mime'].startswith('image/') else 'video' if media['mime'].startswith('video/') else ''
    if not kind:raise ValueError('Scegli un’immagine o un video.')
    path=safe_join(app.data,media['path'])
    if not path.is_file():raise ValueError('File non più disponibile.')
    row=app.store.one('''SELECT m.meta,m.media,j.payload,m.created FROM messages m
        LEFT JOIN jobs j ON j.message_id=m.id WHERE m.role='assistant' AND (
        EXISTS (SELECT 1 FROM json_each(m.media) a WHERE json_extract(a.value,'$.path')=?) OR
        EXISTS (SELECT 1 FROM json_each(json_extract(m.meta,'$.artifact.media')) a WHERE json_extract(a.value,'$.path')=?))
        ORDER BY m.created DESC,m.seq DESC LIMIT 1''',(media['path'],media['path']))
    meta=json.loads(row['meta'] or '{}') if row else {};payload=json.loads(row['payload'] or '{}') if row else {}
    # Prefer this exact member of a batch, never the last seed of its model.
    candidates=(json.loads(row['media']) if row else [])+meta.get('artifact',{}).get('media',[])
    chosen=next((m for m in candidates if m.get('path')==media['path']),media)
    generation=dict(chosen.get('generation') or {})
    saved=None
    if kind=='image':
        try:saved=png_recipe(path)
        except (OSError,ValueError,UnicodeError):pass
    if saved and saved.get('version')==1 and saved.get('kind')=='image':
        recipe=clean(saved);source='png'
    else:
        parameters=(meta.get('image_parameters') if kind=='image' else meta.get('video_parameters')) or {}
        parameters=dict(parameters)|generation
        # Native video files have per-job plans even if the chat record is old.
        if kind=='video' and not parameters:
            for name in ('video-plan.json','scenes.json'):
                file=path.parent/name
                try:
                    if file.stat().st_size<=32*1024**2:parameters=json.loads(file.read_text()).get('parameters',{})
                    if parameters:break
                except (OSError,ValueError):pass
        refs=generation.get('reference_assets')
        if refs is None:
            refs=meta.get('references',[]) if kind=='image' and not meta.get('image_batch') else payload.get('media',[])
            if meta.get('image_batch'):
                images=[r for r in refs if r.get('mime','').startswith('image/')]
                refs=[images[i-1] for i in generation.get('references',[]) if type(i) is int and 1<=i<=len(images)]
        model_id=generation.get('image_model_id') if kind=='image' else parameters.get('model_id')
        model_id=model_id or meta.get('image_model_id') or payload.get('settings',{}).get('_image_model')
        recipe={'version':1,'kind':kind,'model':{'id':model_id or '','name':generation.get('model') or parameters.get('model_name') or meta.get('model','')},
                'prompt':generation.get('prompt') or meta.get('image_prompt') or payload.get('prompt',''),
                'parameters':clean(parameters),'references':[asset(r) for r in refs if isinstance(r,dict)],
                'loras':clean(generation.get('loras',meta.get('loras',[]))),'created_at':row['created'] if row else None}
        source='history' if row else 'file'
    if not isinstance(recipe.get('model'),dict) or not isinstance(recipe.get('parameters'),dict) or not isinstance(recipe.get('references'),list) or not isinstance(recipe.get('loras'),list):
        raise ValueError('Dati di creazione non validi.')
    if any(not isinstance(recipe['model'].get(k,''),str) for k in ('id','name')):raise ValueError('Dati di creazione non validi.')
    if len(recipe['references'])>64 or len(recipe['loras'])>8 or any(not isinstance(r,dict) for r in recipe['references']):raise ValueError('Dati di creazione non validi.')
    recipe['asset']=asset(media);recipe['source']=source;warnings=[]
    if source=='png':recipe['parameters']['metadata_embedded']=True
    model=app.catalog.get(recipe.get('model',{}).get('id'))
    if not model and recipe.get('model',{}).get('name'):
        matches=[m for m in app.catalog.values() if m['name']==recipe['model']['name']]
        if len(matches)==1:model=matches[0];recipe['model']['id']=model['id']
    available=[]
    for ref in recipe.get('references',[]):
        try:
            value=app.validate_media([{'id':ref.get('id')}],canvas=True)[0]
            if not safe_join(app.data,value['path']).is_file():raise ValueError()
            available.append(asset(value))
        except (ValueError,OSError,PermissionError):warnings.append('Riferimento non disponibile: '+str(ref.get('name','immagine')))
    recipe['references']=available
    if kind=='video' and not recipe.get('parameters'):warnings.append('Dati di creazione non registrati per questo filmato.')
    if kind=='image':
        if not model:warnings.append('Modello originale non disponibile.')
        else:
            try:app.engine.require_model(model['id'],'edit' if available else 'create')
            except ValueError:warnings.append('Pesi del modello originale non disponibili.')
        p=recipe.get('parameters',{})
        if any(k not in p for k in ('width','height','steps','cfg','sampler','scheduler','seed')) or type(p.get('seed')) is not int or p.get('seed',-1)<0:warnings.append('Parametri originali incompleti o seed effettivo non registrato.')
        if not isinstance(recipe.get('prompt'),str) or not recipe['prompt'].strip():warnings.append('Prompt originale non registrato.')
        try:
            validate_overrides({'recipe':{k:v for k,v in p.items() if k in OVERRIDE_KEYS}}, {'recipe':model} if model else None)
        except (ValueError,KeyError,TypeError) as error:warnings.append('Parametri originali non riutilizzabili: '+str(error))
        try:
            selections=[{k:l[k] for k in ('id','weight','model_id')} for l in recipe.get('loras',[])]
            app.loras.capture(selections,app.store.settings()['lora_dirs'],app.catalog)
        except (ValueError,KeyError,TypeError):warnings.append('LoRA originali non più disponibili.')
    recipe['warnings']=warnings;recipe['reusable']=kind=='image' and not warnings
    return recipe

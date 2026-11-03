"""Named request recipes, workspace scoped. No keys, source content or host grants."""
import json
import threading
import time
from copy import deepcopy
from uuid import uuid4
from .presentation_preferences import title

LOCK=threading.RLock()
KINDS={'slides':'Slide','infographic':'Infografica','poster':'Locandine','study':'Studio','manim':'Manim',
       'calculate':'Calcolo','image':'Immagini','video':'Video','music':'Musica','voice':'Voice',
       'transcribe':'Trascrivi','backgrounds':'Sfondi','image_lot':'Lotti immagini','chat':'Chat','agent':'Agente'}


def recipe(draft,meta=None):
    """Input is the server's credential-free draft, never a client-supplied snapshot."""
    allowed=('parameters','controls','lab','think_level','slides','infographic','poster','study','manim_presentation','background_batch','image_lot','loras')
    value={k:deepcopy(draft[k]) for k in allowed if draft.get(k) is not None}
    if value.get('slides'):value['slides'].pop('reuse_images_from',None)
    if value.get('study'):value['study']['source_text']=''
    if value.get('poster'):
        for k in ('reference_asset_id','hero_asset_id'):value['poster'].pop(k,None)
    if value.get('infographic'):value['infographic']['video_id']=''
    # Lyrics and notation are request content, rather than tuning.
    fields=value.get('controls',{}).get('music_fields',{})
    for k in ('lyrics','abc','title'):fields.pop(k,None)
    if draft.get('rag'):value['rag']={k:draft['rag'][k] for k in ('rag','rag_top_k') if k in draft['rag']}
    lab=value.get('lab','auto');controls=value.setdefault('controls',{});meta=meta or {}
    if meta.get('image_parameters') and meta.get('image_model_id'):
        from .image_options import OVERRIDE_KEYS
        model=meta['image_model_id'];controls['image_model']=model
        controls['image_presets']={model:{k:v for k,v in meta['image_parameters'].items() if k in OVERRIDE_KEYS}}
    elif meta.get('intent') in ('voice','music','video','transcribe'):controls[meta['intent']]=True
    if draft.get('video_edit') or draft.get('operation'):controls.update(video=True,video_editing='continuous')
    kind=lab if lab in KINDS else next((k for k in ('video','music','voice','transcribe') if controls.get(k)),'image' if controls.get('image_model') else 'chat')
    if draft.get('background_batch'):kind='backgrounds'
    elif draft.get('image_lot'):kind='image_lot'
    # Auto-routed requests still carry their resolved tool options.
    elif kind=='chat':kind=next((k for k in ('slides','infographic','poster','study') if value.get(k)),kind)
    value['lab']=lab if lab!='auto' or kind not in ('slides','infographic','poster','study') else kind
    return kind,value


def load(app):
    path=app.data/'generation-presets.json'
    if not path.exists():return {'version':1,'items':[]}
    if path.stat().st_size>4*1024*1024:raise ValueError('Raccolta preset troppo grande.')
    data=json.loads(path.read_text(encoding='utf8'))
    if not isinstance(data,dict) or data.get('version')!=1 or not isinstance(data.get('items'),list):raise ValueError('Raccolta preset non valida.')
    return data


def update(app,body):
    if not isinstance(body,dict) or set(body)-{'action','name','chat_id','message_id','id'} or body.get('action') not in ('save','delete'):raise ValueError('Operazione preset non valida.')
    with LOCK:
        data=load(app)
        if body['action']=='save':
            name=title(body.get('name'))
            from .request_draft import load as request_draft
            draft=request_draft(app,body.get('chat_id'),body.get('message_id'))
            row=app.store.one("SELECT meta FROM messages WHERE id=? AND chat_id=? AND role='assistant'",(body.get('message_id'),body.get('chat_id')))
            kind,value=recipe(draft,json.loads(row['meta']) if row else {})
            previous=next((p for p in data['items'] if p['kind']==kind and p['name'].casefold()==name.casefold()),None)
            if previous:data['items'].remove(previous)
            elif sum(p['kind']==kind for p in data['items'])>=50:raise ValueError('Massimo 50 preset per modalità.')
            data['items'].append({'id':previous['id'] if previous else uuid4().hex,'name':name,'kind':kind,'label':KINDS[kind],'recipe':value,'updated':time.time()})
        else:
            if not any(p['id']==body.get('id') for p in data['items']):raise ValueError('Preset non trovato.')
            data['items']=[p for p in data['items'] if p['id']!=body['id']]
        path=app.data/'generation-presets.json';temp=path.with_name(path.name+'.'+uuid4().hex+'.tmp')
        raw=json.dumps(data,ensure_ascii=False,indent=2)+'\n'
        if len(raw.encode('utf8'))>4*1024*1024:raise ValueError('Raccolta preset troppo grande.')
        try:temp.write_text(raw,encoding='utf8');temp.replace(path)
        finally:temp.unlink(missing_ok=True)
        return data

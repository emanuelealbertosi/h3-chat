"""Workspace-scoped presentation controls. Saving never enqueues generation."""
import json
import threading
import time
from uuid import uuid4
from .slide_backgrounds import options as background_options
from .slide_background_style import options as style_options

LOCK=threading.RLock()
KINDS=('slides','backgrounds')
SLIDE_DEFAULTS=dict(count_mode='fixed',count=8,format='16:9',duration_minutes=0,llm_timeout=0,
    engine='llm',design='professional',detail='concise',composition='standard',motion='auto',vision_scope='relevant',
    generate_images=False,image_model='',image_source='auto',image_lots=[],background='auto',background_color='#f7f3e8',text_tone='auto',palette='auto',background_style=None)

def config(kind,value):
    if kind=='backgrounds':return background_options(value)
    if kind!='slides' or not isinstance(value,dict) or set(value)-set(SLIDE_DEFAULTS):raise ValueError('Impostazioni slide non valide.')
    result=SLIDE_DEFAULTS|value
    for key,allowed in dict(count_mode=('fixed','auto'),format=('16:9','9:16','4:3','16:10','1:1'),engine=('llm','deterministic'),design=('professional','playful','comic'),detail=('concise','full'),composition=('standard','rich'),vision_scope=('relevant','all')).items():
        if result[key] not in allowed:raise ValueError('Impostazione slide non valida: '+key)
    from .slide_motion import options as motion_options
    result['motion']=motion_options('',result)
    if result['motion']=='animated':result['engine']='llm'
    if type(result['count']) is not int or not 1<=result['count']<=100:raise ValueError('Scegli da 1 a 100 slide.')
    if type(result['duration_minutes']) not in (int,float) or not 0<=result['duration_minutes']<=20:raise ValueError('Durata slide non valida.')
    if type(result['llm_timeout']) is not int or result['llm_timeout']!=0 and not 60<=result['llm_timeout']<=14400:raise ValueError('Tempo per fase: 0 oppure da 60 a 14.400 secondi.')
    if type(result['generate_images']) is not bool or not isinstance(result['image_model'],str) or len(result['image_model'])>150 or any(ord(c)<32 for c in result['image_model']):raise ValueError('Modello immagini slide non valido.')
    from .slide_image_lots import ids
    result['image_lots']=ids(result['image_lots'])
    if result['image_source'] not in ('auto','generate','lots'):raise ValueError('Origine illustrazioni non valida.')
    if result['image_source']=='lots':result['generate_images']=False
    if result['engine']=='deterministic' and result['composition']=='rich':raise ValueError('La composizione ricca richiede il motore LLM.')
    from .slide_colors import options as colors
    colors(result)
    result['background_style']=style_options(result['background_style'])
    return result

def empty():return {'version':1,**{k:{'last':None,'presets':[]} for k in KINDS}}

def previous_requests(app):
    data=empty()
    if not hasattr(app,'store'):return data
    for kind,path in (('slides','$.settings._slides'),('backgrounds','$.settings._slide_backgrounds.options')):
        row=app.store.one("SELECT json_extract(payload,?) AS config FROM jobs WHERE json_type(payload,?)='object' AND json_type(payload,'$.settings._slide_revision') IS NULL ORDER BY created DESC LIMIT 1",(path,path))
        if not row:continue
        try:
            value=json.loads(row['config'])
            if kind=='slides':
                value={k:v for k,v in value.items() if k in SLIDE_DEFAULTS}
                if value.get('count')=='auto':value.update(count_mode='auto',count=8)
            data[kind]['last']=config(kind,value)
        except (ValueError,TypeError,KeyError):continue
    return data

def load(app):
    path=app.data/'presentation-preferences.json'
    if not path.exists():return previous_requests(app)
    if path.stat().st_size>512*1024:raise ValueError('Raccolta preset troppo grande.')
    try:data=json.loads(path.read_text(encoding='utf8'))
    except (ValueError,OSError):raise ValueError('Impossibile leggere le impostazioni delle presentazioni.') from None
    if not isinstance(data,dict) or data.get('version')!=1:raise ValueError('Formato preset non supportato.')
    for kind in KINDS:
        group=data.get(kind)
        if not isinstance(group,dict) or not isinstance(group.get('presets'),list) or len(group['presets'])>50:raise ValueError('Raccolta preset non valida.')
        if group.get('last') is not None:config(kind,group['last'])
        for item in group['presets']:
            if not isinstance(item,dict) or not isinstance(item.get('id'),str) or len(item['id'])!=32 or any(c not in '0123456789abcdef' for c in item['id']):raise ValueError('Identificatore preset non valido.')
            title(item.get('name'));config(kind,item.get('config'))
    return data

def title(value):
    if not isinstance(value,str) or not value.strip() or len(value.strip())>80 or any(ord(c)<32 for c in value):raise ValueError('Dai al preset un nome da 1 a 80 caratteri.')
    return value.strip()

def update(app,body):
    if not isinstance(body,dict) or set(body)-{'kind','action','config','name','id'} or body.get('kind') not in KINDS or body.get('action') not in ('last','save','delete'):raise ValueError('Operazione preset non valida.')
    kind=body['kind'];action=body['action']
    value=config(kind,body.get('config')) if action!='delete' else None
    name=title(body.get('name')) if action=='save' else None
    with LOCK:
        data=load(app);group=data[kind]
        if action=='delete':
            ident=body.get('id')
            if not any(p['id']==ident for p in group['presets']):raise ValueError('Preset non trovato.')
            group['presets']=[p for p in group['presets'] if p['id']!=ident]
        else:
            group['last']=value
            if action=='save':
                previous=next((p for p in group['presets'] if p['name'].casefold()==name.casefold()),None)
                if not previous and len(group['presets'])>=50:raise ValueError('Massimo 50 preset per pannello. Elimina un preset prima di aggiungerne altri.')
                item=dict(id=previous['id'] if previous else uuid4().hex,name=name,config=value,updated=time.time())
                if previous:group['presets'][group['presets'].index(previous)]=item
                else:group['presets'].append(item)
        path=app.data/'presentation-preferences.json';temp=path.with_name(path.name+'.'+uuid4().hex+'.tmp')
        try:
            temp.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf8');temp.replace(path)
        finally:temp.unlink(missing_ok=True)
        return data

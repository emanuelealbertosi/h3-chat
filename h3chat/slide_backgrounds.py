"""Standalone background batches. No slide planning, RAG or LLM execution."""
import json
import math
import re
import time
from uuid import uuid4
from .downloads import Cancelled, safe_join
from .image_options import options as image_options, capture_request
from .execution_mode import guard_intent
from .lab_image_model import select
from .visual_routing import assistant_format
from .slide_style import IMAGE_CUES

PALETTES = {
    'pastel': ('Pastello', 'soft coordinated pastel colors'),
    'natural': ('Naturale', 'muted sage green, warm ivory and earthy colors'),
    'blue': ('Blu e ghiaccio', 'muted blue, pale ice blue and cool neutral colors'),
    'warm': ('Sabbia e terracotta', 'warm sand, cream and muted terracotta colors'),
    'mono': ('Monocromatica', 'restrained monochromatic neutral colors'),
    'custom': ('Personalizzata', ''),
}
FORMATS = ('16:9', '9:16', '4:3', '1:1')
MAX_IMAGES = 24


def options(body):
    if not isinstance(body, dict):raise ValueError('Opzioni sfondi non valide.')
    allowed = {'name','kind','format','themes','palettes','custom_palette','variants','margin','opacity','tone','design','model','megapixels','seed_mode','seed'}
    if set(body)-allowed:raise ValueError('Opzione sfondi sconosciuta.')
    result = dict(name='Set di sfondi',kind='frame',format='16:9',themes=[],palettes=['pastel'],custom_palette='',variants=2,
                  margin=12,opacity=20,tone='light',design='professional',model='',megapixels=None,seed_mode='saved',seed=0)
    result.update(body)
    for key, limit in (('name',100),('custom_palette',250),('model',150)):
        value=result[key]
        if not isinstance(value,str) or len(value)>limit or any(ord(c)<32 for c in value):raise ValueError('Nome, palette o modello sfondi non valido.')
        result[key]=value.strip()
    if not result['name']:raise ValueError('Dai un nome al set di sfondi.')
    for key, values in (('kind',('frame','soft')),('format',FORMATS),('tone',('light','dark')),
                        ('design',tuple(IMAGE_CUES)),('seed_mode',('saved','random','fixed'))):
        if result[key] not in values:raise ValueError('Scelta sfondi non valida: '+key)
    for key, lo, hi in (('variants',1,MAX_IMAGES),('margin',5,25),('opacity',5,45),('seed',0,2147483647)):
        if type(result[key]) is not int or not lo<=result[key]<=hi:raise ValueError('Valore sfondi non valido: '+key)
    themes=result['themes'];palettes=result['palettes']
    if not isinstance(themes,list) or len(themes)>8 or any(not isinstance(t,str) or not t.strip() or len(t)>300 for t in themes):
        raise ValueError('Inserisci al massimo 8 temi, uno per riga (massimo 300 caratteri ciascuno).')
    result['themes']=list(dict.fromkeys(t.strip() for t in themes))
    if not isinstance(palettes,list) or not 1<=len(palettes)<=6 or any(not isinstance(p,str) or p not in PALETTES for p in palettes) or len(set(palettes))!=len(palettes):
        raise ValueError('Scegli da una a sei palette diverse.')
    if 'custom' in palettes and not result['custom_palette']:raise ValueError('Descrivi la palette personalizzata.')
    mp=result['megapixels']
    if mp is not None and (type(mp) not in (int,float) or not math.isfinite(mp) or not .25<=mp<=4):raise ValueError('Scegli da 0,25 a 4 megapixel oppure lascia vuoto per usare il modello.')
    if max(1,len(result['themes']))*len(palettes)*result['variants']>MAX_IMAGES:
        raise ValueError('Il batch supera 24 sfondi: riduci temi, palette o varianti.')
    return result


def plan(config, prompt, model, settings):
    tasks=[];form=assistant_format(model)
    base={'aspect':config['format']}
    if config['megapixels'] is not None:base['megapixels']=config['megapixels']
    if config['seed_mode']!='saved':base['seed']=-1 if config['seed_mode']=='random' else config['seed']
    local=capture_request(model,settings,base)
    for theme in config['themes'] or ['']:
        for palette in config['palettes']:
            label,colors=PALETTES[palette];colors=colors or config['custom_palette']
            for variant in range(config['variants']):
                index=len(tasks)+1
                placement=(f'Decorative frame confined to the outer {config["margin"]}% on each edge. '
                           'Keep the entire central rectangle completely empty, flat and uniform; no ornament may cross into it. '
                           'Use fine corner ornaments and thin borders, not thick bars.') if config['kind']=='frame' else (
                           'Very subtle low-contrast background wash, sparse soft shapes near the edges, quiet and uniform center. '
                           'No focal subject, no busy texture, no sharp high-contrast details behind future text.')
                topic=theme or prompt.strip()
                text=(f'THEME: {topic}. '+(f'Additional user direction: {prompt.strip()}. ' if theme else '')+
                      'Make the actual decorative motifs recognizable objects and symbols from THIS THEME, '
                      'not a generic ornamental frame. Do not substitute unrelated stars, flowers or swirls unless the theme asks for them. '
                      f'{placement} Style: '+{'professional':'refined editorial illustration','playful':'friendly playful illustration','comic':'ink-outlined comic illustration'}[config['design']]+'. '
                      f'Palette: {colors}. Base: {"pale light" if config["tone"]=="light" else "deep dark"} neutral. '
                      f'Variation {variant+1}: change the arrangement of the thematic motifs while keeping the same visual family. '
                      'Background artwork only. No written text, logos or watermarks. Leave the center empty for later slide content.')
                if form=='tags':text=text.replace('. ', ', ')
                tasks.append(dict(index=index,theme=theme or prompt[:150],palette=palette,palette_label=label,variant=variant+1,
                                  prompt=text,parameters=image_options(model,local,prompt)))
    return tasks


def enqueue(app,chat_id,body):
    app.store.chat(chat_id)
    prompt=body.get('prompt','')
    if not isinstance(prompt,str) or not 1<=len(prompt.strip())<=4000:raise ValueError('Descrivi nel prompt il tema degli sfondi (massimo 4.000 caratteri).')
    config=options(body.get('options',{}))
    settings=app.effective_settings(app.store.settings())
    guard_intent(settings,'create')
    ident=select(app.engine,settings,config['model'])
    model=app.engine.require_model(ident,'create');config['model']=ident
    tasks=plan(config,prompt,model,settings)  # Validate dimensions/sampling before queueing anything.
    settings=settings|{'_slide_backgrounds':dict(options=config,tasks=tasks,prompt=prompt.strip()), '_image_model':ident,
                       '_assistant':False,'_rag':False,'_web':False,'_lab':'auto'}
    job=app.store.enqueue(chat_id,'Crea sfondi · '+config['name']+'\n'+prompt.strip(),[],settings,True)
    app.wake.set()
    return dict(job_id=job,canvas=True,intent='image_batch',count=len(tasks))


def save(app,collection):
    folder=app.data/'slide-backgrounds';folder.mkdir(exist_ok=True)
    target=folder/(collection['id']+'.json');part=target.with_name(target.name+'.'+uuid4().hex+'.tmp')
    try:
        part.write_text(json.dumps(collection,ensure_ascii=False,indent=2),encoding='utf8');part.replace(target)
    finally:part.unlink(missing_ok=True)


def listing(app):
    folder=app.data/'slide-backgrounds';items=[]
    if not folder.is_dir():return {'items':[]}
    for file in folder.glob('*.json'):
        if not re.fullmatch('[a-f0-9]{32}',file.stem):continue
        try:
            value=json.loads(file.read_text(encoding='utf8'))
            if value.get('id')!=file.stem:continue
            assets=[]
            for item in value.get('images',[]):
                media=item['media'];path=safe_join(app.data,media['path'])
                if not media.get('mime','').startswith('image/') or not path.is_file():continue
                assets.append(item)
            job=app.store.one('SELECT status FROM jobs WHERE id=?',(file.stem,))
            status=job['status'] if job and job['status'] in ('done','failed','cancelled','interrupted') else value.get('status','interrupted')
            items.append(value|{'images':assets,'available':len(assets),'status':status})
        except (OSError,ValueError,KeyError,TypeError):continue
    return {'items':sorted(items,key=lambda x:x.get('created',0),reverse=True)[:100]}


def render(app,job,payload,settings,cancel,stage,meta):
    request=settings['_slide_backgrounds'];config=options(request['options']);tasks=request['tasks']
    model=app.engine.require_model(config['model'],'create')
    meta.update(intent='image_batch',image_batch=True,canvas=True,model=model['name'],batch_total=len(tasks),
                background_set_id=job['id'],background_options=config,settings=settings)
    collection=dict(id=job['id'],name=config['name'],created=time.time(),chat_id=job['chat_id'],status='running',prompt=request['prompt'],
                    options=config,total=len(tasks),images=[])
    def publish(status='running'):
        media=[item['media'] for item in collection['images']]
        title=f"Sfondi · {config['name']} · {len(media)}/{len(tasks)}"
        meta.update(artifact=dict(title=title,content='',media=media),batch_completed=len(media))
        collection['status']=status;save(app,collection)
        app.save_artifact(job['chat_id'],title,'',media)
        app.store.update_answer(job,f'Sfondi salvati: {len(media)}/{len(tasks)}. Nessuna slide creata.',status,media,meta)
    if cancel.is_set():raise Cancelled()
    publish()
    try:
        if not model.get('remote_media'):
            stage('Sfondi · rilascio motori locali prima del batch');app.engine.stop()
        for task in tasks:
            if cancel.is_set():raise Cancelled()
            label=f'Sfondi · {task["index"]}/{len(tasks)} · {model["name"]}'
            stage(label);meta['batch_active_index']=task['index']
            local=settings|{'memory_policy':'on_demand','ram_cache_gb':0,'_loras':[], '_image_options':task['parameters']}
            image=app.engine.generate(model,local,task['prompt'],[],uuid4().hex,cancel,lambda value:stage(label+' · '+value))
            image.update(name=f"{config['name']} · {task['palette_label']} · {task['index']}",
                         batch_id=job['id'],batch_index=task['index'],batch_total=len(tasks),
                         slide_background={k:config[k] for k in ('kind','margin','opacity','tone','format')})
            effective=task['parameters']|image.get('generation',{})
            if effective.get('width') and effective.get('height'):
                image['slide_background']['format']=str(effective['width'])+':'+str(effective['height'])
            effective['slide_background']=image['slide_background']
            from .media_generation import record_image
            record_image(app,image,model,effective,task['prompt'],[],[])
            collection['images'].append({k:task[k] for k in ('index','theme','palette','palette_label','variant')}|{'media':image})
            publish()
        meta.pop('batch_active_index',None);publish('done');stage('Set di sfondi pronto')
    except Exception as exc:
        collection['status']='cancelled' if isinstance(exc,Cancelled) or cancel.is_set() else 'failed'
        save(app,collection);raise
    finally:
        if not model.get('remote_media'):app.engine.stop()

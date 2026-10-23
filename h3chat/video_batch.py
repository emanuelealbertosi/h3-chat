"""Sequential alternatives from one plan, with durable per-clip journals.

The selected first take drives the preview. Clip mode shares that selected
context; film mode restores the corresponding take's own previous footage.
Never run the planner, silently restart completed takes or mix native memories.
"""
import copy
import hashlib
import json
import re
import secrets
import time
from pathlib import Path
from .downloads import Cancelled,safe_join
from .video_resume import save

MAX_VARIANTS=8

def validate_count(value):
    if type(value) is not int or not 1<=value<=MAX_VARIANTS:raise ValueError('Varianti video: scegli un numero intero da 1 a 8.')
    return value

def prompt_options(prompt):
    from .video_timing import _mask
    from .video_clip_budget import NUMBER,number
    text=_mask(prompt)
    text=re.sub(rf'\b(?:non|not|no|anziché|instead of)\s+({NUMBER})\s+(?:varianti|versioni|variants|versions)\b','',text,flags=re.I)
    matches=list(re.finditer(rf'(?<![\w:.,])({NUMBER})\s+(?:varianti|versioni|variants|versions)\b',text,re.I))
    counts={number(m[1]) for m in matches}
    if len(counts)>1:raise ValueError('Indica un solo numero di varianti video per questo lancio.')
    if not counts:return {}
    result={'variants':validate_count(counts.pop())}
    scope=' '.join(text[m.start():m.end()+75] for m in matches)
    if re.search(r'\b(?:inter[oa]|complet[oa]|whole|entire|full)\s+(?:video|film|filmato)|\b(?:video|filmato|film)\s+(?:inter[oa]|complet[oa])',scope,re.I):result['variants_mode']='video'
    elif re.search(r'\b(?:per|ogni|each|per each|for each)\s+(?:singol[oa]\s+)?(?:clip|scena|scene)\b',scope,re.I):result['variants_mode']='clip'
    return result

def write(path,value):
    # Reuse the bounded atomic publisher, under a separate journal directory.
    path.parent.mkdir(parents=True,exist_ok=True)
    save(path.parent,value)

def journal(data,job_id):return safe_join(data,'outputs/'+job_id+'/batch/scenes.json')

def memory_for(record,index,variant=1,mode='clip',data=None):
    if not index:return None
    from .video_edit_memory import source_indices
    anchor,recent=source_indices(record,index)
    def selected(i):
        if mode=='video':
            alternatives=record.get('clip_versions',[])
            if i<len(alternatives):
                take=next((v for v in reversed(alternatives[i]) if v['parameters'].get('variant_index')==variant),None)
                if take:return str(safe_join(data,take['output']))
        return str(safe_join(data,record['outputs'][i]))
    return {'opening':selected(anchor),'recent':[selected(i) for i in recent]}

def generate(engine,model,settings,plan,refs,job_id,cancel,stage,*,prompt=None,scene=None):
    from .video_options import options
    opts=options(model,settings,False);count=validate_count(opts['variants']);mode=opts['variants_mode']
    folder=safe_join(engine.data,'outputs/'+job_id);folder.mkdir(parents=True,exist_ok=True)
    identity={'model':model['id'],'options':opts,'plan':plan,'refs':[{k:r[k] for k in ('id','mime','path')} for r in refs],
        'tuning':{k:settings[k] for k in ('_video_loras','_video_aspect') if k in settings},
        'scene':{k:v for k,v in (scene or {}).items() if k not in ('sequence','resume_memory','batch_memories')},
        'memories':{str(n):(scene.get('batch_memories',{}).get(str(n)) or scene.get('resume_memory')) for n in range(1,count+1)} if scene else {}}
    signature=hashlib.sha256(json.dumps(identity,sort_keys=True).encode()).hexdigest()
    target=journal(engine.data,job_id);cached=None
    candidates=[target]
    if settings.get('_video_resume'):
        root,sep,suffix=job_id.partition('/')
        candidates.append(journal(engine.data,settings['_video_resume']+(sep+suffix if sep else '')))
    for path in candidates:
        if path.is_file():
            value=json.loads(path.read_text(encoding='utf-8'))
            if value.get('signature')!=signature:raise ValueError('Le varianti salvate non coincidono con questa ricetta. Nessuna variante è stata rilanciata.')
            cached=value;break
    base=opts['seed'] if opts['seed']>=0 else secrets.randbelow(2**31)
    state=cached or {'signature':signature,'count':count,'mode':mode,'batch_id':settings.get('_video_batch_id') or job_id.split('/')[0],'seeds':[(base+i)%(2**31) for i in range(count)],'items':[],'started':time.time()}
    settings=settings|{'_video_batch_id':state['batch_id']}
    if len(state['items'])>count:raise ValueError('Elenco varianti salvato non valido.')
    for item in state['items']:
        with safe_join(engine.data,item['path']).open('rb') as f:
            if f.read(12)[4:8]!=b'ftyp':raise ValueError('Una variante video già salvata non è disponibile.')
    write(target,state)
    standalone=scene is None
    standalone_record=None
    if standalone:
        duration=round(opts['duration']*24)/24
        standalone_record={'batch_standalone':True,'batch_source_plan':copy.deepcopy(plan),'timeline':[{'index':0,'start':0,'duration':duration,'frames':round(duration*24),'continuity':'cut','images':copy.deepcopy(plan['images'])}],
            'prompts':[plan['prompt']],'plan':copy.deepcopy(plan),'model':model['id'],'completed':0,'parameters':[],'outputs':[],
            'request_context':{'references':refs,'settings':{}},'batch_requested':count}
        from .video_job_resume_render import CONTEXT_KEYS
        standalone_record['request_context']['settings']={k:copy.deepcopy(settings[k]) for k in CONTEXT_KEYS if k in settings}
        save(folder,standalone_record)
    for i in range(len(state['items']),count):
        if cancel.is_set():raise Cancelled()
        tuning=copy.deepcopy(settings);tuning['video_overrides']=copy.deepcopy(settings.get('video_overrides',{}))
        tuning['video_overrides'][model['id']]=dict(tuning['video_overrides'].get(model['id'],{}),seed=state['seeds'][i],variants=1)
        scoped=copy.deepcopy(scene)
        if scoped is not None:
            memories=scoped.pop('batch_memories',{})
            memory=memories.get(str(i+1)) or scoped.get('resume_memory')
            # Different native sequences clear the previous take's in-memory
            # anchor. A continuation restores only its explicit saved context.
            scoped['sequence']=job_id+f'/take-{i+1}'
            scoped['continuity']='continue' if memory else 'cut'
            if memory:scoped['resume_memory']=memory
        def report(label):stage(f'Variante {i+1}/{count} · '+label)
        item=engine._generate_video_once(model,tuning,plan,refs,job_id+(f'/variant-{i+1:03d}' if i else ''),cancel,report,prompt=prompt,scene=scoped)
        item['generation'].update(variant_index=i+1,variants=count,variants_mode=mode,variant_batch_id=state['batch_id'],variant_seed_base=state['seeds'][0],variant_seed_policy='consecutive',variant_created=time.time())
        state['items'].append(item);write(target,state)
        if standalone_record:
            standalone_record['batch_ready']=copy.deepcopy(state['items']);save(folder,standalone_record)
    selected=copy.deepcopy(state['items'][0]);selected['batch_variants']=copy.deepcopy(state['items'])
    if standalone_record:selected['batch_standalone_record']=standalone_record
    return selected

def register(record,index,item,refs):
    items=item.get('batch_variants',[])
    if not items:return
    from .video_versions import snapshot
    history=record.setdefault('clip_versions',[[] for _ in record['timeline']])[index]
    original=copy.deepcopy({k:record[k][index] for k in ('outputs','parameters')})
    first=None
    for take in items:
        record['outputs'][index]=take['path'];record['parameters'][index]=copy.deepcopy(take['generation'])
        variant=snapshot({'record':record,'images':[r for r in refs if r['mime'].startswith('image/')]},index)
        variant.update(created=take['generation'].get('variant_created',time.time()),created_source='generated')
        if first is None:first=variant['id']
        if not any(v['id']==variant['id'] for v in history):history.append(variant)
    record['outputs'][index]=original['outputs'];record['parameters'][index]=original['parameters']
    record.setdefault('selected_versions',{})[str(index+1)]=first
    record['batch_requested']=len(items);record['batch_mode']=items[0]['generation']['variants_mode']
    record['batch_id']=items[0]['generation'].get('variant_batch_id')

def finish_standalone(app,item,plan,refs,job,cancel,stage,log):
    record=item.pop('batch_standalone_record',None)
    if record is None:return plan,refs
    items=item['batch_variants'];audio_refs=[]
    from .store import uid
    for take in items:
        if cancel.is_set():raise Cancelled()
        path=safe_join(app.data,take['path']);audio=safe_join(app.data,'outputs/'+job['id']+f'/batch-audio/take-{take["generation"]["variant_index"]:03d}.wav');audio.parent.mkdir(parents=True,exist_ok=True)
        app.engine.tool_call('video-batch-audio-worker.py',{'source':str(path),'output':str(audio),'duration':record['timeline'][0]['duration']},cancel,stage,log,timeout=300)
        audio_refs.append({'id':uid(),'name':f"Audio variante {take['generation']['variant_index']}.wav",'mime':'audio/wav','path':audio.relative_to(app.data).as_posix()})
    app.store.gallery.register(audio_refs,internal=True)
    record.update(completed=1,outputs=[item['path']],parameters=[item['generation']],batch_generated_audio=True)
    # Keep original references for exact recreation; one additional master track
    # supplies editing/assembly. Alternative masters live in owned snapshots.
    global_refs=refs+[audio_refs[0]];global_plan=copy.deepcopy(plan)
    for a in global_plan['audios']:a['role']='reference'
    global_plan['audios'].append({'index':sum(r['mime'].startswith('audio/') for r in refs)+1,'role':'reuse','start':0})
    record['plan']=global_plan
    record['recreate_recipes']=[{'plan':copy.deepcopy(plan),'refs':copy.deepcopy(refs)}]
    register(record,0,item,global_refs)
    for variant in record['clip_versions'][0]:variant['audio']=copy.deepcopy(audio_refs[variant['parameters']['variant_index']-1])
    if record.get('batch_mode')=='video':
        record['batch_movies']=[{'variant_index':t['generation']['variant_index'],'path':t['path']} for t in items]
        item['generation']['batch_movies']=copy.deepcopy(record['batch_movies'])
    save(safe_join(app.data,'outputs/'+job['id']),record)
    item.pop('batch_variants',None)
    return global_plan,global_refs

def compose_branches(engine,record,folder,audio,cancel,stage,log,start,duration):
    if record.get('batch_mode')!='video':return
    from .soundtrack import compose
    record['batch_movies']=[{'variant_index':1,'path':(folder/'video.mp4').relative_to(engine.data).as_posix()}]
    for n in range(2,record.get('batch_requested',1)+1):
        if cancel.is_set():raise Cancelled()
        paths=[]
        for i,path in enumerate(record['outputs']):
            history=record.get('clip_versions',[])
            alternative=next((v for v in history[i] if v['parameters'].get('variant_index')==n),None) if i<len(history) else None
            paths.append(safe_join(engine.data,alternative['output'] if alternative else path))
        target=folder/f'version-{n:03d}.mp4'
        stage(f'Montaggio · versione completa {n}/{record["batch_requested"]}')
        compose(engine,paths,safe_join(engine.data,audio['path']),target,cancel,stage,log,audio_start=start,audio_duration=duration)
        record['batch_movies'].append({'variant_index':n,'path':target.relative_to(engine.data).as_posix()});save(folder,record)

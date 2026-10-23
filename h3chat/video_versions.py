"""Immutable clip alternatives, scoped to a chat and a source timeline."""
import copy
import hashlib
import json
import math
import re
import time
from .video_resume import checkpoint
from .downloads import safe_join


def snapshot(value, index):
    from .video_edit import clip_source
    record=value['record'];source=clip_source(value,index)
    key=hashlib.sha256(json.dumps(source,sort_keys=True).encode()).hexdigest()[:24]
    return {'id':key,'source':copy.deepcopy(source),'output':record['outputs'][index],
        'scene':copy.deepcopy(record['timeline'][index]),'prompt':record['prompts'][index],
        'parameters':copy.deepcopy(record['parameters'][index]),'images':copy.deepcopy(value['images'])}


def catalog(app, chat_id, ident, value):
    """Also discover older and sibling edits, without modifying saved records."""
    rows=app.store.all("SELECT id,status,COALESCE(json_extract(payload,'$.settings._video_edit.source'),json_extract(payload,'$.settings._video_assemble'),json_extract(payload,'$.settings._video_timeline_recover'),CASE WHEN json_extract(payload,'$.settings._video_clip.action')='replace' THEN json_extract(payload,'$.settings._video_clip.source') END) AS parent FROM jobs WHERE chat_id=? ORDER BY created",(chat_id,))
    parents={};terminal={}
    for row in rows:
        parent=row['parent']
        if isinstance(parent,str):parents[row['id']]=parent
        if row['status'] in ('done','cancelled','failed','interrupted'):terminal[row['id']]=row['status']
    def root(node):
        seen=set()
        while node in parents and node not in seen:seen.add(node);node=parents[node]
        return node
    origin=root(ident);history=[[] for _ in value['record']['timeline']]
    def add(candidate,only=None):
        record=candidate['record']
        if len(record['timeline'])!=len(history):return
        for i,scene in enumerate(record['timeline']):
            current=value['record']['timeline'][i]
            if scene['start']!=current['start'] or scene['frames']!=current['frames']:return
        for i in range(len(history)):
            if only is not None and i+1 not in only:continue
            variants=record.get('clip_versions',[[] for _ in history])[i]
            if not variants:variants=[snapshot(candidate,i)]
            for item in variants:
                if not any(v['id']==item['id'] for v in history[i]):history[i].append(copy.deepcopy(item))
    # Put the original first, including lazy intervals of uploaded movies.
    if origin!=ident:
        try:
            from .video_edit import source
            add(source(app,chat_id,origin,segment_seconds=value['record'].get('import_segment_seconds')))
        except (ValueError,OSError):pass
    else:add(value)
    for candidate_id,status in terminal.items():
        if candidate_id==ident or root(candidate_id)!=origin:continue
        try:
            saved=checkpoint(app.data,candidate_id)
            # A stopped edit still owns its committed alternatives. Never offer
            # a generated-but-not-installed scene, or an unfinished base movie.
            if status!='done' and not saved.get('working_timeline'):continue
            row=app.store.one("SELECT m.meta,json_extract(j.payload,'$.media') AS media FROM jobs j JOIN messages m ON m.id=j.message_id WHERE j.id=? AND j.chat_id=?",(candidate_id,chat_id))
            refs=json.loads(row['meta']).get('references',json.loads(row['media'] or '[]'))
            only=set(saved.get('revision_completed',[])) if status!='done' else None
            if saved.get('revision_remount') is False and not saved.get('working_timeline'):
                # Old whole-clip exports already contain an alternative. Partial
                # exports need the explicit CPU timeline recovery to splice them.
                only=set()
                for p in saved.get('revision_request',[]):
                    n=p['clip'];i=n-1
                    if 'start' in p or n not in saved.get('revision_completed',[]):continue
                    generated=saved.get('revision_generated',{}).get(str(n))
                    plan=saved.get('revision_plans',{}).get(str(n))
                    if not generated or not plan:continue
                    fitted=app.data/'outputs'/candidate_id/f'fitted-{n:03d}.mp4'
                    path=fitted.relative_to(app.data).as_posix() if fitted.is_file() else generated['path']
                    if saved.get('imported_size') and not fitted.is_file():continue
                    only.add(n)
                    saved['outputs'][i]=path
                    if saved.get('clip_sources') is not None:saved['clip_sources'][i]=None
                    saved['parameters'][i]=saved['parameters'][i]|generated['generation']
                    saved['prompts'][i]=re.sub(r'<Picture\s+(\d+)>',lambda m:f"<Picture {p['images'][int(m[1])-1]}>",plan['prompt'],flags=re.I)
                    saved['timeline'][i].update(images=[{'index':j,'role':'reference'} for j in p['images']],generation_mode=p.get('mode','reference'),lip_sync=p.get('lip_sync',False))
            add({'record':saved,'images':[r for r in refs if r['mime'].startswith('image/')]},only)
        except (ValueError,OSError,KeyError,TypeError):continue
    add(value)
    dates={}
    for variants in history:
        for variant in variants:
            merge_images(value,variant)
            if not variant.get('created'):
                path=variant['source']['path']
                if path not in dates:
                    try:dates[path]=safe_join(app.data,path).stat().st_mtime
                    except (ValueError,OSError):dates[path]=None
                variant.update(created=dates[path],created_source='file')
    selected=value['record'].get('selected_versions',{})
    value['record']['clip_versions']=history
    value['record']['selected_versions']={str(i+1):selected.get(str(i+1),snapshot(value,i)['id']) for i in range(len(history))}
    return history


def choices(app, chat_id, ident, value, selected=None):
    history=catalog(app,chat_id,ident,value)
    if selected is None:selected={}
    if not isinstance(selected,dict):raise ValueError('Versioni dei clip non valide.')
    for key,ident in selected.items():
        if not isinstance(key,str) or not key.isdigit() or str(int(key))!=key or not 1<=int(key)<=len(history) or not isinstance(ident,str):
            raise ValueError('Selezione versione del clip non valida.')
        if not any(v['id']==ident for v in history[int(key)-1]):raise ValueError('La versione scelta non appartiene a questa timeline.')
    return selected.copy()


def merge_images(value,variant):
    mapping={};known={r['id']:i for i,r in enumerate(value['images'],1)}
    for ordinal,ref in enumerate(variant['images'],1):
        found=known.get(ref['id'])
        if found is None:
            value['images'].append(copy.deepcopy(ref));value['refs'].append(copy.deepcopy(ref));found=len(value['images']);known[ref['id']]=found
        mapping[ordinal]=found
    return mapping


def remap_prompt(prompt,mapping):
    return re.sub(r'<Picture\s+(\d+)>',lambda m:f'<Picture {mapping[int(m[1])]}>',prompt,flags=re.I)


def apply(value, selected, data):
    """Select server-owned snapshots; request bodies never provide file paths."""
    record=value['record'];record.setdefault('clip_sources',[None]*len(record['timeline']))
    for key,ident in selected.items():
        index=int(key)-1;variant=next(v for v in record['clip_versions'][index] if v['id']==ident)
        source=variant['source'];path=source.get('path');start=source.get('start')
        if not isinstance(path,str) or type(start) not in (int,float) or not math.isfinite(start) or start<0:raise ValueError('Origine della versione non valida.')
        with safe_join(data,path).open('rb') as stream:
            if stream.read(12)[4:8]!=b'ftyp':raise ValueError('Il video della versione non è disponibile.')
        scene=copy.deepcopy(variant['scene']);mapping=merge_images(value,variant)
        for image in scene.get('images',[]):image['index']=mapping[image['index']]
        prompt=remap_prompt(variant['prompt'],mapping)
        if 'prompt' in scene:scene['prompt']=prompt
        record['timeline'][index]=scene;record['prompts'][index]=prompt
        record['parameters'][index]=copy.deepcopy(variant['parameters']);record['outputs'][index]=variant['output']
        record['clip_sources'][index]=copy.deepcopy(source) if source['path']!=variant['output'] or start else None
        record['selected_versions'][key]=ident
        if record.get('batch_generated_audio') and len(record['timeline'])==1 and variant.get('audio'):
            previous=value['audio'];value['audio']=copy.deepcopy(variant['audio'])
            value['refs']=[copy.deepcopy(value['audio']) if r['id']==previous['id'] else r for r in value['refs']]
        if record.get('storyboard'):record['storyboard']['shots'][index]=copy.deepcopy(scene)
    if selected:record.pop('recreate_recipes',None)
    record['edited_clips']=[i+1 for i,variants in enumerate(record['clip_versions']) if record['selected_versions'][str(i+1)]!=variants[0]['id']]


def describe(value,index):
    history=value['record']['clip_versions'][index]
    return [{'id':v['id'],'label':(f"Batch · variante {v['parameters']['variant_index']}/{v['parameters'].get('variants',1)}" if v['parameters'].get('variant_index') else 'Originale' if n==0 else f'Versione {n}')+
        (' · '+v['parameters']['timeline_label'] if n and v['parameters'].get('timeline_label') else '')+
        (f" · {v['parameters']['steps']} passi" if n and v['parameters'].get('steps') else ''),
        'url':'/media/'+v['source']['path'],'preview_start':v['source']['start'],
        'source_interval':v['source']['path']!=v['output'] or bool(v['source']['start']),
        'created':v.get('created'),'created_source':v.get('created_source'),'seed':v['parameters'].get('seed'),
        'variant_index':v['parameters'].get('variant_index'),'variants_mode':v['parameters'].get('variants_mode'),'variant_batch_id':v['parameters'].get('variant_batch_id'),
        'prompt':remap_prompt(v['prompt'],merge_images(value,v))} for n,v in enumerate(history)]


def remember(value,record,index):
    original=snapshot(value,index);history=record.setdefault('clip_versions',[[] for _ in record['timeline']])[index]
    current=snapshot(value|{'record':record},index)
    current.update(created=time.time(),created_source='generated')
    for item in ([original] if not history else [])+[current]:
        if not any(v['id']==item['id'] for v in history):history.append(item)
    record.setdefault('selected_versions',{})[str(index+1)]=current['id']

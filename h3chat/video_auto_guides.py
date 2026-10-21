"""Optional queued image edits of exact source keyframes, before video loading."""
import copy
import math
import re
from .downloads import Cancelled,safe_join
from .image_options import options as image_options
from .store import uid
from .video_resume import save


def points(mode,count):
    return {'first':0,**({'middle':count//2} if mode=='three' else {}),
            **({'last':count-1} if mode in ('ends','three') else {})}


def validate_models(app,patches,settings):
    for patch in patches:
        if not patch.get('auto_anchors'):continue
        model=app.engine.require_model(patch.get('anchor_edit_model') or settings.get('edit_model'),'edit')
        count=len(points(patch['anchors'],360))
        if len(patch['images'])+count>9:
            raise ValueError('Guide automatiche: lascia spazio ai fotogrammi entro i nove riferimenti video.')
        if len(patch['images'])+1>model.get('max_refs',1):
            raise ValueError(f"{model['name']}: ogni guida usa un fotogramma sorgente; puoi aggiungere al massimo {max(0,model.get('max_refs',1)-1)} immagini di riferimento.")
        patch['anchor_edit_model']=model['id']
        image_options(model,settings) # Validate before placing anything in the queue.


def still_prompt(patch):
    mapping={number:index+2 for index,number in enumerate(patch['images'])}
    change=re.sub(r'<Picture\s+(\d+)>',lambda m:f"reference image {mapping[int(m[1])]}",patch['prompt'],flags=re.I)
    change=re.sub(r'<(?:Video|Audio)\s+\d+>','the original video',change,flags=re.I)
    return ('Edit the FIRST input image, an exact frame of the source video, as a single still photograph. '
        'Apply ONLY the requested changes to identity, clothing, background or objects. Preserve all other '
        'attributes: the exact body pose, hands, face unless explicitly changed, expression, camera, framing, '
        'composition, perspective and lighting. Do not move the subject, animate, add shots or create a collage. '
        'Temporal directions, audio and lip-sync describe the later video; do not illustrate them as a new pose. '
        'Other input images supply only the explicitly requested attributes; their pose must not replace the '
        'first image pose. Return one edited frame with the same composition.\nREQUESTED CHANGE: '+change)


def prepare(app,job,value,record,patches,settings,cancel,stage,log,folder):
    selected=[p for p in patches if p.get('auto_anchors')]
    if not selected:return patches
    from .video_edit import source_interval
    validate_models(app,selected,settings)
    saved=record.setdefault('revision_auto_guides',{})
    # Extract and plan all clips before starting the single image-model batch.
    for patch in selected:
        if cancel.is_set():raise Cancelled()
        number=patch['clip'];key=str(number);source=source_interval(value,patch)
        entry=saved.setdefault(key,{'model':patch['anchor_edit_model'],'anchors':patch['anchors'],
                                   'source':source,'images':{},'prompts':{}})
        if entry['model']!=patch['anchor_edit_model'] or entry['source']!=source:
            raise ValueError('Le guide salvate appartengono a un’altra modifica.')
        if not entry.get('originals'):
            stage(f'Guide automatiche · clip {number} · estrazione fotogrammi')
            extracted=app.engine.tool_call('video-remix-worker.py',{'op':'extract_guides',
                'runtime':{'backend':'cpu','threads':2},'folder':str(folder/f'guide-{number:03d}'),
                'source':str(safe_join(app.data,source['path'])),'start':source['start'],
                'frames':source['frames'],'positions':points(patch['anchors'],source['frames'])},cancel,stage,log,timeout=180)
            entry['originals']={name:item|{'path':str(safe_join(app.data,item['path']).relative_to(app.data).as_posix()),
                'mime':'image/png','name':f'Clip {number} · fotogramma originale {name}'} for name,item in extracted.items()}
            save(folder,record)
        missing=[name for name in entry['originals'] if name not in entry['images']]
        if missing and not entry.get('prompt'):
            model=app.engine.require_model(entry['model'],'edit')
            prompt=still_prompt(patch)
            if settings.get('_assistant',True):
                stage(f'Guide automatiche · clip {number} · istruzioni per il modello immagini')
                originals=entry['originals'];refs=[next(iter(originals.values()))]+[value['images'][n-1] for n in patch['images']]
                refined,_=app.engine.refine_image_prompt([],prompt,refs,settings,cancel,log,stage,image_model=model)
                prompt='Edit the first image only; preserve its exact pose, framing and composition.\n'+refined
            entry['prompt']=prompt;save(folder,record)
    needs_images=any(len(e['images'])<len(e['originals']) for e in (saved[str(p['clip'])] for p in selected))
    local_batch=needs_images and any(not app.engine.require_model(p['anchor_edit_model'],'edit').get('remote_media') for p in selected)
    if local_batch:
        stage('Guide automatiche · rilascio motori locali prima del batch immagini')
        app.engine.stop()
    try:
        for patch in selected:
            number=patch['clip'];entry=saved[str(number)]
            model=app.engine.require_model(entry['model'],'edit')
            tuning=settings|{'memory_policy':'on_demand','ram_cache_gb':0,'_image_model':model['id'],'_loras':[]}
            params=image_options(model,settings)
            # Keep the source framing at approximately the model's configured pixel budget.
            first=next(iter(entry['originals'].values()))
            scale=min(math.sqrt(params['width']*params['height']/(first['width']*first['height'])),1536/max(first['width'],first['height']))
            params.update(width=max(256,min(1536,round(first['width']*scale/64)*64)),
                          height=max(256,min(1536,round(first['height']*scale/64)*64)))
            tuning['_image_options']=params
            for position,(name,original) in enumerate(entry['originals'].items(),1):
                if cancel.is_set():raise Cancelled()
                if name in entry['images']:
                    safe_join(app.data,entry['images'][name]['path']).stat()
                    continue
                label=f'Guide automatiche · clip {number} · {position}/{len(entry["originals"])} · '+model['name']
                refs=[original]+[value['images'][n-1] for n in patch['images']]
                prompt=entry['prompt']
                first_guide=entry['images'].get('first')
                if first_guide and len(refs)<model.get('max_refs',1):
                    refs.append(first_guide)
                    prompt+='\nThe LAST input image is the already edited first frame: match ONLY the requested appearance consistently. Keep the pose and composition of the FIRST image.'
                image=app.engine.generate(model,tuning,prompt,refs,job['id']+f'/guide-{number:03d}/{name}',cancel,lambda text:stage(label+' · '+text))
                image.update(id=uid(),name=f'Clip {number} · guida {name} modificata',
                             guide_frame=original['frame'],guide_seconds=original['frame']/24)
                entry['images'][name]=image;entry['prompts'][name]=prompt
                save(folder,record);app.store.gallery.register([image],internal=True)
                app.store.update_answer(job,'Sto preparando i fotogrammi guida prima di generare il video.',
                    meta={'intent':'video','model':model['name'],'video_auto_guides':saved,
                          'references':value['images']+[image for e in saved.values() for image in e['images'].values()]+[r for r in value['refs'] if not r['mime'].startswith('image/')]})
    finally:
        if local_batch:
            stage('Guide automatiche · rilascio modello immagini prima di MiniMax')
            app.engine.stop()
    # Preserve the original validated request for resume, and use generated ordinals only in execution.
    resolved=copy.deepcopy(patches)
    for patch in resolved:
        if not patch.get('auto_anchors'):continue
        entry=saved[str(patch['clip'])];anchors={}
        for name,image in entry['images'].items():
            index=next((i for i,r in enumerate(value['images'],1) if r['id']==image['id']),None)
            if index is None:value['images'].append(image);index=len(value['images'])
            anchors[name]=index
        patch['anchor_images']=anchors
        patch['images']=list(anchors.values())+patch['images']
        patch.pop('auto_anchors');patch.pop('anchor_edit_model',None)
    record['revision_resolved_request']=resolved;save(folder,record)
    return resolved

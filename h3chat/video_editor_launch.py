"""Recover editor defaults from the accepted request, never today's presets."""
import copy
import json
import re
from .downloads import safe_join


def load(app,chat_id,ident,value):
    # A timeline may be reopened either from its source or its resulting edit.
    # Restrict lookup to this chat and these exact sources, not another film.
    sources={ident};parent=value['record'].get('revision_source')
    while isinstance(parent,str) and re.fullmatch('[a-f0-9]{32}',parent) and parent not in sources and len(sources)<160:
        sources.add(parent)
        ancestor=app.store.one('SELECT payload FROM jobs WHERE id=? AND chat_id=?',(parent,chat_id))
        parent=json.loads(ancestor['payload'])['settings'].get('_video_edit',{}).get('source') if ancestor else None
    marks=','.join('?' for _ in sources)
    rows=app.store.all(f"SELECT id,created,status,payload FROM jobs WHERE chat_id=? AND (id=? OR json_extract(payload,'$.settings._video_edit.source') IN ({marks})) ORDER BY created DESC,rowid DESC",(chat_id,ident,*sorted(sources)))
    size=value['record'].get('import_segment_seconds')
    result=None;clips={};patches={};images=[];known={}
    for row in rows:
        payload=json.loads(row['payload']);settings=payload['settings'];edit=settings.get('_video_edit')
        if not edit or edit.get('segment_seconds')!=size:continue
        try:
            saved_path=safe_join(app.data,'outputs/'+row['id']+'/scenes.json')
            saved=json.loads(saved_path.read_text(encoding='utf-8')) if saved_path.is_file() else None
            if saved and [(s['start'],s['frames']) for s in saved['timeline']]!=[(s['start'],s['frames']) for s in value['record']['timeline']]:continue
            refs=[r for r in payload.get('media',[]) if r.get('mime','').startswith('image/')]
            if any(not safe_join(app.data,r['path']).is_file() for r in refs):continue
            from .video_recreate import EDITABLE
            from .video_options import validate
            parameters=validate(settings.get('video_overrides',{}).get(settings['video_model'],{}))
            parameters={k:v for k,v in parameters.items() if k in EDITABLE}
            command={k:copy.deepcopy(edit[k]) for k in ('source','patches','remount') if k in edit}
            command['image_ids']=[r['id'] for r in refs]
            # Preserve the selected resulting footage, not the base used to
            # generate it. Restoring defaults must not undo completed edits.
            command['versions']=copy.deepcopy(value['record'].get('selected_versions',{}))
            ready=set(saved.get('revision_completed',[])) if saved else set()
            pending=[p['clip'] for p in command['patches'] if p['clip'] not in ready]
            common={'model':settings['video_model'],'parameters':parameters,'steps':settings.get('_video_steps'),
                'assistant':settings.get('_assistant',True),'saved_at':row['created']}
            mapping={}
            for n,ref in enumerate(refs,1):
                if ref['id'] not in known:images.append(copy.deepcopy(ref));known[ref['id']]=len(images)
                mapping[n]=known[ref['id']]
            def picture(number):return mapping[number] if number is not None else None
            for patch in command['patches']:
                key=str(patch['clip'])
                if key in clips:continue
                mapped=copy.deepcopy(patch);mapped['images']=[picture(n) for n in patch.get('images',[])]
                mapped['prompt']=re.sub(r'<Picture\s+(\d+)>',lambda m:f'<Picture {picture(int(m[1]))}>',patch['prompt'],flags=re.I)
                for name in ('start_image','anchor_image'):
                    if name in mapped:mapped[name]=picture(mapped[name])
                if 'anchor_images' in mapped:mapped['anchor_images']={k:picture(n) for k,n in mapped['anchor_images'].items()}
                patches[key]=mapped;clips[key]=copy.deepcopy(common)|{'reference_megapixels':patch.get('reference_megapixels',.35)}
            if result is None:result={'job_id':row['id'],'saved_at':row['created'],'status':row['status'],
                'model':settings['video_model'],'parameters':parameters,'steps':settings.get('_video_steps'),
                'assistant':settings.get('_assistant',True),'edit':command,'image_refs':refs,
                'pending_clips':pending,'completed_clips':sorted(ready)}
        except (OSError,ValueError,KeyError,TypeError):continue
    if result:
        result['edit']['patches']=[patches[k] for k in sorted(patches,key=int)]
        result['edit']['image_ids']=[r['id'] for r in images];result['image_refs']=images
        return result|{'clip_launches':clips}
    return None

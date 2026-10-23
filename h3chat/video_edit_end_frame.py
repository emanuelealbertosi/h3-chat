"""Optional final keyframe for reference regeneration, independent of visual memory."""
import copy
from .downloads import safe_join
from .store import uid
from .video_resume import save


def validate(choice, patch, scene, index, count, image_count):
    if choice=='none':return
    if type(choice) is int:
        if not 1<=choice<=image_count:raise ValueError('Scegli un’immagine finale valida.')
    elif not isinstance(choice,str) or choice not in ('original','next'):
        raise ValueError('Fotogramma finale: scegli libero, originale, clip successiva oppure un’immagine.')
    if patch.get('mode','reference')!='reference':raise ValueError('Il raccordo finale indipendente richiede Rigenera · riferimenti.')
    if patch.get('start',0)!=0 or patch.get('end',scene['duration'])!=scene['duration']:
        raise ValueError('Il raccordo finale indipendente richiede Intera clip.')
    if choice=='next' and index+1>=count:raise ValueError('L’ultima clip non ha una clip successiva da cui prendere il fotogramma.')


def prepare(app,value,record,patches,folder,cancel,stage,log):
    resolved=copy.deepcopy(patches)
    saved=record.setdefault('revision_end_frames',{})
    for patch in resolved:
        choice=patch.get('end_frame','none')
        if choice=='none' or type(choice) is int:continue
        from .video_edit import clip_source
        index=patch['clip']-1+(choice=='next')
        scene=value['record']['timeline'][index];source=clip_source(value,index)
        position=0 if choice=='next' else scene['frames']-1
        signature={'choice':choice,'source':source,'frames':scene['frames'],'position':position}
        key=str(patch['clip']);entry=saved.get(key)
        if entry and entry['signature']!=signature:raise ValueError('Il fotogramma finale salvato appartiene a una versione diversa.')
        if entry is None:
            stage(f'Fotogramma finale · clip {patch["clip"]} · estrazione CPU')
            result=app.engine.tool_call('video-remix-worker.py',{'op':'extract_guides','runtime':{'backend':'cpu','threads':2},
                       'folder':str(folder/f'end-frame-{patch["clip"]:03d}'),'source':str(safe_join(app.data,source['path'])),
                       'start':source['start'],'frames':scene['frames'],'positions':{'last':position}},cancel,stage,log,timeout=180)
            image=result['last']|{'id':uid(),'path':safe_join(app.data,result['last']['path']).relative_to(app.data.resolve()).as_posix(),
                                  'mime':'image/png','name':f'Clip {patch["clip"]} · raccordo finale ({choice})'}
            saved[key]={'signature':signature,'image':image};entry=saved[key]
            save(folder,record);app.store.gallery.register([image],internal=True)
        safe_join(app.data,entry['image']['path']).stat()
        ordinal=next((i for i,r in enumerate(value['images'],1) if r['id']==entry['image']['id']),None)
        if ordinal is None:value['images'].append(copy.deepcopy(entry['image']));ordinal=len(value['images'])
        if ordinal not in patch['images']:patch['images'].append(ordinal)
        if len(patch['images'])>9:raise ValueError('Il fotogramma finale richiede uno dei nove posti immagine: riduci i riferimenti selezionati.')
        patch['end_frame']=ordinal
    return resolved

"""Explicit editor drafts, isolated by workspace, chat, source and segment size."""
import copy
import json
import re
import secrets
import time
from .downloads import safe_join


def signature(value):
    return [[round(s['start']*24),s['frames']] for s in value['record']['timeline']]


def path(app,chat_id,ident,value):
    app.store.chat(chat_id)
    if any(not isinstance(x,str) or not re.fullmatch(r'[a-f0-9]{32}',x) for x in (chat_id,ident)):
        raise ValueError('Origine della bozza non valida.')
    size=value['record'].get('import_segment_seconds',0)
    return safe_join(app.data,f'video-editor-drafts/{chat_id}/{ident}-{size}.json')


def validate(app,chat_id,ident,value,state):
    keys={'signature','model','parameters','values','active','common_prompt','image_ids','clips','versions'}
    if not isinstance(state,dict) or set(state)-{'clip_launches'}!=keys:
        raise ValueError('Bozza della timeline non valida.')
    if state['signature']!=signature(value):
        raise ValueError('La suddivisione del video è cambiata: questa bozza appartiene a una timeline diversa.')
    if not isinstance(state['model'],str) or not isinstance(state['parameters'],dict):
        raise ValueError('Impostazioni della bozza non valide.')
    from .video_options import DEFAULTS
    if set(state['parameters'])-set(DEFAULTS):raise ValueError('Parametri della bozza non riconosciuti.')
    values=state['values']
    if not isinstance(values,dict) or set(values)!={'megapixels','video_steps','reference_megapixels','assistant','remount'}:
        raise ValueError('Controlli della bozza non validi.')
    if any(type(values[k]) is not bool for k in ('assistant','remount')) or any(not isinstance(values[k],str) or len(values[k])>32 for k in ('megapixels','video_steps','reference_megapixels')):
        raise ValueError('Valori della bozza non validi.')
    if not isinstance(state['common_prompt'],str) or len(state['common_prompt'])>6000:
        raise ValueError('Prompt comune della bozza non valido.')
    count=len(value['record']['timeline'])
    launches=state.get('clip_launches',{})
    if not isinstance(launches,dict):raise ValueError('Impostazioni dei clip non valide.')
    for key,launch in launches.items():
        if not isinstance(key,str) or not key.isdigit() or str(int(key))!=key or not 1<=int(key)<=count or not isinstance(launch,dict) or set(launch)-{'reference_megapixels'}!={'model','parameters','steps','assistant','saved_at'}:
            raise ValueError('Ultimo lancio del clip non valido.')
        if not isinstance(launch['model'],str) or not isinstance(launch['parameters'],dict) or set(launch['parameters'])-set(DEFAULTS) or type(launch['assistant']) is not bool or type(launch['saved_at']) not in (int,float):
            raise ValueError('Impostazioni dell’ultimo lancio non valide.')
        from .video_options import validate_steps
        validate_steps(launch['steps'])
        if 'reference_megapixels' in launch and (type(launch['reference_megapixels']) not in (int,float) or not .1<=launch['reference_megapixels']<=.98):raise ValueError('Risoluzione guida del clip non valida.')
    if state['active'] is not None and (type(state['active']) is not int or not 1<=state['active']<=count):
        raise ValueError('Clip aperta nella bozza non valida.')
    from . import video_versions
    video_versions.choices(app,chat_id,ident,value,state['versions'])
    ids=state['image_ids']
    if not isinstance(ids,list) or len(ids)>2048 or any(not isinstance(x,str) for x in ids) or len(ids)!=len(set(ids)):
        raise ValueError('Riferimenti della bozza non validi.')
    known={r['id']:r for r in value['images']}
    missing=[x for x in ids if x not in known]
    if any(not re.fullmatch(r'[a-f0-9]{32}',x) for x in missing):raise ValueError('Identificativo immagine della bozza non valido.')
    if len(missing)>9:raise ValueError('La bozza contiene troppe nuove immagini.')
    if missing:
        extra=app.validate_media([{'id':x} for x in missing],canvas=True)
        if any(not r['mime'].startswith('image/') for r in extra):raise ValueError('I riferimenti della bozza devono essere immagini.')
        known.update({r['id']:r for r in extra})
    references=[known[x] for x in ids]
    for ref in references:
        if not safe_join(app.data,ref['path']).is_file():raise ValueError('Un’immagine della bozza non è più disponibile.')
    def image(n):return n is None or (type(n) is int and 1<=n<=len(ids))
    clips=state['clips']
    if not isinstance(clips,list) or len(clips)!=count:raise ValueError('Elenco dei clip della bozza non valido.')
    allowed={'enabled','clip','prompt','images','lip_sync','audio_guide','range','first','last','frames','mode','anchors','anchor_image','start_image','auto_anchors','anchor_edit_model','anchor_images'}
    for i,(clip,scene) in enumerate(zip(clips,value['record']['timeline']),1):
        if not isinstance(clip,dict) or set(clip)-{'audio_guide'}!=allowed-{'audio_guide'} or type(clip['clip']) is not int or clip['clip']!=i or type(clip['frames']) is not int or clip['frames']!=scene['frames']:
            raise ValueError('La bozza non corrisponde ai segmenti del video.')
        if 'audio_guide' in clip and type(clip['audio_guide']) is not bool:raise ValueError('Guida audio della bozza non valida.')
        if any(type(clip[k]) is not bool for k in ('enabled','lip_sync','range','auto_anchors')):
            raise ValueError('Selezioni dei clip della bozza non valide.')
        if any(type(clip[k]) is not int for k in ('first','last')) or not 0<=clip['first']<clip['last']<=scene['frames']:
            raise ValueError('Intervallo del clip nella bozza non valido.')
        if not isinstance(clip['prompt'],str) or len(clip['prompt'])>6000 or clip['mode'] not in ('video','reference','i2v') or clip['anchors'] not in ('none','first','ends','three'):
            raise ValueError('Modifica del clip nella bozza non valida.')
        if not isinstance(clip['images'],list) or len(clip['images'])>9 or any(not image(n) or n is None for n in clip['images']) or len(clip['images'])!=len(set(clip['images'])):
            raise ValueError('Immagini del clip nella bozza non valide.')
        if not image(clip['anchor_image']) or not image(clip['start_image']) or not isinstance(clip['anchor_edit_model'],str):
            raise ValueError('Guide del clip nella bozza non valide.')
        anchors=clip['anchor_images']
        if not isinstance(anchors,dict) or set(anchors)-{'first','middle','last'} or any(not image(n) or n is None for n in anchors.values()):
            raise ValueError('Fotogrammi guida della bozza non validi.')
    json.dumps(state,allow_nan=False)
    return references


def load(app,chat_id,ident,value):
    target=path(app,chat_id,ident,value)
    if not target.exists():return None
    try:
        draft=json.loads(target.read_text(encoding='utf-8'))
        if not isinstance(draft,dict) or draft.get('version')!=1:raise ValueError('Versione della bozza non supportata.')
        refs=validate(app,chat_id,ident,value,draft['state'])
        return draft|{'image_refs':refs}
    except (OSError,KeyError,TypeError,ValueError) as exc:
        raise ValueError('Impossibile riprendere la bozza salvata. '+str(exc)) from exc


def save(app,chat_id,ident,body):
    if not isinstance(body,dict) or set(body)!={'state','segment_seconds'}:
        raise ValueError('Salvataggio bozza non valido.')
    from .video_edit import source
    value=source(app,chat_id,ident,body['segment_seconds'])
    refs=validate(app,chat_id,ident,value,body['state'])
    state=copy.deepcopy(body['state']);draft={'version':1,'saved_at':time.time(),'state':state}
    raw=json.dumps(draft,ensure_ascii=False,allow_nan=False)
    if len(raw.encode('utf-8'))>8*1024*1024:raise ValueError('Bozza troppo grande.')
    target=path(app,chat_id,ident,value);target.parent.mkdir(parents=True,exist_ok=True)
    temp=target.with_name(target.name+'.'+secrets.token_hex(8)+'.tmp')
    try:
        temp.write_text(raw,encoding='utf-8');temp.replace(target)
    finally:temp.unlink(missing_ok=True)
    from .gallery_timelines import touch
    touch(app.store.gallery,ident,draft['saved_at'])
    return draft|{'image_refs':refs}


def remove(app,chat_id,ident,body):
    from .video_edit import source
    value=source(app,chat_id,ident,body.get('segment_seconds'))
    path(app,chat_id,ident,value).unlink(missing_ok=True)
    return {'ok':True}

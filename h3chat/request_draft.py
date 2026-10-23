"""Return an editable request draft without enqueueing or exposing credentials."""
import json
from .video_options import DEFAULTS,REQUEST_KEYS


def load(app,chat_id,message_id):
    app.store.chat(chat_id)
    message=app.store.one('SELECT rowid AS input_rowid,id,role FROM messages WHERE chat_id=? AND id=?',(chat_id,message_id))
    if not message:raise ValueError('Messaggio non trovato in questa chat.')
    if message['role']=='assistant':
        row=app.store.one('SELECT payload FROM jobs WHERE chat_id=? AND message_id=? ORDER BY created DESC LIMIT 1',(chat_id,message_id))
    else:
        row=app.store.one("SELECT payload FROM jobs WHERE chat_id=? AND json_extract(payload,'$.until')=? ORDER BY created DESC LIMIT 1",(chat_id,message['input_rowid']))
    if not row:raise ValueError('La richiesta originale non è disponibile.')
    payload=json.loads(row['payload']);settings=payload['settings']
    controls={name:settings.get(key,default) for name,key,default in (
        ('assistant','_assistant',True),('image_model','_image_model',''),('music','_music',False),
        ('video','_video',False),('voice','_voice',False),('web','_web',False),('transcribe','_transcribe',False),
        ('music_fields','_music_fields',{}),('voice_fields','_voice_fields',{}),('music_quality','music_quality','model'),
        ('music_max_duration','_music_max_duration',None),('video_quality','_video_quality','high'),
        ('video_steps','_video_steps',None),('video_editing','_video_editing','continuous'),
        ('video_segment_seconds','_video_segment_seconds',None))}
    if controls['music']:
        controls['music_model']=settings['music_model']
        controls['music_resing']=bool(settings.get('_music_resing'))
        controls['music_presets']={settings['music_model']:settings.get('_music_request_parameters',settings.get('music_overrides',{}).get(settings['music_model'],{}))}
    if controls['image_model'] and settings.get('_image_request_parameters'):
        controls['image_presets']={controls['image_model']:settings['_image_request_parameters']}
    if controls['video']:
        controls['video_model']=settings['video_model']
        preset=DEFAULTS|settings.get('video_overrides',{}).get(settings['video_model'],{})
        controls['video_parameters']={k:preset[k] for k in REQUEST_KEYS if k!='aspect'}
        if settings.get('_video_aspect'):controls['video_parameters']['aspect']=settings['_video_aspect']
    media=payload['media'];edit=settings.get('_video_edit');extra={}
    if edit:
        images=[m for m in media if m.get('mime','').startswith('image/')]
        selected={n for patch in edit['patches'] for n in patch.get('images',[])}
        media=[m for i,m in enumerate(images,1) if i in selected]
        extra['video_edit']={k:edit[k] for k in ('source','patches','remount','parameters','versions','segment_seconds') if k in edit}
        extra['video_edit']['image_ids']=[m['id'] for m in images]
        try:
            source=app.store.gallery.get(edit['source'])
            if source['mime'].startswith('video/'):
                media=[{k:source[k] for k in ('id','name','path','mime')}]+media
        except ValueError:pass
    return {'prompt':payload['prompt'],'media':media,'canvas':bool(payload.get('canvas')),**extra,
            'controls':controls,'lab':settings.get('_lab','auto'),'lab_source':settings.get('_lab_source',''),
            'slides':settings.get('_slides'),'infographic':settings.get('_infographic'),
            'manim_presentation':settings.get('_manim_presentation'),
            'loras':[{k:x[k] for k in ('id','name','weight','model_id','model_name') if k in x} for x in payload.get('loras',[])]}

"""Reuse only recorded illustrations from an explicitly selected job in this chat."""
import json
import re
import struct
from .downloads import safe_join


def resolve(app, chat_id, job_id):
    if not isinstance(job_id,str) or not re.fullmatch('[a-f0-9]{32}',job_id):
        raise ValueError('Richiesta di origine delle immagini non valida.')
    row=app.store.one('SELECT m.meta FROM jobs j JOIN messages m ON m.id=j.message_id WHERE j.id=? AND j.chat_id=?',(job_id,chat_id))
    if not row:raise ValueError('La richiesta delle immagini non appartiene a questa chat.')
    meta=json.loads(row['meta']);plan=meta.get('slide_image_plan',[])
    media={m['id']:m for m in meta.get('artifact',{}).get('media',[])+meta.get('slide_generated_images',[])}
    if meta.get('slide_image_cache'):
        plan=[{'asset_id':x['media']['id'],**{k:x[k] for k in ('description','aspect','width','height') if k in x}} for x in meta['slide_image_cache']]
        media.update({x['media']['id']:x['media'] for x in meta['slide_image_cache']})
    result=[]
    for item in plan:
        image=media.get(item.get('asset_id'))
        if not image or not image.get('mime','').startswith('image/') or item.get('role'):continue
        try:
            path=safe_join(app.data,image['path'])
            if not path.is_file():continue
            # Generated images are PNG. Read IHDR on CPU without importing a
            # model runtime or assuming Pillow is in the server interpreter.
            with path.open('rb') as stream:header=stream.read(24)
            if len(header)==24 and header[:8]==b'\x89PNG\r\n\x1a\n' and header[12:16]==b'IHDR':width,height=struct.unpack('>II',header[16:24])
            else:width,height=item.get('width',0),item.get('height',0)
            if type(width) is not int or type(height) is not int or not 0<width<=32768 or not 0<height<=32768:continue
        except (ValueError,OSError,KeyError):continue
        if any(x['media']['id']==image['id'] for x in result):continue
        result.append({'media':dict(image),'description':str(item.get('description',''))[:800],
                       'aspect':item.get('aspect','4:3'),'width':width,'height':height})
    return result[:100]


def offer(app,chat_id,job_id):
    items=resolve(app,chat_id,job_id)
    return {'job_id':job_id,'count':len(items)} if items else None

"""Authorized video backgrounds, decoded sequentially without another model."""
import math
from pathlib import Path
from .downloads import safe_join

def validate(value):
    if not isinstance(value,dict) or set(value)-{'asset_id','poster_id','duration','width','height','audio','fit','end','sound'}:raise ValueError('Video di sfondo non valido.')
    for key in ('asset_id','poster_id'):
        if not isinstance(value.get(key),str) or not 1<=len(value[key])<=150:raise ValueError('Riferimento video non valido.')
    if type(value.get('duration')) not in (int,float) or not math.isfinite(value['duration']) or not 0<value['duration']<=3600:raise ValueError('Durata video non valida.')
    if any(type(value.get(k)) is not int or not 1<=value[k]<=16384 for k in ('width','height')) or type(value.get('audio')) is not bool:raise ValueError('Dimensioni video non valide.')
    if value.get('fit') not in ('contain','cover') or value.get('end') not in ('freeze','loop') or value.get('sound') not in ('mute','keep','duck'):raise ValueError('Opzioni video non valide.')

def asset(data,media,ident,mime):
    item=next((m for m in media if m.get('id')==ident and m.get('mime')==mime),None)
    if not item or not item.get('path','').startswith(('uploads/','outputs/')):raise ValueError('Video o anteprima non disponibili negli allegati di questa infografica.')
    path=safe_join(data,item['path'])
    if not path.is_file():raise ValueError('File video non disponibile.')
    return path

def select(opts,media):
    if opts.get('video_background','auto')=='off':return None
    videos=[m for m in media if m.get('mime')=='video/mp4']
    if opts.get('video_id'):
        item=next((m for m in videos if m['id']==opts['video_id']),None)
        if not item:raise ValueError('Allega il video selezionato o sceglilo dalla galleria.')
        return item
    if len(videos)>1:raise ValueError('Hai allegato più video: scegli quello da usare come sfondo nelle opzioni Infografica.')
    return videos[0] if videos else None

def select_many(opts,media):
    if opts.get('layout','full')=='full':
        item=select(opts,media);return [item] if item else []
    if opts.get('video_background','auto')=='off':return []
    videos=list({m['id']:m for m in media if m.get('mime')=='video/mp4'}.values())
    if opts.get('video_id'):
        item=next((m for m in videos if m['id']==opts['video_id']),None)
        if not item:raise ValueError('Allega il video principale selezionato.')
        videos.remove(item);videos.insert(0,item)
    if len(videos)>6:raise ValueError('Split screen: allega fino a sei video; rimuovi quelli che non vuoi usare.')
    return videos

def probe(path,poster):
    import av
    with av.open(str(path),options={'protocol_whitelist':'file'}) as inp:
        if not inp.streams.video:raise ValueError('Il file non contiene immagini video.')
        stream=inp.streams.video[0]
        duration=float(stream.duration*stream.time_base) if stream.duration is not None else (inp.duration or 0)/av.time_base
        frame=next(inp.decode(stream),None)
        if not frame:raise ValueError('Il video è vuoto o non decodificabile.')
        image=oriented(frame);image.thumbnail((1280,1280));image.save(poster,'JPEG',quality=88)
        width,height=oriented(frame).size
        if not 0<duration<=3600 or max(width,height)>16384:raise ValueError('Video non supportato: durata massima un’ora, risoluzione massima 16K.')
        return {'duration':duration,'width':width,'height':height,'audio':bool(inp.streams.audio)}

def oriented(frame):
    image=frame.to_image()
    rotation=float(getattr(frame,'rotation',0) or 0)
    if rotation:image=image.rotate(rotation,expand=True)
    return image

def source_time(seconds,duration,end):
    return seconds%duration if end=='loop' else min(seconds,max(0,duration-1e-6))

class Frames:
    """Keep only current/lookahead frames. Restart decoding only when looping."""
    def __init__(self,path,video):
        self.path=path;self.video=video;self.last=-1;self.container=None;self.current=None;self.next=None
        self.restart()
    def restart(self):
        import av
        self.close();self.container=av.open(str(self.path),options={'protocol_whitelist':'file'})
        stream=self.container.streams.video[0];self.origin=float((stream.start_time or 0)*stream.time_base)
        self.frames=iter(self.container.decode(stream));self.current=next(self.frames);self.next=next(self.frames,None)
    def image(self,seconds):
        target=source_time(seconds,self.video['duration'],self.video['end'])
        if target<self.last:self.restart()
        self.last=target
        while self.next is not None and float(self.next.time or 0)-self.origin<=target+1e-6:
            self.current=self.next;self.next=next(self.frames,None)
        image=oriented(self.current);image.thumbnail((1920,1920));return image
    def close(self):
        if self.container:self.container.close();self.container=None

"""Bounded source-video conditioning. Imported lazily inside the private worker."""
import math

REFERENCE_MEGAPIXELS = .35


def video_block(latent):
    # PackedLayout reads audio span even for silent video-only references.
    return {'kind':'video','latent_t':latent.shape[2],'latent_h':latent.shape[3],
            'latent_w':latent.shape[4],'latent':latent,'ref_audio_t':0,'audio_latent':None}


def validate_source(value):
    if not isinstance(value,dict) or set(value)-{'path','start','frames','megapixels','anchors'}:
        raise ValueError('Sorgente della modifica video non valida.')
    path=value.get('path');start=value.get('start');frames=value.get('frames')
    mp=value.get('megapixels',REFERENCE_MEGAPIXELS)
    anchors=value.get('anchors','none')
    if anchors not in ('none','first','ends','three'):raise ValueError('Ancoraggio sorgente: scegli libero, inizio, inizio e fine, oppure inizio/metà/fine.')
    if not isinstance(path,str) or not path or type(start) not in (int,float) or not math.isfinite(start) or start<0:
        raise ValueError('Intervallo della sorgente video non valido.')
    if type(frames) is not int or not 24<=frames<=360:
        raise ValueError('Modifica video: ogni tratto deve durare da 1 a 15 secondi.')
    if type(mp) not in (int,float) or not math.isfinite(mp) or not .1<=mp<=.98:
        raise ValueError('Dettaglio del video sorgente: scegli da 0,1 a 0,98 MP.')
    return {'path':path,'start':start,'frames':frames,'megapixels':mp}|({'anchors':anchors} if anchors!='none' else {})


def reference_shape(width,height,megapixels):
    if min(width,height)<=0 or max(width,height)>32768:
        raise ValueError('Dimensioni del video sorgente non valide.')
    scale=min(1,math.sqrt(megapixels*1024**2/(width*height)))
    w=max(2,round(width*scale/2)*2);h=max(2,round(height*scale/2)*2)
    return w,h,math.ceil(w/32)*32,math.ceil(h/32)*32


def decode_source(value,canvas=None):
    """Read the actual selected interval at 24 fps, retaining every source moment.

    Decode sequentially from a preceding keyframe; no JPEG intermediates, full
    movie allocation or GPU decoder. Source resolution is bounded separately
    from output resolution. Only the two model-grid tail frames are repeated.
    """
    import av
    import numpy as np
    import torch
    value=validate_source(value);count=value['frames'];start=value['start']
    with av.open(value['path'],options={'protocol_whitelist':'file'}) as source:
        if not source.streams.video:raise ValueError('La sorgente non contiene un video.')
        stream=source.streams.video[0];stream.codec_context.thread_count=2
        w,h,cw,ch=reference_shape(stream.width,stream.height,value['megapixels'])
        if canvas:
            w,h,cw,ch=(canvas[k] for k in ('output_width','output_height','width','height'))
            if any(type(v) is not int or v<=0 for v in (w,h,cw,ch)) or w>cw or h>ch:raise ValueError('Canvas guida allineata non valido.')
            scale=min(w/stream.width,h/stream.height)
            w=max(2,round(stream.width*scale/2)*2);h=max(2,round(stream.height*scale/2)*2)
        base=float((stream.start_time or 0)*stream.time_base)
        duration=float(stream.duration*stream.time_base) if stream.duration is not None else None
        if duration is not None and start+count/24>duration+1/24+1e-6:
            raise ValueError('Il tratto richiesto supera la durata del video sorgente.')
        source.seek(max(0,int((base+start)/stream.time_base)),stream=stream,backward=True)
        pixels=np.zeros((count,ch,cw,3),dtype=np.uint8);left=(cw-w)//2;top=(ch-h)//2
        position=0;previous=None;last_time=None
        def put(frame):
            nonlocal position
            pixels[position,top:top+h,left:left+w]=frame.reformat(width=w,height=h,format='rgb24').to_ndarray()
            position+=1
        for frame in source.decode(stream):
            if frame.pts is None:continue
            when=float(frame.pts*stream.time_base)-base
            if when<start:
                previous=frame;last_time=when;continue
            while position<count and start+position/24<=when+1e-6:
                put(previous if previous is not None and when>start+position/24+1e-6 else frame)
            previous=frame;last_time=when
            if position==count:break
        if previous is None or last_time is None or last_time+max(1/24,1/float(stream.average_rate or 24))<start+(count-1)/24-1e-6:
            raise ValueError('Fotogrammi del video sorgente mancanti: impossibile applicare la modifica.')
        while position<count:put(previous)
    frames=torch.from_numpy(pixels).float().div_(255)
    # H3's VAE temporal grid is 17k+5. Pad instead of truncating the source tail.
    grid=max(5,math.ceil((count-5)/17)*17+5)
    if grid>count:frames=torch.cat((frames,frames[-1:].expand(grid-count,-1,-1,-1)),dim=0)
    samples=list(range(0,count,12))
    return frames,frames[samples],{'frames':count,'model_frames':grid,'width':cw,'height':ch,
        'start':start,'duration':count/24,'encoder_fps':2,'megapixels':cw*ch/1024**2 if canvas else value['megapixels'],
        'content_width':w,'content_height':h,'pad_left':left,'pad_top':top,
        'conditioning':'aligned' if canvas else 'reference',
        **({'requested_reference_megapixels':value['megapixels']} if canvas else {})}


def anchor_positions(source):
    mode=source.get('anchors','none')
    return [0,source['frames']//2,source['frames']-1] if mode=='three' else [0,source['frames']-1] if mode=='ends' else [0] if mode=='first' else []


def source_still(frames,info,position):
    """Strip source-grid padding before fitting an anchor to the output canvas."""
    left,top=info['pad_left'],info['pad_top']
    return frames[position:position+1,top:top+info['content_height'],left:left+info['content_width']]

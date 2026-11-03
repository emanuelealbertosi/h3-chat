"""Logical scene durations, independent of H3's native 15-second window."""
import math
import re

def controls(body):
    result={}
    for name,maximum in (('count',100),('seconds',600)):
        value=body.get('video_scene_'+name)
        if value is None:continue
        if type(value) not in ((int,) if name=='count' else (int,float)) or not math.isfinite(value) or not 1<=value<=maximum:
            raise ValueError('Scene video: numero da 1 a 100 e durata da 1 a 600 secondi.')
        result['_video_scene_'+name]=value
    return result

def resolve(settings,prompt):
    from .video_direct_storyboard import request_text
    from .video_clip_budget import NUMBER,number
    from .video_options import prompt_duration,DEFAULTS
    text=request_text(prompt)
    count=settings.get('_video_scene_count',1)
    saved=settings.get('video_overrides',{}).get(settings.get('video_model'),{})
    seconds=settings.get('_video_scene_seconds') or settings.get('_video_segment_seconds') or saved.get('duration',DEFAULTS['duration'])
    explicit=bool(settings.get('_video_scene_count') or settings.get('_video_scene_seconds'))
    count_match=re.search(rf'(?<![\w:.,])({NUMBER})\s+(?:(?:consecutive|consecutiv[ei])\s+)?(?:scene|scenes|clips?|segmenti)\b',text,re.I)
    if count_match:count=number(count_match[1]);explicit=True
    unit=r'(second[io]|seconds?|sec|s|minut[io]|minutes?|min)\b'
    amount=r'(\d+(?:[.,]\d+)?)\s*'+unit
    per=re.search(r'\b(?:scene|scenes|clips?|segmenti)\s+(?:(?:consecutive|consecutiv[ei])\s+)?(?:da|di|of|lasting)\s*'+amount,text,re.I)
    if not per:per=re.search(r'\b(?:durata\s+(?:di\s+)?(?:ogni\s+)?scena|scene\s+duration)\s*[:=]?\s*'+amount,text,re.I)
    if not per:per=re.search(amount+r'\s*(?:ciascun[ao]|ognun[ao]|l[’\']una|each|per\s+scena)',text,re.I)
    if per:seconds=float(per[1].replace(',','.'))*(60 if per[2].lower().startswith('min') else 1);explicit=True
    # Remove the per-scene phrase so it cannot be mistaken for total duration.
    total=prompt_duration(text[:per.start()]+text[per.end():] if per else text,has_audio=True)
    if total is not None:
        seconds=total/count;explicit=True
    if type(count) is not int or not 1<=count<=100 or not math.isfinite(seconds) or seconds<1 or count*seconds>600:
        raise ValueError('Video: da 1 a 100 scene, almeno 1 secondo per scena e massimo 600 secondi complessivi.')
    frames=round(seconds*24)
    return {'count':count,'scene_seconds':frames/24,'duration':count*frames/24,'explicit':explicit}

def apply(settings,prompt,*,remote=False):
    spec=resolve(settings,prompt)
    if remote and (spec['count']>1 or spec['duration']>15):
        raise ValueError('Video con più scene o scene oltre 15 secondi: scegli MiniMax H3 locale.')
    model=settings['video_model'];presets=settings.get('video_overrides',{})
    result=settings|{'video_overrides':presets|{model:presets.get(model,{})|{'duration':min(spec['scene_seconds'],settings.get('_video_segment_seconds') or 15)}}}
    if spec['count']>1 or spec['duration']>(settings.get('_video_segment_seconds') or 15) or settings.get('_video_editing')=='storyboard':
        result=result|{'_video_duration':spec['duration'],'_video_sequence':spec}
    return result

def scenes(settings):
    from .video_timeline import timeline
    spec=settings.get('_video_sequence')
    if not spec:return timeline(settings['_video_duration'],settings.get('_video_segment_seconds') or 15)
    result=[]
    for logical in range(spec['count']):
        for part in timeline(spec['scene_seconds'],settings.get('_video_segment_seconds') or 15):
            offset=part['start'];start=logical*spec['scene_seconds']
            result.append(part|{'index':len(result),'start':start+offset,'logical_scene':logical+1,
                'logical_start':start,'logical_duration':spec['scene_seconds'],'logical_offset':offset})
    if len(result)>160:raise ValueError('Il video richiede più di 160 segmenti: aumenta la durata massima dei segmenti o riduci le scene.')
    return result

def budget(settings):
    clips=scenes(settings)
    return {'count':len(clips),'minimum':len(clips),'explicit':True,
        'end_frames':[round((s['start']+s['duration'])*24) for s in clips],
        'segment_seconds':settings.get('_video_segment_seconds') or 15}

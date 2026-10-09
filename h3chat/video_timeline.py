"""Audio-driven scene boundaries and stable reference identities."""
import copy
import math

def tail_padding_samples(count,wanted,rate,*,tail=False):
    missing=wanted-count
    if missing<=0:return 0
    if count>0 and tail and missing<=math.ceil(rate/24)+1:return missing
    raise ValueError('La traccia non copre l’intervallo audio richiesto.')

def validate_audio_interval(duration,start,seconds,*,tail=False):
    if not all(math.isfinite(v) for v in (duration,start,seconds)) or duration<=0 or start<0 or seconds<=0:raise ValueError('Intervallo audio non valido.')
    tolerance=1/24+1/8000 if tail else 1/192000
    if start>=duration or start+seconds>duration+tolerance:raise ValueError(f'Audio troppo corto: servono {seconds:g} secondi dalla posizione {start:g}.')

def timeline(duration):
    if not math.isfinite(duration) or not 0<duration<=600:raise ValueError('Video con audio: durata massima 10 minuti.')
    frames=math.ceil(duration*24)
    return [{'index':i,'start':start/24,'duration':min(360,frames-start)/24,'frames':min(360,frames-start)} for i,start in enumerate(range(0,frames,360))]

def scene_plan(plan,scene,soundtrack_index,prompt=None,*,audio_start=0):
    result=copy.deepcopy(plan);start=scene['start'];end=start+scene['duration']
    result['prompt']=prompt or plan['prompt']
    for entry in result['images']:
        when=entry['seconds']
        if entry['role']=='keyframe':
            if start<=when<end or abs(when-end)<1e-5 and scene.get('last'):entry['seconds']=max(0,when-start)
            else:entry.update(role='reference',seconds=0)
    for entry in result['audios']:
        if entry['index']==soundtrack_index:
            # Use the requested source window, regardless of invented LLM offsets.
            entry['start']=audio_start+start
            if entry['role']=='reference':entry['role']='reuse'
    result['prompt']+=f'\nThis is clip {scene["index"]+1}, covering seconds {start:g} to {end:g} of one continuous film. Use supplied visual memory to preserve subject identities, clothing and visual style while advancing the requested action. Follow the intended location/scene changes; keep environment and lighting coherent within each setting. Do not restart the opening.'
    return result

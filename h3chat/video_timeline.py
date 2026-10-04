"""Audio-driven scene boundaries and stable reference identities."""
import copy
import math

def timeline(duration):
    if not math.isfinite(duration) or not 0<duration<=600:raise ValueError('Video con audio: durata massima 10 minuti.')
    frames=math.ceil(duration*24)
    return [{'index':i,'start':start/24,'duration':min(360,frames-start)/24,'frames':min(360,frames-start)} for i,start in enumerate(range(0,frames,360))]

def scene_plan(plan,scene,soundtrack_index,prompt=None):
    result=copy.deepcopy(plan);start=scene['start'];end=start+scene['duration']
    result['prompt']=prompt or plan['prompt']
    for entry in result['images']:
        when=entry['seconds']
        if entry['role']=='keyframe':
            if start<=when<end or abs(when-end)<1e-5 and scene.get('last'):entry['seconds']=max(0,when-start)
            else:entry.update(role='reference',seconds=0)
    for entry in result['audios']:
        if entry['index']==soundtrack_index:
            # The final soundtrack is the whole selected file, starting at zero.
            # Ignore an Assistant-invented offset so conditioning stays in sync.
            entry['start']=start
            if entry['role']=='reference':entry['role']='reuse'
    result['prompt']+=f'\nThis is clip {scene["index"]+1}, covering seconds {start:g} to {end:g} of one continuous film. Continue actions and preserve subject identities, clothing, environment and lighting from the supplied visual memory. Do not restart the opening.'
    return result

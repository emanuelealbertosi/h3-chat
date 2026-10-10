"""Plan ordered, timed shots and select only their actual image references."""
import copy
import json
import math
import re
from .downloads import Cancelled
from .remote_llm import EmptyCompletion, StructuredCompletionError
from .video_options import validate_plan
from .video_request import repeated_scene, spoken_lines
from .video_clip_budget import contract, requested

MAX_SHOTS=160
SCHEMA={'type':'object','properties':{
    'style':{'type':'string','maxLength':1200},
    'shots':{'type':'array','minItems':1,'maxItems':MAX_SHOTS,'items':{'type':'object','properties':{
        'end':{'type':'number'},'prompt':{'type':'string','maxLength':2400},
        'time_basis':{'type':'string','enum':['local','video','source']},
        'continuity':{'type':'string','enum':['cut','continue']},'lip_sync':{'type':'boolean'},
        'images':{'type':'array','items':{'type':'object','properties':{
            'index':{'type':'integer'},'role':{'type':'string','enum':['reference','keyframe']}},
            'required':['index','role'],'additionalProperties':False}}},
        'required':['end','prompt','time_basis','continuity','lip_sync','images'],'additionalProperties':False}}},
    'required':['style','shots'],'additionalProperties':False}


def validate(value,duration,refs,request,*,audio_start=0,clip_budget=None):
    if not isinstance(value,dict) or set(value)!= {'style','shots'} or not isinstance(value['style'],str) or not value['style'].strip() or len(value['style'])>1200:
        raise ValueError('Stile dello storyboard non valido.')
    shots=value['shots'];images=[r for r in refs if r['mime'].startswith('image/')]
    if not isinstance(shots,list) or not 1<=len(shots)<=MAX_SHOTS:raise ValueError('Storyboard: da 1 a 160 inquadrature.')
    if clip_budget is None and requested(request)[0] is not None:clip_budget=contract(request,duration,audio_start=audio_start)
    if clip_budget and len(shots)!=clip_budget['count']:
        raise ValueError(f"Storyboard: servono esattamente {clip_budget['count']} clip da generare; ricevuti {len(shots)}. Raggruppa gli stacchi interni nei prompt, senza aggiungere generazioni.")
    target=math.ceil(duration*24);cursor=0;scenes=[]
    for index,shot in enumerate(shots):
        if not isinstance(shot,dict) or set(shot)-{'time_basis'}!= {'end','prompt','continuity','lip_sync','images'}:raise ValueError('Inquadratura storyboard non valida.')
        end=shot['end']
        if type(end) not in (int,float) or not math.isfinite(end) or not 0<end<=duration+1/24:raise ValueError('Tempo finale storyboard fuori intervallo.')
        if index==len(shots)-1:
            if abs(end-duration)>1/24:raise ValueError('Lo storyboard deve coprire tutta la durata richiesta.')
            frame=target
        else:frame=round(end*24)
        if clip_budget and clip_budget['end_frames'] and frame!=clip_budget['end_frames'][index]:
            raise ValueError(f"Il clip {index+1} deve terminare a {clip_budget['end_frames'][index]/24:g} secondi, come richiesto.")
        frames=frame-cursor
        if not 1<=frames<=360 or (frames<24 and index!=len(shots)-1):raise ValueError('Ogni inquadratura deve durare da 1 a 15 secondi, salvo la coda finale.')
        if shot['continuity'] not in ('cut','continue') or type(shot['lip_sync']) is not bool:raise ValueError('Stacco o lip-sync storyboard non valido.')
        if not isinstance(shot['prompt'],str) or not shot['prompt'].strip() or len(shot['prompt'])>2400:raise ValueError('Descrizione dell’inquadratura non valida.')
        chosen=shot['images']
        if not isinstance(chosen,list) or len(chosen)>9:raise ValueError('Riferimenti dell’inquadratura non validi.')
        seen=set()
        for item in chosen:
            if not isinstance(item,dict) or set(item)!= {'index','role'} or type(item['index']) is not int or not 1<=item['index']<=len(images) or item['role'] not in ('reference','keyframe') or item['index'] in seen:
                raise ValueError('Lo storyboard cita un’immagine inesistente o ripetuta.')
            seen.add(item['index'])
        if sum(x['role']=='keyframe' for x in chosen)>1:raise ValueError('Scegli un solo frame iniziale per inquadratura.')
        labels=[int(n) for n in re.findall(r'<Picture\s+(\d+)>',shot['prompt']+' '+value['style'],re.I)]
        if any(n not in seen for n in labels):raise ValueError('La descrizione cita un’immagine non selezionata per questa inquadratura.')
        from .video_timing import localize
        clip={'index':index,'start':cursor/24,'duration':frames/24,'frames':frames,'end':frame/24}
        description=localize(shot['prompt'].strip(),clip,basis=shot.get('time_basis','auto'),audio_start=audio_start)
        scenes.append(clip|{'prompt':description,'time_basis':'local','images':chosen,'continuity':shot['continuity'],'lip_sync':shot['lip_sync']})
        cursor=frame
    if cursor!=target:raise ValueError('Storyboard incompleto.')
    if any(line not in '\n'.join(s['prompt'] for s in scenes) for line in spoken_lines(request)):
        raise ValueError('Lo storyboard deve conservare le parole esatte del canto/dialogo nelle inquadrature appropriate.')
    duplicate=repeated_scene([],[s['prompt'] for s in scenes],request)
    if duplicate:raise ValueError(f'L’inquadratura {duplicate} copia un’azione già descritta: sviluppa lo storyboard senza ripetere l’apertura.')
    return {'style':value['style'].strip(),'shots':scenes}


def build(engine,plan,refs,settings,prompt,cancel,stage,log):
    duration=settings['_video_duration'];clip_budget=contract(prompt,duration,audio_start=settings.get('_video_audio_start',0))
    # With the minimum number of clips there is no useful timing choice for
    # the LLM: use 15-second windows and the exact decoded audio tail.
    ends=clip_budget['end_frames']
    if not ends and clip_budget['count']==clip_budget['minimum']:
        ends=[min((i+1)*360,math.ceil(duration*24)) for i in range(clip_budget['count'])]
        clip_budget=clip_budget|{'end_frames':ends}
    stage(f"Storyboard · {clip_budget['count']} clip da generare · stacchi interni al prompt")
    llm=engine.require_model(settings['chat_model'],'chat');engine.start_llama(llm,settings,log,cancel,stage=stage)
    budget=min(settings['context']//2,settings['video_prompt_max_tokens'])
    context={'request':prompt,'duration':duration,'audio_source_start':settings.get('_video_audio_start',0),
             'generation_clips':clip_budget['count'],'minimum_generation_clips':clip_budget['minimum'],
             'required_clip_ends':[frame/24 for frame in clip_budget['end_frames']],
             'images':[{'index':i,'name':r['name'],'role':next((x['role'] for x in plan.get('images',[]) if x['index']==i),'reference')} for i,r in enumerate([r for r in refs if r['mime'].startswith('image/')],1)]}
    instructions='''Direct a music-video storyboard covering the entire requested duration.
Return JSON style, shots. Each shots item is ONE GPU GENERATION CLIP, not one
visual shot or cut. Return EXACTLY generation_clips items. Never multiply GPU
calls for camera cuts or action changes. style contains only stable cast, wardrobe and visual aesthetic,
not a replay of the opening, and no Picture labels. Each shot has end (seconds relative
to this video), prompt (English visible action/camera), continuity (cut or continue),
lip_sync, images [{index,role}]. Start is the preceding end, starting at zero.
Generation clips last 1–15 seconds, the last may have a shorter tail. End the last
exactly at duration. If required_clip_ends is nonempty, use those exact ends.
Without explicit clip timings, use near-even durations across generation_clips,
leaving enough time for the complete requested ending. Internal visual cuts can
occur at any appropriate local time inside a clip; keep every requested action.
In each prompt use [Shot 1] without a timestamp for the first visual shot, then
[Shot 2] At MM:SS.mmm, [Shot 3] At MM:SS.mmm, etc. for internal cuts. Restart
shot numbering in each clip. A clip with one uninterrupted shot needs no extra cuts.
Each shot also declares time_basis: prefer local for narrative timestamps within
its prompt, from 00:00 to that shot's duration. Subtract the shot start from global
film times, or audio_source_start + shot start from SOURCE audio times. Declare
video or source only if deliberately keeping those coordinates. Never mix bases.
end always remains a global FILM time, regardless of time_basis in the prompt.
Honor every user scene, order, timing, cast and image assignment. Use global image
indices from the supplied inventory. Reference preserves identity/style; keyframe
uses that image as the first frame. Only select images relevant to each shot.
The inventory role is authoritative: never promote a reference character sheet,
face, costume or location into a keyframe. A reference guides identity/style,
not the opening composition or output aspect ratio. Explicitly associate each
selected Picture label with its intended character in that clip's prompt.
A clip's continuity=cut starts it without the preceding last frame; continuity=continue
is only for continuation across GENERATION CLIP boundaries. Internal cuts stay
inside that clip's prompt and do not create new shots-array items. Use cut at
clip boundaries by default for montage; do not invent extra visual cuts against
the request. A 15-second clip may contain multiple shorter visual shots. Respect
explicit wardrobe changes and the reference chosen for each scene; stable identity
does not mean every scene must use the same location, costume or composition.
Split actions longer than 15s across the allocated generation clips, without
restarting the action. Select all references needed by the internal visual shots
of that clip. Only a clip's starting image can be role=keyframe; images needed
after an internal cut are role=reference and must be mentioned in the prompt.
Keep prompts concise and concrete. Preserve exact user-supplied sung/spoken words
and their language in the matching shot. Do not invent unheard lyrics, singers,
beat timings or transcriptions. Music is one continuous original track under every
shot, never a fresh song or loop per shot. lip_sync=true only for visible performance
requested by the user; other shots keep the music without forcing singing.
Image labels, if used, must refer to images selected in that shot. No Audio labels
are needed in your prompts. Fill creative gaps only where the user left them open.
Before returning check EXACT generation clip count, full time coverage, internal
cut clocks, scene progression, complete ending and image assignments.'''
    schema=copy.deepcopy(SCHEMA)
    schema['properties']['shots'].update(minItems=clip_budget['count'],maxItems=clip_budget['count'])
    tuning=settings|{'max_tokens':budget,'think_level':'off'}
    messages=[{'role':'system','content':instructions+f'\nTotal output budget: {budget} tokens. Use concise shot descriptions.'},
              {'role':'user','content':json.dumps(context,ensure_ascii=False)}]
    for attempt in range(2):
        if cancel.is_set():raise Cancelled()
        raw='{}'
        stage('Assistant · regia dello storyboard'+(' · correzione' if attempt else ''))
        try:
            raw,finish=engine.completion(messages,tuning,cancel,on_text=lambda _:None,schema=schema)
            if finish=='length':raise StructuredCompletionError('Output storyboard incompleto: aumenta i token Assistant video.')
            value=json.loads(raw)
            # Keep directing actions with the LLM, but never let it redefine
            # the already allocated audio windows or attachment semantics.
            if isinstance(value,dict) and isinstance(value.get('shots'),list):
                authoritative={x['index']:x['role'] for x in plan.get('images',[])}
                for i,shot in enumerate(value['shots']):
                    if not isinstance(shot,dict):continue
                    if ends and len(value['shots'])==len(ends) and type(shot.get('end')) in (int,float) and math.isfinite(shot['end']):
                        shot['end']=ends[i]/24
                    if isinstance(shot.get('images'),list):
                        for image in shot['images']:
                            if isinstance(image,dict) and authoritative.get(image.get('index'))=='reference' and image.get('role')=='keyframe':
                                image['role']='reference'
            result=validate(value,duration,refs,prompt,audio_start=settings.get('_video_audio_start',0),clip_budget=clip_budget)
            result['clip_budget']=clip_budget
            stage(f'Storyboard confermato · {len(result["shots"])} generazioni · stacchi interni · traccia continua')
            return result
        except (ValueError,TypeError,EmptyCompletion,StructuredCompletionError) as exc:
            if attempt:raise ValueError('Assistant: storyboard non valido dopo la correzione. '+str(exc)+' Nessun video è stato avviato.') from exc
            messages.extend([{'role':'assistant','content':raw},
                             {'role':'user','content':'Correct the storyboard before generation: '+str(exc)+'. Return the complete JSON, following the original request. Clip ends are GLOBAL FILM seconds, independent of local action clocks. Required ends: '+json.dumps([frame/24 for frame in ends])+'.'}])


def local_plan(storyboard,shot,global_plan,refs,soundtrack_index,audio_start):
    images=[r for r in refs if r['mime'].startswith('image/')];audios=[r for r in refs if r['mime'].startswith('audio/')]
    chosen=shot['images'];mapping={entry['index']:i for i,entry in enumerate(chosen,1)}
    def remap(match):
        index=int(match[1])
        if index not in mapping:raise ValueError('Immagine non selezionata nell’inquadratura.')
        return f'<Picture {mapping[index]}>'
    from .video_timing import localize
    description=localize(re.sub(r'<Picture\s+(\d+)>',remap,shot['prompt'],flags=re.I),shot,basis=shot.get('time_basis','auto'),audio_start=audio_start)
    keep='; '.join(f'<Picture {i}> fully_preserved identity/style' for i in range(1,len(chosen)+1))
    start=audio_start+shot['start']
    prompt=f'subject_definitions: {storyboard["style"]}\nsummary: {description}\nretention_analysis: {keep}; <Audio {soundtrack_index}> fully_copy original audio.\ndetailed_description: {description}\noverall_soundscape: Original <Audio {soundtrack_index}> from source seconds {start:g} to {start+shot["duration"]:g}, unchanged.\nnon_diegetic_music: Preserve the original supplied track continuously; no replacement music or extra dialogue.'
    plan={'prompt':prompt,'images':[{'index':i,'role':entry['role'],'seconds':0} for i,entry in enumerate(chosen,1)],
          'audios':[entry|({'start':start,'role':'lipsync' if shot['lip_sync'] else 'reuse'} if entry['index']==soundtrack_index else {'role':'reference'}) for entry in global_plan['audios']]}
    selected=[images[entry['index']-1] for entry in chosen]+audios
    return validate_plan(plan,selected,shot['duration']),selected

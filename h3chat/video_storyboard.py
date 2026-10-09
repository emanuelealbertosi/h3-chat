"""Plan ordered, timed shots and select only their actual image references."""
import json
import math
import re
from .downloads import Cancelled
from .remote_llm import EmptyCompletion, StructuredCompletionError
from .video_options import validate_plan
from .video_request import repeated_scene, spoken_lines

MAX_SHOTS=160
SCHEMA={'type':'object','properties':{
    'style':{'type':'string','maxLength':1200},
    'shots':{'type':'array','minItems':1,'maxItems':MAX_SHOTS,'items':{'type':'object','properties':{
        'end':{'type':'number'},'prompt':{'type':'string','maxLength':2400},
        'continuity':{'type':'string','enum':['cut','continue']},'lip_sync':{'type':'boolean'},
        'images':{'type':'array','items':{'type':'object','properties':{
            'index':{'type':'integer'},'role':{'type':'string','enum':['reference','keyframe']}},
            'required':['index','role'],'additionalProperties':False}}},
        'required':['end','prompt','continuity','lip_sync','images'],'additionalProperties':False}}},
    'required':['style','shots'],'additionalProperties':False}


def validate(value,duration,refs,request):
    if not isinstance(value,dict) or set(value)!= {'style','shots'} or not isinstance(value['style'],str) or not value['style'].strip() or len(value['style'])>1200:
        raise ValueError('Stile dello storyboard non valido.')
    shots=value['shots'];images=[r for r in refs if r['mime'].startswith('image/')]
    if not isinstance(shots,list) or not 1<=len(shots)<=MAX_SHOTS:raise ValueError('Storyboard: da 1 a 160 inquadrature.')
    target=math.ceil(duration*24);cursor=0;scenes=[]
    for index,shot in enumerate(shots):
        if not isinstance(shot,dict) or set(shot)!= {'end','prompt','continuity','lip_sync','images'}:raise ValueError('Inquadratura storyboard non valida.')
        end=shot['end']
        if type(end) not in (int,float) or not math.isfinite(end) or not 0<end<=duration+1/24:raise ValueError('Tempo finale storyboard fuori intervallo.')
        if index==len(shots)-1:
            if abs(end-duration)>1/24:raise ValueError('Lo storyboard deve coprire tutta la durata richiesta.')
            frame=target
        else:frame=round(end*24)
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
        scenes.append({'index':index,'start':cursor/24,'duration':frames/24,'frames':frames,'end':frame/24,
                       'prompt':shot['prompt'].strip(),'images':chosen,'continuity':shot['continuity'],'lip_sync':shot['lip_sync']})
        cursor=frame
    if cursor!=target:raise ValueError('Storyboard incompleto.')
    if any(line not in '\n'.join(s['prompt'] for s in scenes) for line in spoken_lines(request)):
        raise ValueError('Lo storyboard deve conservare le parole esatte del canto/dialogo nelle inquadrature appropriate.')
    duplicate=repeated_scene([],[s['prompt'] for s in scenes],request)
    if duplicate:raise ValueError(f'L’inquadratura {duplicate} copia un’azione già descritta: sviluppa lo storyboard senza ripetere l’apertura.')
    return {'style':value['style'].strip(),'shots':scenes}


def build(engine,plan,refs,settings,prompt,cancel,stage,log):
    llm=engine.require_model(settings['chat_model'],'chat');engine.start_llama(llm,settings,log,cancel,stage=stage)
    duration=settings['_video_duration'];budget=min(settings['context']//2,settings['video_prompt_max_tokens'])
    context={'request':prompt,'duration':duration,'audio_source_start':settings.get('_video_audio_start',0),
             'images':[{'index':i,'name':r['name']} for i,r in enumerate([r for r in refs if r['mime'].startswith('image/')],1)]}
    instructions='''Direct a music-video storyboard covering the entire requested duration.
Return JSON style, shots. style contains only stable cast, wardrobe and visual aesthetic,
not a replay of the opening, and no Picture labels. Each shot has end (seconds relative
to this video), prompt (English visible action/camera), continuity (cut or continue),
lip_sync, images [{index,role}]. Start is the preceding end, starting at zero.
Shots last 1–15 seconds, the last may have a shorter tail. End the last exactly at duration.
Honor every user scene, order, timing, cast and image assignment. Use global image
indices from the supplied inventory. Reference preserves identity/style; keyframe
uses that image as the first frame. Only select images relevant to each shot.
A cut is a true new shot/location/framing and does not force the preceding last frame.
continue is only for an explicit continuation of the same action/in-camera movement.
Use cuts by default for montage; do not create arbitrary extra cuts against the request.
Without requested shot timings, favor varied shots of roughly 4–8 seconds for a music
montage, rather than a succession of identical 15-second introductions. Respect
explicit wardrobe changes and the reference chosen for each scene; stable identity
does not mean every scene must use the same location, costume or composition.
Split actions longer than 15s into continued shots, without restarting the action.
Keep prompts concise and concrete. Preserve exact user-supplied sung/spoken words
and their language in the matching shot. Do not invent unheard lyrics, singers,
beat timings or transcriptions. Music is one continuous original track under every
shot, never a fresh song or loop per shot. lip_sync=true only for visible performance
requested by the user; other shots keep the music without forcing singing.
Image labels, if used, must refer to images selected in that shot. No Audio labels
are needed in your prompts. Fill creative gaps only where the user left them open.
Before returning check full time coverage, scene progression and image assignments.'''
    tuning=settings|{'max_tokens':budget,'think_level':'off'}
    messages=[{'role':'system','content':instructions+f'\nTotal output budget: {budget} tokens. Use concise shot descriptions.'},
              {'role':'user','content':json.dumps(context,ensure_ascii=False)}]
    for attempt in range(2):
        if cancel.is_set():raise Cancelled()
        stage('Assistant · regia dello storyboard'+(' · correzione' if attempt else ''))
        try:
            raw,finish=engine.completion(messages,tuning,cancel,on_text=lambda _:None,schema=SCHEMA)
            if finish=='length':raise StructuredCompletionError('Output storyboard incompleto: aumenta i token Assistant video.')
            result=validate(json.loads(raw),duration,refs,prompt)
            stage(f'Storyboard · {len(result["shots"])} inquadrature · traccia continua')
            return result
        except (ValueError,TypeError,EmptyCompletion,StructuredCompletionError) as exc:
            if attempt:raise ValueError('Assistant: storyboard non valido dopo la correzione. '+str(exc)+' Nessun video è stato avviato.') from exc
            messages.append({'role':'user','content':'Correct the storyboard before generation: '+str(exc)+'. Return the complete JSON, following the original request.'})


def local_plan(storyboard,shot,global_plan,refs,soundtrack_index,audio_start):
    images=[r for r in refs if r['mime'].startswith('image/')];audios=[r for r in refs if r['mime'].startswith('audio/')]
    chosen=shot['images'];mapping={entry['index']:i for i,entry in enumerate(chosen,1)}
    def remap(match):
        index=int(match[1])
        if index not in mapping:raise ValueError('Immagine non selezionata nell’inquadratura.')
        return f'<Picture {mapping[index]}>'
    description=re.sub(r'<Picture\s+(\d+)>',remap,shot['prompt'],flags=re.I)
    keep='; '.join(f'<Picture {i}> fully_preserved identity/style' for i in range(1,len(chosen)+1))
    start=audio_start+shot['start']
    prompt=f'subject_definitions: {storyboard["style"]}\nsummary: {description}\nretention_analysis: {keep}; <Audio {soundtrack_index}> fully_copy original audio.\ndetailed_description: {description}\noverall_soundscape: Original <Audio {soundtrack_index}> from source seconds {start:g} to {start+shot["duration"]:g}, unchanged.\nnon_diegetic_music: Preserve the original supplied track continuously; no replacement music or extra dialogue.'
    plan={'prompt':prompt,'images':[{'index':i,'role':entry['role'],'seconds':0} for i,entry in enumerate(chosen,1)],
          'audios':[entry|({'start':start,'role':'lipsync' if shot['lip_sync'] else 'reuse'} if entry['index']==soundtrack_index else {'role':'reference'}) for entry in global_plan['audios']]}
    selected=[images[entry['index']-1] for entry in chosen]+audios
    return validate_plan(plan,selected,shot['duration']),selected

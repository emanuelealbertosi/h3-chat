"""Video routing and prompt preparation, with attachment identities kept stable."""
import re
from .video_options import validate_plan

BRIEF = '''Prepare a MiniMax H3 video plan. Return JSON prompt, images, audios.
Each image has index (one-based Picture number), role (reference or keyframe), seconds.
Each audio has index (one-based Audio number), role (reference, lipsync or reuse), start (source offset in seconds).
Use EVERY provided attachment exactly once, in its original numbered order. Never invent assets.
A start/first frame is keyframe at 0, intermediate frames use requested seconds,
end frame uses the clip duration. Images without timing are identity/style references;
a single image to animate is a keyframe at 0. Audio reference transfers sound/voice style;
lipsync preserves original audio AND conditions visible mouth motion; reuse preserves audio.
Choose lipsync for singing/talking along the supplied soundtrack. Do not transcribe unheard audio.
For lipsync/reuse, sound sections must preserve the supplied Audio track exactly;
never infer its genre, tempo, instruments, lyrics or beat timestamps from its filename.
Describe requested visible instruments separately from the unheard soundtrack.
Prompt is English narrative, but preserve exact user dialogue/lyrics and their language.
Keep speaker IDs (S1), (S2) stable and wrap dialogue in <d>[language] words</d>.
Do not invent image details. Preserve visible identity, composition, wardrobe and lighting.
The original user request is authoritative: preserve explicit actions, sequence, timing,
cast, costumes, instruments, visual style and framing. Fill only unspecified creative gaps.
Keep requested canonical appearances/costumes; do not guess unsupported costume colors
or redesign characters. Assign unspecified roles consistently, without overriding user roles.
Turn broad direction into concrete, filmable action: who does what, where, how the camera
observes it, and what changes by the end. One clear main event fits the available duration;
avoid vague lists such as "playing instruments or posing dynamically".
Express requested tone through visible behavior: a parody needs an appropriate visual gag
or comic contrast, rather than just the word "parody". Do not add comedy to a serious request.
Maintain a coherent visual identity while developing the action; continuity does not mean
repeating the same scene or freezing the location when the user asks for scene changes.
Use [Shot 1] without time; only add further shots when asked, with increasing cut times within duration.
For text-only/start/keyframe video use integrated_multimodal_description, overall_soundscape,
non_diegetic_music as labeled sections. Identify a keyframe only when an actual image
is assigned that role: use its existing Picture label, requested time and shot.
With no image attachments, images must be empty. Never write a Picture label or claim
a supplied start frame exists. Generate original visuals from the textual description;
an audio-only music video does not require an image attachment.
For reference images/audio use six labeled sections: subject_definitions, summary,
retention_analysis, detailed_description, overall_soundscape, non_diegetic_music.
Map reusable <Subject N> identities to an existing Picture label only when an image
actually supplies that subject; otherwise define the subject in words. Map sound to
existing Audio labels. Do not invent labels for internal memory or future generated frames.
Specify fully_preserved/partially_preserved/attribute_transfer/weak_reference for visuals;
fully_copy/partially_copy/reference/weak_reference for sound. State exact audio reuse for lipsync.
All labels must agree with attachment order. Respect duration, avoid impossible action density.
You are preparing instructions, not claiming to have generated a video.'''

SCENE_DIRECTION = '''Direct the entire sequence using total_scenes and each clip's global index.
Honor the original request over unsupported details introduced by the preliminary plan.
Follow an explicit user storyboard, order, pacing and requested repetitions; do not replace
them with your own formula. If no storyboard is supplied, develop a clear progression.
When alternating requested threads/locations, maintain that order across batch boundaries.
Each return must advance the action with a different concrete event, interaction or outcome;
changing only the opening sentence or camera adjective is not a new scene. Keep stable cast
and style anchors concise, rather than repeating whole descriptions from opening/previous.
Give each clip a feasible main action, clear setting/framing and ending state that leads into
the next beat. Vary framing and camera movement where suitable; do not invent extra cuts
against the requested shot constraints. Preserve identities and wardrobe across location
changes. Lip-sync performance clips need a clearly visible singer's mouth, not only distant
crowd shots. Do not force singing into action-only clips unless requested.
Make tone observable in the action, including concrete comic beats for a requested parody.
Place development in middle clips and resolution only in the final clip; do not repeatedly
restart the introduction or add an early finale. Do not invent timings of unheard beats/lyrics.
Before returning, check every requested clip against request, previous and opening for
unintended repeated action, omitted constraints and unsupported audio/costume details.
Return only the required concise scene prompts; no commentary, analysis or extra JSON keys.'''

PLAN_SCHEMA={'type':'object','properties':{
 'prompt':{'type':'string'},
 'images':{'type':'array','items':{'type':'object','properties':{'index':{'type':'integer'},'role':{'type':'string','enum':['reference','keyframe']},'seconds':{'type':'number'}},'required':['index','role','seconds'],'additionalProperties':False}},
 'audios':{'type':'array','items':{'type':'object','properties':{'index':{'type':'integer'},'role':{'type':'string','enum':['reference','lipsync','reuse']},'start':{'type':'number'}},'required':['index','role','start'],'additionalProperties':False}}},'required':['prompt','images','audios'],'additionalProperties':False}

def attachment_instructions(images,audios):
    """Enumerate the actual user assets; generated memory is not an attachment."""
    pictures=[f'<Picture {x["index"]}>' for x in images]
    sounds=[f'<Audio {x["index"]}>' for x in audios]
    return ('\nAllowed Picture labels: '+(', '.join(pictures) if pictures else 'NONE. No image was attached: never cite Picture labels or a supplied visual/keyframe')+
            '.\nAllowed Audio labels: '+(', '.join(sounds) if sounds else 'NONE. No audio was attached: never cite Audio labels')+
            '. These lists are exhaustive. Never invent other indices or label internal visual memory as a user attachment.')

def route(history,settings):
    text=history[-1]['content'].strip()
    if settings.get('_video'):return {'intent':'video','prompt':text,'selection':'explicit'}
    if settings.get('_music') or settings.get('_image_model') or not settings.get('video_auto',True):return None
    opening=re.sub(r'^(?:(?:per favore[, ]*|puoi\s+|potresti\s+|vorrei\s+|mi piacerebbe\s+|please\s+|can you\s+))+','',text.casefold())
    if re.match(r'^(?:anima(?:re)?|animate)\b',opening) or re.match(r'^(?:crea(?:mi|re)?|genera(?:mi|re)?|realizza(?:mi|re)?|fammi|fai|create|generate|make)\s+(?:(?:un|una|uno|il|lo|la|a|an|the)\s+)?(?:video|videoclip|filmato|clip|animazione|animation|music video|lip[ -]?sync)\b',opening):
        if not re.search(r'\b(?:codice|tutorial|prompt|come fare|how to)\b',opening[:100]):return {'intent':'video','prompt':text,'selection':'auto'}
    return None

def direct_plan(prompt,refs,duration):
    """Assistant Off: deterministic labels, without rewriting the user's prompt."""
    pictures=[x for x in refs if x['mime'].startswith('image/')]
    audios=[x for x in refs if x['mime'].startswith('audio/')]
    images=[]
    for index in range(1,len(pictures)+1):
        match=re.search(rf'(?:immagine|image|picture|foto)\s*{index}\s*(?:a|at|@)\s*(\d+(?:[.,]\d+)?)\s*(?:s|sec|secondi|seconds)\b',prompt,re.I)
        if match:role,seconds='keyframe',float(match[1].replace(',','.'))
        elif index==1 and (len(pictures)==1 and not re.search(r'\b(reference|riferimento)\b',prompt,re.I) or re.search(r'\b(start frame|first frame|frame iniziale|primo fotogramma)\b',prompt,re.I)):role,seconds='keyframe',0
        else:role,seconds='reference',0
        images.append({'index':index,'role':role,'seconds':seconds})
    audio_role='lipsync' if re.search(r'lip[ -]?sync|sincronizz\w*\s+(?:labial|labbra)|canta|singing',prompt,re.I) else 'reuse' if re.search(r'audio originale|original audio|conserva.*audio',prompt,re.I) else 'reference'
    plan={'prompt':prompt,'images':images,'audios':[{'index':i,'role':audio_role if i==1 else 'reference','start':0} for i in range(1,len(audios)+1)]}
    return validate_plan(plan,refs,duration)

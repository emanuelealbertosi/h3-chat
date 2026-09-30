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
Prompt is English narrative, but preserve exact user dialogue/lyrics and their language.
Keep speaker IDs (S1), (S2) stable and wrap dialogue in <d>[language] words</d>.
Do not invent image details. Preserve visible identity, composition, wardrobe and lighting.
Use [Shot 1] without time; only add further shots when asked, with increasing cut times within duration.
For text-only/start/keyframe video use integrated_multimodal_description, overall_soundscape,
non_diegetic_music as labeled sections. Explicitly identify keyframes:
For the target video, at 0.00 seconds into the target video, <Picture 1> (from [Shot 1]) is fully referenced.
Use analogous sentences at other requested keyframe times.
For reference images/audio use six labeled sections: subject_definitions, summary,
retention_analysis, detailed_description, overall_soundscape, non_diegetic_music.
Map reusable <Subject N> identities to <Picture N> and sound to <Audio N>.
Specify fully_preserved/partially_preserved/attribute_transfer/weak_reference for visuals;
fully_copy/partially_copy/reference/weak_reference for sound. State exact audio reuse for lipsync.
All labels must agree with attachment order. Respect duration, avoid impossible action density.
You are preparing instructions, not claiming to have generated a video.'''

PLAN_SCHEMA={'type':'object','properties':{
 'prompt':{'type':'string'},
 'images':{'type':'array','items':{'type':'object','properties':{'index':{'type':'integer'},'role':{'type':'string','enum':['reference','keyframe']},'seconds':{'type':'number'}},'required':['index','role','seconds'],'additionalProperties':False}},
 'audios':{'type':'array','items':{'type':'object','properties':{'index':{'type':'integer'},'role':{'type':'string','enum':['reference','lipsync','reuse']},'start':{'type':'number'}},'required':['index','role','start'],'additionalProperties':False}}},'required':['prompt','images','audios'],'additionalProperties':False}

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

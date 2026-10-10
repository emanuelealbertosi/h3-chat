"""Choose a soundtrack outside generated Python; never ask an LLM to mux it."""
import re
from .downloads import safe_join


def excludes_soundtrack(prompt):
    # Silence assigned to a character is not silence assigned to the output.
    # Likewise, image references and bans on *additional* sound keep the track.
    media=r'(?:video|film|filmato|movie|animation|animazione|output|render)'
    silence=r'(?:silent|mute|muted|mut[oa])'
    qualifiers=r'(?:(?:must|should|be|is|completely|entirely|deve|essere|sia|completamente|del\s+tutto)\s+)*'
    return bool(re.search(
        r'\b(?:senza\s+audio|no\s+audio|without\s+audio)\b(?!\s+(?:aggiuntiv\w*|extra|additional|new|changes|modific\w*)\b)'
        r'|\b'+silence+r'\s+'+media+r'\b'
        r'|\b'+media+r'\s+'+qualifiers+silence+r'\b'
        r'|^\s*(?:'+silence+r'|solo\s+(?:come\s+)?riferimento)\s*[.!]?\s*$'
        r'|\b(?:audio|traccia|soundtrack)\s+(?:solo\s+)?(?:come\s+)?(?:reference|riferimento)\b'
        r'|\b(?:audio|traccia|soundtrack)\s+(?:as\s+)?reference\s+only\b',prompt,re.I|re.M))


def select(prompt, media, history=()):
    if excludes_soundtrack(prompt):return None
    audios=[m for m in media if m.get('mime','').startswith('audio/')]
    if not audios and re.search(r'\b(?:audio|traccia|soundtrack|voce|musica|canzone|song|colonna sonora)\b',prompt,re.I):
        audios=next(([m for m in row.get('media',[]) if m.get('mime','').startswith('audio/')] for row in reversed(history) if any(m.get('mime','').startswith('audio/') for m in row.get('media',[]))),[])
    if not audios:return None
    match=re.search(r'\b(?:audio|traccia|track)\s*(\d+)\b',prompt,re.I)
    if match:
        index=int(match[1])-1
        if not 0<=index<len(audios):raise ValueError('La traccia audio indicata non è disponibile.')
        return audios[index]
    named=[m for m in audios if m.get('name','').casefold() in prompt.casefold()]
    if len(named)==1:return named[0]
    if len(audios)>1:raise ValueError('Sono presenti più tracce: indica “audio 1” o “audio 2” come colonna sonora.')
    return audios[0]


def probe(engine,data,item,cancel,stage,log):
    return engine.tool_call('media-compose-worker.py',{'op':'probe','path':str(safe_join(data,item['path']))},cancel,stage,log,timeout=300)


def compose(engine,videos,audio,output,cancel,stage,log,*,retime=False,durations=None,audio_start=0,audio_duration=None):
    stage('Montaggio · applicazione della traccia audio originale' if audio else 'Montaggio · sequenza delle slide')
    return engine.tool_call('media-compose-worker.py',{'op':'compose','videos':[str(p) for p in videos],
        'audio':str(audio) if audio else None,'output':str(output),'retime':retime,**({'durations':durations} if durations is not None else {}),
        **({'audio_start':audio_start,'audio_duration':audio_duration} if audio_start or audio_duration is not None else {})},cancel,stage,log,timeout=3600)

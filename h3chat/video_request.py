"""Explicit soundtrack windows take priority over automatic full-track videos."""
import math
import re
from .video_options import prompt_duration


def audio_window(prompt,source_duration):
    if type(source_duration) not in (int,float) or not math.isfinite(source_duration) or source_duration<=0:
        raise ValueError('Durata della traccia audio non valida.')
    duration=prompt_duration(prompt,has_audio=True);start=0;end=None
    # Scope ranges to the overall timeline or audio instructions. Shot timings
    # (00:06–00:09, etc.) are not the requested soundtrack window.
    clock=r'\d{1,2}:\d{2}(?::\d{2})?(?:[.,]\d+)?'
    ranges=[]
    for line in prompt.splitlines():
        if not re.search(r'\b(?:absolute\s+timeline|timeline\s+assoluta|timeline|audio|soundtrack|traccia|segmento|segment)\b',line,re.I):continue
        match=re.search(rf'({clock})\s*(?:[–—-]|to|a)\s*({clock})',line,re.I)
        if match:
            def seconds(value):
                parts=[float(p.replace(',','.')) for p in value.split(':')]
                if any(p>=60 for p in parts[1:]):raise ValueError('Intervallo audio: minuti e secondi devono essere inferiori a 60.')
                return sum(p*60**i for i,p in enumerate(reversed(parts)))
            ranges.append((seconds(match[1]),seconds(match[2])))
    if ranges:
        start,end=ranges[0]
        if any(abs(a-start)>1e-6 or abs(b-end)>1e-6 for a,b in ranges[1:]):
            raise ValueError('Sono indicati intervalli audio diversi: specifica un solo segmento per questo video.')
        if end<=start:raise ValueError('Il segmento audio deve terminare dopo il suo inizio.')
        if duration is not None and abs(duration-(end-start))>1/24:
            raise ValueError('Durata video e intervallo audio non coincidono: correggi il prompt.')
        duration=end-start
    if duration is None:duration=source_duration-start
    if not 0<duration<=600:raise ValueError('Video con audio: durata massima 10 minuti.')
    if start>=source_duration or start+duration>source_duration+1/192000:
        raise ValueError(f'La traccia audio non copre il segmento richiesto: {start:g}–{start+duration:g} secondi.')
    return {'start':start,'duration':duration,'source_duration':source_duration,'explicit':end is not None or prompt_duration(prompt,has_audio=True) is not None}


def repetition_allowed(prompt):
    prompt=re.sub(r"\b(?:do not|don't|never|avoid|no|non|senza|evita)\s+(?:ripeti\w*|ripet\w*|repeat\w*|loop\w*)\b",'',prompt,flags=re.I)
    return bool(re.search(r'\b(?:ripeti|ripetere|ripetizione|ripetizioni|repeat|repeated|loop|ciclo)\b',prompt,re.I))


def repeated_scene(scripts,candidates,prompt):
    """Catch copied scene bodies, not shared cast/style or deliberate repeats."""
    if repetition_allowed(prompt):return None
    def key(text):
        text=re.sub(r'\b(?:clip|scene|scena)\s*\d+\b','',text,flags=re.I)
        return ' '.join(re.findall(r'\w+',text.casefold()))
    previous=[key(s) for s in scripts]
    for index,text in enumerate(candidates):
        normalized=key(text)
        if len(normalized.split())>=12 and normalized in previous:return len(scripts)+index+1
        previous.append(normalized)
    return None


def spoken_lines(prompt):
    """Verbatim quoted speech following explicit vocal/dialogue directions."""
    result=[]
    for match in re.finditer(r'["“]([^"”\n]{2,400})["”]',prompt):
        context=prompt[max(0,match.start()-220):match.start()]
        if re.search(r'\b(?:vocal|vocals|lyric|lyrics|dialogue|dialogo|battuta|canta|canto|dice|sings|says)\b',context,re.I):
            result.append(match[1])
    return result

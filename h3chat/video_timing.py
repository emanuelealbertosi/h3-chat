"""Convert narrative clocks to clip-local time without moving source audio."""
import re

CLOCK = r'\d{1,3}:\d{2}(?::\d{2})?(?:[.,]\d+)?'
TOKEN = re.compile(rf'(?<![\w:]){CLOCK}(?!\d|[.:,]\d)')
RANGE = re.compile(rf'(?<![\w:])(?P<first>{CLOCK})\s*(?:[–—-]|\bto\b|\ba\b)\s*(?P<last>{CLOCK})(?!\d|[.:,]\d)',re.I)
NUMBER = r'\d+(?:[.,]\d+)?'
UNIT = r'(?:seconds?|second[io]|sec|s)\b'
NUM_RANGE = re.compile(rf'(?<![\w:.])(?P<first>{NUMBER})\s*(?:{UNIT})?\s*(?:[–—-]|\bto\b|\ba\b)\s*(?P<last>{NUMBER})\s*{UNIT}',re.I)
POINT = re.compile(rf'\b(?:at|after|until|from|a|al|da|fino a|t\s*=)\s*(?P<value>{NUMBER})\s*(?:seconds|second[io]|sec|s)\b',re.I)
PROTECTED = re.compile(r'<d>.*?</d>|["“][^"”\n]*["”]',re.S)
SECTION = re.compile(r'\b(subject_definitions|summary|retention_analysis|detailed_description|integrated_multimodal_description|overall_soundscape|non_diegetic_music)\s*:',re.I)
TOLERANCE = 1/24 + 1e-6

def seconds(clock):
    if ':' not in clock:return float(clock.replace(',','.'))
    parts = [float(p.replace(',','.')) for p in clock.split(':')]
    if any(p>=60 for p in parts[1:]):raise ValueError('Tempo del video non valido: '+clock)
    return sum(p*60**i for i,p in enumerate(reversed(parts)))

def stamp(value):
    value=max(0,value)
    minutes=int(value//60);tail=round(value-minutes*60,6)
    if tail>=60:minutes+=1;tail=0
    decimal=f'{tail:09.6f}'.rstrip('0').rstrip('.')
    return f'{minutes:02}:{decimal}'

def _mask(text):
    # Lyrics/dialogue are verbatim content, never scheduling instructions.
    return PROTECTED.sub(lambda m:' '*len(m[0]),text)

def _markers(masked):
    marks={m.start():(m.end(),m[0],True) for m in TOKEN.finditer(masked)}
    for match in NUM_RANGE.finditer(masked):
        for name in ('first','last'):
            marks[match.start(name)]=(match.end(name),match[name],False)
    for match in POINT.finditer(masked):
        marks[match.start('value')]=(match.end('value'),match['value'],False)
    return marks

def localize(text,scene,*,basis='auto',audio_start=0):
    """Repair legacy clocks; explicit basis resolves overlapping short clips."""
    if basis not in ('auto','local','video','source'):raise ValueError('Base temporale del video non valida.')
    start=scene['start'];duration=scene['duration'];end=start+duration
    masked=_mask(text);marks=_markers(masked)
    if not marks:return text
    values=[seconds(value) for stop,value,clock in marks.values()]
    offsets={'local':0,'video':start,'source':audio_start+start}
    fits=lambda offset:all(-TOLERANCE<=v-offset<=duration+TOLERANCE for v in values)
    if basis=='auto' or not fits(offsets[basis]):
        # Old checkpoints may already be local, or contain the global clocks
        # seen in earlier Assistant output. Never subtract the offset twice.
        valid=[name for name,offset in offsets.items() if fits(offset)]
        if not valid:raise ValueError(f'Tempi fuori dal clip {start:g}–{end:g} s: usa tempi locali 0–{duration:g} s oppure i tempi globali di questo clip.')
        basis=valid[0]
    offset=offsets[basis]
    for match in [*RANGE.finditer(masked),*NUM_RANGE.finditer(masked)]:
        if seconds(match['last'])<seconds(match['first']):raise ValueError('Intervallo temporale invertito nel prompt video.')
    replacements={position:(stop,stamp(min(duration,max(0,seconds(value)-offset))) if clock else f'{min(duration,max(0,seconds(value)-offset)):.6f}'.rstrip('0').rstrip('.')) for position,(stop,value,clock) in marks.items()}
    for position,(stop,value) in sorted(replacements.items(),reverse=True):text=text[:position]+value+text[stop:]
    return text

def shared_story(text,scene):
    """Scope a timed Assistant-Off story to this clip, retaining cast/labels."""
    masked=_mask(text);sections=list(SECTION.finditer(masked))
    visual=next((m for m in sections if m[1].lower() in ('detailed_description','integrated_multimodal_description')),None)
    first=visual.end() if visual else 0
    stop=next((m.start() for m in sections if m.start()>first),len(text)) if visual else len(text)
    body=text[first:stop];masked_body=_mask(body)
    matches=sorted([*RANGE.finditer(masked_body),*NUM_RANGE.finditer(masked_body)],key=lambda m:m.start())
    if not matches:return localize(text,scene)
    start=scene['start'];end=start+scene['duration']
    actions=[]
    for i,match in enumerate(matches):
        a,b=seconds(match['first']),seconds(match['last'])
        if b<a:raise ValueError('Intervallo temporale invertito nel prompt video.')
        if b<=start or a>=end:continue
        tail=body[match.end():matches[i+1].start() if i+1<len(matches) else len(body)]
        tail=re.sub(r'\s*\[(?:Shot|Scene|Scena|Segment)\s*\d+\]\s*$','',tail,flags=re.I).strip(' :\n')
        actions.append(f'{stamp(max(a,start)-start)}–{stamp(min(b,end)-start)}: {tail}')
    if not actions:raise ValueError(f'Il piano temporale non contiene azioni per il clip {start:g}–{end:g} s.')
    stable=[]
    for i,match in enumerate(sections):
        if match[1].lower() in ('subject_definitions','retention_analysis'):
            stable.append(text[match.start():sections[i+1].start() if i+1<len(sections) else len(text)].strip())
    lead=re.sub(r'\s*\[(?:Shot|Scene|Scena|Segment)\s*\d+\]\s*$','',body[:matches[0].start()],flags=re.I).strip()
    label=visual[1] if visual else 'integrated_multimodal_description'
    return '\n'.join(stable+[f'{label}: '+(' '.join([lead,*actions]) if lead else ' '.join(actions)),
        'overall_soundscape: Preserve the supplied original soundtrack segment, unchanged; no replacement music or invented dialogue.'])

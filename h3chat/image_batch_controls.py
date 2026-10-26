"""Literal controls remain authoritative after natural-language planning."""
import re

ORDINALS={name:i for i,names in enumerate((('prima','first'),('seconda','second'),('terza','third'),('quarta','fourth'),
          ('quinta','fifth'),('sesta','sixth'),('settima','seventh'),('ottava','eighth'),('nona','ninth'),('decima','tenth')),1) for name in names}
WORDS='|'.join(ORDINALS)
MARKER=re.compile(r'(?i)(?:\b(?:la|the)\s+|(?:^|(?<=[.;\n]))\s*)('+WORDS+r')\b(?:\s+(?:e|and)\s+(?:(?:la|the)\s+)?('+WORDS+r')\b)?\s*[:,-]?')
# A colon after a numeric ratio is not a list separator: "16:9. " used
# to become image 9 and silently remove the global aspect from the header.
NUMBERED=re.compile(r'(?i)(?:(?:^|[;\n]|(?<=[A-Za-zÀ-ÿ]):)\s*(\d{1,2})[.)]\s+|\b(?:immagine|image)\s+(\d{1,2})\s*[:)])')
CONTROL_PATTERNS=(
    r'(?<!\d)(?:16|9|4|3|2|1)\s*[:/]\s*(?:16|9|4|3|2|1)(?!\d)',
    r'(?<!\d)\d{3,4}\s*[x×*]\s*\d{3,4}(?!\d)',
    r'(?<![\d.])\d+(?:[.,]\d+)?\s*(?:MP|megapixel(?:s)?)\b',
    r'\bseed\s*[:=]?\s*(?:(?:fisso|fixed)\s*[:=]?\s*)?(?:-?\d+|casuale|casuali|casual[ei]|random(?:ico|ica|ized)?)\b',
    r'\b(?:steps?|passi)\s*[:=]?\s*\d+\b|\b\d+\s*(?:steps?|passi)\b',
    r'\bCFG\s*[:=]?\s*\d+(?:[.,]\d+)?\b',
    r'\b(?:strength|denoise|intensit[aà])\s*[:=]?\s*\d+(?:[.,]\d+)?\b',
    r'\bsampler\s*[:=]?\s*[a-z0-9_+.-]+',r'\bscheduler\s*[:=]?\s*[a-z0-9_+.-]+')


def requested_parameter_keys(prompt,index):
    """Only literal user controls may replace saved defaults, including grouped ratios."""
    # Preserve controls assigned by the planner from a shared header such as
    # "two 16:9 and two 9:16"; source_controls deliberately removes that ambiguity.
    markers=[m.start() for m in MARKER.finditer(prompt)]+[m.start() for m in NUMBERED.finditer(prompt)]
    header=prompt[:min(markers)] if markers else prompt
    text=header+'\n'+source_controls(prompt,index)
    keys=set()
    for pattern,names in zip(CONTROL_PATTERNS,(
        ('aspect',),('width','height'),('megapixels',),('seed',),('steps',),('cfg',),
        ('strength',),('sampler',),('scheduler',))):
        if re.search(pattern,text,re.I):keys.update(names)
    if re.search(r'\b(?:quadrat[ao]|square|verticale|vertical|portrait format|orizzontale|horizontal|landscape format)\b',text,re.I):keys.add('aspect')
    if re.search(r'\bseed\s*(?:fisso|fixed|casuale|random)',text,re.I):keys.add('seed')
    if re.search(r'\b(?:negative[ _-]*prompt|prompt\s+negativo|negativo)\s*[:=]',text,re.I):keys.add('negative_prompt')
    if re.search(r'\b(?:turbo|dmd2)\b',text,re.I):keys.add('moss_turbo')
    return keys


def global_controls(text):
    # A group request such as "two 16:9 and two 9:16" is not a global
    # override. Leave that assignment to the plan instead of taking the last.
    for pattern in CONTROL_PATTERNS:
        values=re.findall(pattern,text,re.I)
        if len({re.sub(r'\s+','',v.casefold()).replace(',','.') for v in values})>1:
            text=re.sub(pattern,'',text,flags=re.I)
    if re.search(r'\bverticale\b',text,re.I) and re.search(r'\borizzontale\b',text,re.I):
        text=re.sub(r'\b(?:verticale|orizzontale)\b','',text,flags=re.I)
    return text


def source_controls(prompt,index):
    markers=[(m.start(),m.end(),{ORDINALS[word.casefold()] for word in m.groups() if word}) for m in MARKER.finditer(prompt)]
    markers += [(m.start(),m.end(),{int(next(v for v in m.groups() if v))}) for m in NUMBERED.finditer(prompt) if 1<=int(next(v for v in m.groups() if v))<=50]
    markers.sort()
    if not markers:return global_controls(prompt)
    header=global_controls(prompt[:markers[0][0]]);local=[]
    for i,(_,end,targets) in enumerate(markers):
        if index in targets:
            local.append(prompt[end:markers[i+1][0] if i+1<len(markers) else len(prompt)])
    return header+'\n'+'\n'.join(local)

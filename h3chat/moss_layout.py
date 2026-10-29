"""MOSS spatial prompts: LLM plans normalized boxes; Python converts coordinates.

Official format: OpenMOSS/MOSS-Image USERGUIDE.md, Layout Prompts.
This compiles text only; it never invokes an image model or changes settings.
"""
import json
import math
import re


def requested(prompt):
    return bool(re.search(r'\b(?:layout|posiziona\w*|disponi|colloca|a sinistra|a destra|in alto|in basso|al centro|centrat[oaie]|top left|top right|bottom left|bottom right|on the left|on the right|at the top|at the bottom|in the cent(?:er|re))\b',prompt,re.I))


def disabled(prompt):
    return bool(re.search(r'\b(?:senza (?:box|layout)|composizione libera|no (?:boxes|layout)|free composition)\b',prompt,re.I))


def brief(width,height,*,automatic=False):
    item={'type':'object','properties':{'label':{'type':'string','enum':['text','object']},
          'caption':{'type':'string'},'text':{'type':'string'},
          'bbox':{'type':'array','items':{'type':'number'},'minItems':4,'maxItems':4}},
          'required':['label','caption','text','bbox'],'additionalProperties':False}
    schema={'type':'object','properties':{'summary':{'type':'string'},
            'items':{'type':'array','items':item,'minItems':0 if automatic else 1,'maxItems':12}},
            'required':['summary','items'],'additionalProperties':False}
    instructions=f'''You prepare a spatial layout for MOSS-Image, an image generator.
Return only JSON matching the schema. The final canvas is {width} pixels wide
and {height} pixels high. Plan positions for this aspect ratio.
summary is a self-contained English scene description preserving the user's
subjects, style, colours, perspective, relationships and composition.
items contains only the principal objects and explicitly requested visible text.
Use label object or text. caption describes the element in English. Preserve
visible text exactly in the requested language in text; objects have text "".
Each bbox is [left, top, right, bottom], normalized from 0 to 1000 on each axis,
with the origin at the top left. left < right and top < bottom. Respect the
user's spatial directions and percentages; leave breathing room around text.
Do not add labels, logos or text the user did not request. Do not add people or
objects from old requests. Do not turn a normal photograph into an infographic.
Use at most 12 main elements. No invented coordinate tags, commentary or code.
The application converts these draft boxes to MOSS's official pixel coordinates.
Sampling settings and output dimensions are handled separately; do not alter them.'''
    if automatic:instructions+='''
Decide automatically whether spatial control helps this request. Use boxes for
multiple principal subjects, relative positions, foreground/background, requested
visible text or an intentional arrangement, even when the user never says JSON
or layout. Explicit user positions always take priority over your composition.
For a simple unconstrained scene, return items=[] and a final English prose
prompt in summary. Do not box every detail or invent content to fill the frame.'''
    return instructions,schema


def planned(value,width,height,*,allow_prose=True):
    """One planner decision, before inference; never reinterpret official JSON."""
    if allow_prose and isinstance(value,dict) and value.get('items')==[]:
        summary=value.get('summary')
        if not isinstance(summary,str) or not summary.strip():raise ValueError('Descrizione MOSS vuota.')
        return summary.strip()
    return compile_layout(value,width,height)


def number(value):
    if type(value) not in (int,float) or not math.isfinite(value):raise ValueError('Coordinate layout MOSS non valide.')
    return value


def compile_layout(value,width,height):
    if not isinstance(value,dict) or not isinstance(value.get('summary'),str) or not value['summary'].strip():
        raise ValueError('Descrizione layout MOSS non valida.')
    items=value.get('items')
    if not isinstance(items,list) or not 1<=len(items)<=12:raise ValueError('Layout MOSS: scegli da 1 a 12 elementi.')
    output=[]
    for item in items:
        if not isinstance(item,dict) or item.get('label') not in ('object','text') or not isinstance(item.get('caption'),str) or not item['caption'].strip():
            raise ValueError('Elemento layout MOSS non valido.')
        box=item.get('bbox')
        if not isinstance(box,list) or len(box)!=4:raise ValueError('Coordinate layout MOSS non valide.')
        left,top,right,bottom=map(number,box)
        if not (0<=left<right<=1000 and 0<=top<bottom<=1000):raise ValueError('Coordinate layout MOSS fuori immagine o invertite.')
        # Center stays identical when a non-16-aligned MOSS image is generated
        # on a slightly larger grid and then centre-cropped without rescaling.
        x0=round((left/1000-.5)*width);x1=round((right/1000-.5)*width)
        y0=round((top/1000-.5)*height);y1=round((bottom/1000-.5)*height)
        if x0>=x1 or y0>=y1:raise ValueError('Un elemento del layout MOSS è troppo piccolo.')
        result={'label':item['label'],'caption':item['caption'].strip(),'bbox':[y0,x0,y1,x1]}
        if item['label']=='text':
            if not isinstance(item.get('text'),str) or not item['text'].strip():raise ValueError('Testo layout MOSS vuoto.')
            result['text']=item['text']
        output.append(result)
    return json.dumps({'summary':{'canvas':'single','caption':value['summary'].strip()},'items':output,
                       'bbox_coord_space':'abs_centralized','bbox_format':'yxyx'},ensure_ascii=False,separators=(',',':'))


def explicit(prompt):
    """Preserve already-authored official layouts rather than asking an LLM to rewrite."""
    if not prompt.lstrip().startswith('{'):return None
    try:value=json.loads(prompt)
    except ValueError:return None
    if not isinstance(value,dict) or not {'summary','items','bbox_format','bbox_coord_space'}<=value.keys():return None
    if value['bbox_format']!='yxyx' or value['bbox_coord_space']!='abs_centralized':raise ValueError('Formato layout MOSS non supportato.')
    if not isinstance(value['summary'],dict) or not isinstance(value['summary'].get('caption'),str) or not value['summary']['caption'].strip():raise ValueError('Descrizione layout MOSS non valida.')
    if not isinstance(value['items'],list) or not value['items']:raise ValueError('Layout MOSS vuoto.')
    for item in value['items']:
        if not isinstance(item,dict) or item.get('label') not in ('text','object') or not isinstance(item.get('caption'),str):raise ValueError('Elemento layout MOSS non valido.')
        box=item.get('bbox')
        if not isinstance(box,list) or len(box)!=4:raise ValueError('Coordinate layout MOSS non valide.')
        y0,x0,y1,x1=map(number,box)
        if x0>=x1 or y0>=y1:raise ValueError('Coordinate layout MOSS invertite.')
        if item['label']=='text' and (not isinstance(item.get('text'),str) or not item['text'].strip()):raise ValueError('Testo layout MOSS vuoto.')
    return prompt.strip()

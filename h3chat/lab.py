"""Calculation and declarative Manim instructions produced by the selected chat LLM."""
import json
import math
import re
from .calculator import Calculator
from .downloads import safe_join
from .store import uid

SCHEMA={'type':'object','properties':{'title':{'type':'string'},'code':{'type':'string'}},'required':['title','code'],'additionalProperties':False}
def object_schema(kind,fields):
    properties={'type':{'type':'string','const':kind},'x':{'type':'number'},'y':{'type':'number'},'color':{'type':'string'}}|fields
    return {'type':'object','properties':properties,'required':list(properties),'additionalProperties':False}
NUMBER={'type':'number'};TEXT={'type':'string'};POINT={'type':'array','items':NUMBER,'minItems':2,'maxItems':2}
OBJECT_SCHEMA={'oneOf':[object_schema(kind,fields) for kind,fields in [('text',{'text':TEXT}),('formula',{'text':TEXT}),('circle',{'radius':NUMBER}),('rectangle',{'width':NUMBER,'height':NUMBER}),('arrow',{'start':POINT,'end':POINT}),('plot',{'expression':TEXT,'x_min':NUMBER,'x_max':NUMBER,'y_min':NUMBER,'y_max':NUMBER})]]}
FRAME_SCHEMA={'type':'object','properties':{'title':TEXT,'objects':{'type':'array','items':OBJECT_SCHEMA,'minItems':1,'maxItems':30}},'required':['title','objects'],'additionalProperties':False}
MANIM_SCHEMA={'type':'object','properties':{'title':TEXT,'scenes':{'type':'array','items':FRAME_SCHEMA,'minItems':1,'maxItems':12}},'required':['title','scenes'],'additionalProperties':False}
MANIM_BRIEF=r'''Create a declarative animation storyboard as a JSON object with title and scenes.
Each scene contains title and objects; the screen is cleared between scenes. Only the listed object types exist:
text (text), formula (text in MathText, e.g. A=\pi r^2), circle (radius), rectangle (width,height),
arrow (start:[x,y],end:[x,y]), plot (expression using x and math, x_min,x_max,y_min,y_max).
Every object has type,x,y,color. Color is hex #RRGGBB. Position x=-6..6,y=-3..3.
Use a few simple objects and avoid overlap. Never produce executable code or invented object types.
Preserve numbers from supplied documents. Do not invent unreadable image data.
Example: {"title":"Cerchio","scenes":[{"title":"Area","objects":[{"type":"text","text":"Area del cerchio","x":0,"y":2,"color":"#24605b"},{"type":"circle","radius":1,"x":0,"y":0,"color":"#24605b"},{"type":"formula","text":"A=\\pi r^2","x":0,"y":-2,"color":"#24605b"}]}]}.
'''
BRIEF='''Prepare a precise calculation artifact. Return title and code as strings in JSON.
For calculation: code is Python numerical syntax interpreted in a bounded environment.
Allowed: assignments, for/range, if, list comprehensions, numeric lists/dicts, indexing,
math.sin/cos/tan/sqrt/exp/log and standard math functions, pi/e, sum/min/max/abs/round/len/print.
No files, network, imports except math, arbitrary attributes, functions, classes or external packages.
Print the final results. Optionally assign chart={"type":"line|bar|scatter|pie|doughnut","title":...,
"labels":[...],"datasets":[{"label":...,"data":[numbers or {"x":number,"y":number}]}]}.
Compute every plotted coordinate using the code. Do not fabricate unreadable image values.
All exact text/data from source excerpts remain traceable.
'''

def route(prompt):
    if re.search(r'\bmanim\b',prompt,re.I):return 'manim'
    if re.search(r'\b(?:esegui|usa|utilizza)\b.*\b(?:interprete|python)\b|\bcalcola\b.*\b(?:python|interprete)\b',prompt,re.I):return 'calculate'
    return None

def validate_scene(scene):
    if isinstance(scene,dict) and 'scenes' in scene:
        if set(scene)-{'title','scenes'} or not isinstance(scene.get('title',''),str) or len(scene.get('title',''))>150:raise ValueError('Storyboard non valido.')
        frames=scene['scenes']
        if not isinstance(frames,list) or not 1<=len(frames)<=12:raise ValueError('Da 1 a 12 scene Manim.')
        for frame in frames:
            if not isinstance(frame,dict) or 'scenes' in frame:raise ValueError('Le scene dello storyboard non possono contenere altri storyboard.')
            validate_scene(frame)
        return scene
    if not isinstance(scene,dict) or set(scene)-{'title','objects'} or not isinstance(scene.get('title',''),str) or len(scene.get('title',''))>150:raise ValueError('Scena Manim non valida.')
    objects=scene.get('objects')
    if not isinstance(objects,list) or not 1<=len(objects)<=30:raise ValueError('Manim: da 1 a 30 oggetti.')
    for obj in objects:
        kind=obj.get('type') if isinstance(obj,dict) else None
        fields={'text':{'text'},'formula':{'text'},'circle':{'radius'},'rectangle':{'width','height'},'arrow':{'start','end'},'plot':{'expression','x_min','x_max','y_min','y_max'}}
        if kind not in fields or set(obj)-fields[kind]-{'type','x','y','color'}:raise ValueError('Oggetto Manim non supportato.')
        if not re.fullmatch(r'#[0-9a-fA-F]{6}',obj.get('color','#24605b')):raise ValueError('Colore Manim non valido.')
        for key in ('x','y','radius','width','height','x_min','x_max','y_min','y_max'):
            if key in obj and (type(obj[key]) not in (int,float) or not math.isfinite(obj[key]) or abs(obj[key])>10000):raise ValueError('Coordinata Manim non valida.')
        if abs(obj.get('x',0))>7 or abs(obj.get('y',0))>4:raise ValueError('Oggetto fuori dalla scena.')
        for key in ('radius','width','height'):
            if key in obj and not .05<=obj[key]<=12:raise ValueError('Dimensione oggetto non valida.')
        if kind in ('text','formula'):
            if not isinstance(obj.get('text'),str) or not 1<=len(obj['text'])<=1000:raise ValueError('Testo Manim non valido.')
        if kind=='arrow':
            for key in ('start','end'):
                v=obj.get(key)
                if not isinstance(v,list) or len(v)!=2 or any(type(x) not in (int,float) or not math.isfinite(x) or abs(x)>7 for x in v):raise ValueError('Estremi freccia non validi.')
        if kind=='plot':
            if not isinstance(obj.get('expression'),str) or len(obj['expression'])>500:raise ValueError('Espressione grafico non valida.')
            if obj.get('x_min',-3)>=obj.get('x_max',3) or obj.get('y_min',0)>=obj.get('y_max',9):raise ValueError('Intervallo assi non valido.')
            calculate=Calculator()
            for x in (obj.get('x_min',-3),(obj.get('x_min',-3)+obj.get('x_max',3))/2,obj.get('x_max',3)):
                calculate.values['x']=x;calculate.run('y = '+obj['expression'])
    return scene

def validate_chart(chart):
    if not isinstance(chart,dict) or chart.get('type') not in ('line','bar','scatter','pie','doughnut'):raise ValueError('Grafico numerico non valido.')
    series=chart.get('datasets');labels=chart.get('labels',[])
    if not isinstance(series,list) or not 1<=len(series)<=8 or not isinstance(labels,list) or len(labels)>1000:raise ValueError('Serie grafico non valide.')
    for row in series:
        if not isinstance(row,dict) or not isinstance(row.get('data'),list) or not 1<=len(row['data'])<=1000:raise ValueError('Dati grafico non validi.')
        if chart['type']!='scatter' and len(row['data'])!=len(labels):raise ValueError('Etichette e dati hanno lunghezze diverse.')
        for item in row['data']:
            values=[item.get('x'),item.get('y')] if chart['type']=='scatter' and isinstance(item,dict) else [item]
            if any(type(x) not in (int,float) or not math.isfinite(x) for x in values):raise ValueError('Coordinate non numeriche.')
    return chart

def files(data,job_id,title,items):
    result=[]
    for name,content,mime in items:
        relative=f'outputs/{job_id}/{name}';path=safe_join(data,relative);path.parent.mkdir(parents=True,exist_ok=True);path.write_text(content,encoding='utf-8');result.append({'id':uid(),'name':name,'path':relative,'mime':mime})
    return result

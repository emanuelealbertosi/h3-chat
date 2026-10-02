"""Full Manim source contract. Execution is isolated by the Windows broker."""
import ast
import re

SCHEMA={'type':'object','properties':{'title':{'type':'string'},'code':{'type':'string'},'scene_name':{'type':'string'}},
        'required':['title','code','scene_name'],'additionalProperties':False}
BRIEF=r'''Create a complete executable Manim Community 0.21 Python scene.
Return JSON with title, code and scene_name. Use `from manim import *` and import
numpy as np when needed. Define the named Scene or ThreeDScene subclass with a
construct method. Full Manim API is available: transformations, ValueTracker,
updaters, camera movement, ThreeDAxes, Surface, meshes and ImageMobject.
Use Text for prose and MathTex/Tex for LaTeX mathematics. Do not replace formulas
with approximate text. Prefer Cairo-compatible objects unless GPU is selected.
The default background is dark teal; use contrasting colors. Keep labels readable and fixed to the screen in 3D when appropriate. Set camera
orientation before drawing 3D. Numerically compute coordinates and preserve
facts, numbers and citations from documents; do not invent unreadable data.
Use only the attached asset filenames explicitly listed in the request.
Do not use internet, install packages, read other files, spawn tools yourself or
start an interactive window. The application handles rendering and export.
Do not call scene.render() or a CLI from the scene code. Respect requested
duration, resolution and fps. Keep all scene code, no ellipses or placeholders.
'''

def validate_source(value):
    if not isinstance(value,dict) or set(value)-{'title','code','scene_name'}:
        raise ValueError('Sorgente Manim non valido.')
    title=value.get('title','Animazione Manim');code=value.get('code');name=value.get('scene_name')
    if not isinstance(title,str) or not 1<=len(title)<=150:raise ValueError('Titolo Manim non valido.')
    if not isinstance(code,str) or not 1<=len(code)<=100000:raise ValueError('Codice Manim vuoto o troppo lungo.')
    try:tree=ast.parse(code)
    except SyntaxError as e:raise ValueError(f'Python Manim: riga {e.lineno}: {e.msg}') from e
    classes=[n.name for n in tree.body if isinstance(n,ast.ClassDef)]
    scenes=[n.name for n in tree.body if isinstance(n,ast.ClassDef) and any((isinstance(b,ast.Name) and b.id.endswith('Scene')) or (isinstance(b,ast.Attribute) and b.attr.endswith('Scene')) for b in n.bases)]
    if name is None:
        if len(scenes)!=1:raise ValueError('Indica scene_name quando il sorgente contiene più classi.')
        name=scenes[0]
    if not isinstance(name,str) or not re.fullmatch(r'[A-Za-z_]\w{0,99}',name) or name not in classes:
        raise ValueError('La classe della scena Manim non è presente nel codice.')
    # This is a format/syntax check, not a Python security sandbox.
    return {'title':title,'code':code,'scene_name':name}

def source_from_text(text):
    """Accept a .py block, the exported source JSON, or legacy storyboard JSON."""
    import json
    text=text.strip()
    if text.startswith('{'):
        value=json.loads(text)
        return validate_source(value) if 'code' in value else value
    match=re.search(r'^# h3_scene: ([A-Za-z_]\w{0,99})$',text,re.M)
    return validate_source({'title':'Animazione Manim','code':text}|({'scene_name':match[1]} if match else {}))


def duration(prompt,default):
    """Explicit duration beats preferences; reject unsupported requests clearly."""
    found=re.search(r'(?<![\w.])(\d+(?:[.,]\d+)?)\s*(second[io]|seconds?|sec|s|minut[io]|minutes?|min)\b',prompt,re.I)
    if not found:return default,False
    value=float(found[1].replace(',','.'))*(60 if found[2].lower().startswith('min') else 1)
    if not 1<=value<=600:raise ValueError('Manim: la durata richiesta deve essere fra 1 e 600 secondi.')
    return value,True

"""Per-model MiniMax H3 settings and validated, immutable generation plans."""
import math
import re
import secrets
from fractions import Fraction

DEFAULTS = {'duration':15, 'megapixels':.7, 'aspect':'16:9', 'steps':12, 'cfg':1,
            'sampler':'res_multistep', 'scheduler':'simple', 'seed':-1,
            'shift_video':12, 'shift_audio':3, 'offload':True, 'attention':'auto','attention_chunks':0}
ASPECTS = ('16:9','9:16','1:1','4:3','3:4')

def validate(value):
    if not isinstance(value,dict) or set(value)-set(DEFAULTS):raise ValueError('Parametri video non riconosciuti.')
    result=DEFAULTS|value
    for key,lo,hi in (('duration',1,15),('megapixels',.2,1),('steps',1,50),('cfg',1,10),('shift_video',.01,100),('shift_audio',.01,100)):
        v=result[key]
        if type(v) not in (int,float) or not math.isfinite(v) or not lo<=v<=hi:raise ValueError('Parametro video fuori intervallo: '+key)
    if type(result['steps']) is not int:raise ValueError('I passi video devono essere interi.')
    if result['aspect'] not in ASPECTS:raise ValueError('Formato video non valido.')
    if result['sampler'] not in ('res_multistep','euler','dpmpp_2m') or result['scheduler'] not in ('simple','normal','beta'):raise ValueError('Sampler/scheduler video non supportato.')
    if type(result['offload']) is not bool:raise ValueError('Offload video: scegli attivo o disattivo.')
    if result['attention'] not in ('auto','sage','pytorch'):raise ValueError('Accelerazione video non supportata.')
    if type(result['attention_chunks']) is not int or not 0<=result['attention_chunks']<=56:raise ValueError('Suddivisioni attenzione: da 0 (automatico) a 56.')
    if type(result['seed']) is not int or not -1<=result['seed']<=2147483647:raise ValueError('Seed video non valido.')
    return result

def options(model,settings,randomize=True):
    result=validate(settings.get('video_overrides',{}).get(model['id'],{}))
    if randomize and result['seed']==-1:result['seed']=secrets.randbelow(2**31)
    a,b=map(int,result['aspect'].split(':'));ratio=a/b
    result['width']=max(32,round(math.sqrt(result['megapixels']*1024**2*ratio)/32)*32)
    result['height']=max(32,round(math.sqrt(result['megapixels']*1024**2/ratio)/32)*32)
    result['frames']=round(result['duration']*24)
    return result

def resolve_canvas(opts,plan,image_sizes,prompt=''):
    """Choose the output ratio before padding to the H3 latent's 32px grid.

    Keyframes own the format. Reference-only jobs can override it in the user's
    original prompt. The padded model canvas is cropped back after decoding.
    """
    matches=list(re.finditer(r'(?<![\d.])(\d+(?:[.,]\d+)?)\s*[:/]\s*(\d+(?:[.,]\d+)?)(?![\d.])',prompt))
    explicit=None
    for match in matches:
        prefix=prompt[max(0,match.start()-50):match.start()]
        # Fractions in a scene description are not output formats.
        if '/' in match.group(0) and not re.search(r'\b(?:format[oa]?|aspect|ratio|rapporto)\b',prefix,re.I):continue
        if re.search(r'\b(?:non|not)\s*(?:in\s+)?(?:format[oa]?\s+)?$',prefix,re.I):continue
        a,b=(Fraction(v.replace(',','.')) for v in match.groups())
        if a>0 and b>0 and Fraction(1,10)<=a/b<=10:explicit=a/b
    if explicit is None:
        if re.search(r'\b(?:verticale|vertical|portrait)\b',prompt,re.I):explicit=Fraction(9,16)
        elif re.search(r'\b(?:quadrato|quadrata|square)\b',prompt,re.I):explicit=Fraction(1)
        elif re.search(r'\b(?:orizzontale|landscape|widescreen)\b',prompt,re.I):explicit=Fraction(16,9)
    images=plan.get('images',[])
    guides=sorted((x for x in images if x['role']=='keyframe'),key=lambda x:(x['seconds'],x['index']))
    anchor=guides[0] if guides else (images[0] if images and explicit is None else None)
    if anchor:
        width,height=image_sizes[anchor['index']-1]
        if min(width,height)<=0:raise ValueError('Dimensioni del riferimento video non valide.')
        ratio=Fraction(width,height);source='image'
    elif explicit is not None:ratio=explicit;source='prompt'
    else:ratio=Fraction(opts['aspect'].replace(':','/'));source='preset'
    area=opts['megapixels']*1024**2
    a,b=ratio.numerator,ratio.denominator
    if max(a,b)<=32:
        step=2 if a%2 or b%2 else 1
        k=max(step,round(math.sqrt(area/(a*b))/step)*step)
        output_width,output_height=a*k,b*k
    else:
        output_width=max(2,round(math.sqrt(area*float(ratio))/2)*2)
        output_height=max(2,round(output_width/float(ratio)/2)*2)
    width=math.ceil(output_width/32)*32;height=math.ceil(output_height/32)*32
    if max(width,height)>8192:raise ValueError('Formato troppo allungato per il video. Usa soli riferimenti e specifica un formato nel prompt.')
    return opts|{'aspect':f'{a}:{b}','aspect_source':source,'format_image':anchor['index'] if anchor else None,
        'width':width,'height':height,'output_width':output_width,'output_height':output_height}

def validate_plan(plan,refs,duration):
    if not isinstance(plan,dict) or set(plan)-{'prompt','images','audios'}:raise ValueError('Piano video non valido.')
    prompt=plan.get('prompt')
    if not isinstance(prompt,str) or not prompt.strip() or len(prompt)>24000:raise ValueError('Istruzioni video vuote o troppo lunghe.')
    result={'prompt':prompt.strip(),'images':[],'audios':[]}
    for key,mime,limit,roles in (('images','image/',9,('reference','keyframe')),('audios','audio/',3,('reference','lipsync','reuse'))):
        available=[x for x in refs if x['mime'].startswith(mime)]
        items=plan.get(key,[])
        if not isinstance(items,list) or len(items)>limit:raise ValueError('Troppi riferimenti video.')
        seen=set();times=set()
        for item in items:
            allowed={'index','role','seconds'} if key=='images' else {'index','role','start'}
            if not isinstance(item,dict) or set(item)-allowed:raise ValueError('Riferimento video non valido.')
            index=item.get('index');role=item.get('role')
            if type(index) is not int or not 1<=index<=len(available) or index in seen or role not in roles:raise ValueError('Indice o ruolo video non valido.')
            seen.add(index);entry={'index':index,'role':role}
            field='seconds' if key=='images' else 'start';v=item.get(field,0)
            if type(v) not in (int,float) or not math.isfinite(v) or not 0<=v<=(duration if key=='images' else 3600):raise ValueError('Posizione temporale video non valida.')
            if key=='images' and role=='keyframe':
                frame=min(round(v*24),round(duration*24)-1)
                if frame in times:raise ValueError('Due immagini occupano lo stesso fotogramma.')
                times.add(frame)
            entry[field]=v;result[key].append(entry)
        # Never silently drop an attachment or reorder Picture/Audio labels.
        if seen!=set(range(1,len(available)+1)):raise ValueError('Il piano deve assegnare un ruolo a ogni allegato video.')
        result[key].sort(key=lambda x:x['index'])
    if sum(x['role'] in ('lipsync','reuse') for x in result['audios'])>1:raise ValueError('Scegli una sola traccia audio da conservare o sincronizzare.')
    for label,key,mime in (('Picture','images','image/'),('Audio','audios','audio/')):
        count=sum(x['mime'].startswith(mime) for x in refs)
        if any(not 1<=int(index)<=count for index in re.findall(r'<'+label+r'\s+(\d+)>',prompt,re.I)):
            raise ValueError('Il prompt cita un allegato '+label+' inesistente.')
    return result


def prompt_duration(prompt,has_audio=False):
    """An explicit clip duration must not be replaced by a preset silently."""
    pattern=r'\b(?:durata|duration|dura|lasting|di|da|per|for|video|clip|filmato|animazione|animation)\s*[:=]?\s*(\d+(?:[.,]\d+)?)\s*(second[io]|seconds?|sec|s|minut[io]|minutes?|min)\b'
    match=re.search(pattern,prompt,re.I)
    if not match:return None
    value=float(match[1].replace(',','.'))*(60 if match[2].lower().startswith('min') else 1)
    if has_audio and 0<value<=600:return value
    if not 1<=value<=15:raise ValueError(f'Video MiniMax H3: richiesti {value:g} secondi, ma un singolo clip supporta da 1 a 15 secondi. Allega una traccia audio per creare automaticamente più scene fino alla sua durata, oppure usa Manim.')
    return value


def with_prompt_duration(settings,prompt):
    value=prompt_duration(prompt)
    if value is None:return settings
    model=settings['video_model'];presets=dict(settings.get('video_overrides',{}))
    presets[model]=dict(presets.get(model,{}))|{'duration':value}
    return settings|{'video_overrides':presets}

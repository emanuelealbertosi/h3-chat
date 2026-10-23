"""Per-model MiniMax H3 settings and validated, immutable generation plans."""
import math
import re
import secrets
from fractions import Fraction

DEFAULTS = {'duration':12, 'megapixels':.7, 'aspect':'16:9', 'steps':12, 'cfg':1,
            'sampler':'res_multistep', 'scheduler':'simple', 'seed':-1,
            'shift_video':12, 'shift_audio':3, 'offload':True, 'attention':'auto','attention_chunks':0,'attention_chunks_mode':'auto',
            'veda_predictor':'', 'veda_sparsity':90, 'veda_reference_sparsity':90,
            'pdd_enabled':False,'pdd_lora':'','experimental_resolution':False,
            'loras':[],'source_conditioning':'reference','variants':1,'variants_mode':'clip'}
ASPECTS = ('16:9','9:16','1:1','4:3','3:4')
NATIVE_MEGAPIXELS = .98
NATIVE_PIXELS = 1344 * 768
ACCELERATION_KEYS = ('attention','attention_chunks','attention_chunks_mode','veda_predictor','veda_sparsity','veda_reference_sparsity')
REQUEST_KEYS = ('duration','megapixels','aspect','attention','attention_chunks','attention_chunks_mode','pdd_enabled','pdd_lora','seed','variants','variants_mode')


def validate_segment_seconds(value):
    if value is not None and (type(value) is not int or value not in (5,10,15)):
        raise ValueError('Durata segmenti video: scegli 5, 10 o 15 secondi.')
    return value


def capture_request(settings,body,require_model):
    """Capture composer choices in the queued snapshot, never the saved preset."""
    selection=body.get('video_model','')
    if not isinstance(selection,str):raise ValueError('Selezione modello video non valida.')
    changes=body.get('video_parameters',{})
    if isinstance(changes,dict):changes={k:v for k,v in changes.items() if k!='longtake_enabled'}
    segment_seconds=validate_segment_seconds(body.get('video_segment_seconds'))
    if not isinstance(changes,dict) or set(changes)-set(REQUEST_KEYS):
        raise ValueError('Parametri della richiesta video non validi.')
    if body.get('video') and isinstance(body.get('prompt'),str) and 'attention' not in changes:
        from .video_attention import prompt_choice
        changes=prompt_choice(body['prompt'])|changes
    if body.get('video') and isinstance(body.get('prompt'),str):
        from .video_batch import prompt_options
        changes=changes|prompt_options(body['prompt'])
    if not selection and not changes and segment_seconds is None:return settings
    if not body.get('video',False):raise ValueError('Seleziona Video per usare le impostazioni video della richiesta.')
    model_id=selection or settings['video_model']
    model=require_model(model_id,'video')
    if model.get('remote_media') and (set(changes)-{'duration','megapixels','aspect'} or segment_seconds is not None):
        raise ValueError('PDD e accelerazione locale richiedono MiniMax H3 standalone.')
    result=settings|{'video_model':model_id,'_video_segment_seconds':segment_seconds,
                     '_video_request':{'model':selection,'parameters':dict(changes)}}
    if 'aspect' in changes:result['_video_aspect']=changes['aspect']
    if changes or segment_seconds is not None:
        candidate=settings.get('video_overrides',{}).get(model_id,{})|changes
        if segment_seconds is not None:candidate['duration']=segment_seconds
        if candidate.get('pdd_enabled'):
            candidate.update(steps=8,sampler='euler',cfg=1,shift_video=12,shift_audio=3)
        result['video_overrides']=settings.get('video_overrides',{})|{model_id:validate(candidate)}
    return result

def inherited_acceleration(settings,model_id):
    """Newly linked H3 models inherit the user's selected attention configuration."""
    presets=settings.get('video_overrides',{})
    if model_id in presets:return {}
    selected=presets.get(settings.get('video_model',''),{})
    return {key:selected[key] for key in ACCELERATION_KEYS if key in selected}

def quality(value='high'):
    if not isinstance(value,str) or value not in ('high','medium'):
        raise ValueError('Qualità video: scegli Alta oppure Media.')
    return value

def validate_steps(value):
    if value is not None and (type(value) is not int or not 1<=value<=50):
        raise ValueError('Passi video: scegli un numero intero da 1 a 50.')
    return value


def apply_quality(parameters,value='high',steps=None):
    """Request-only caps; never change the model's saved generation parameters."""
    result=dict(parameters)
    if quality(value)=='medium':
        result['megapixels']=min(result.get('megapixels',DEFAULTS['megapixels']),.5)
        result['steps']=min(result.get('steps',DEFAULTS['steps']),8)
    if validate_steps(steps) is not None:result['steps']=steps
    return result

def validate(value):
    # Retired option in saved presets and timeline recipes has no effect.
    if isinstance(value,dict):value={k:v for k,v in value.items() if k!='longtake_enabled'}
    if not isinstance(value,dict) or set(value)-set(DEFAULTS):raise ValueError('Parametri video non riconosciuti.')
    result=DEFAULTS|value
    from .video_batch import validate_count
    validate_count(result['variants'])
    if result['variants_mode'] not in ('clip','video'):raise ValueError('Batch video: scegli varianti per clip oppure versioni dell’intero video.')
    from .video_attention import validate as validate_attention
    validate_attention(result)
    from .video_loras import validate as validate_loras,aligned
    result['loras']=validate_loras(result['loras'])
    if result['source_conditioning'] not in ('reference','aligned'):raise ValueError('Guida video: scegli riferimento leggero o allineata.')
    if aligned(result['loras']):result['source_conditioning']='aligned'
    if result['pdd_enabled']:
        from .video_loras import validate_pdd_combination
        validate_pdd_combination(result['loras'])
    if type(result['experimental_resolution']) is not bool:raise ValueError('Risoluzione sperimentale: scegli attivo o disattivo.')
    for key,lo,hi in (('duration',1,15),('megapixels',.2,2 if result['experimental_resolution'] else 1),('steps',1,50),('cfg',1,10),('shift_video',.01,100),('shift_audio',.01,100)):
        v=result[key]
        if type(v) not in (int,float) or not math.isfinite(v) or not lo<=v<=hi:raise ValueError('Parametro video fuori intervallo: '+key)
    if type(result['steps']) is not int:raise ValueError('I passi video devono essere interi.')
    if result['aspect'] not in ASPECTS:raise ValueError('Formato video non valido.')
    if result['sampler'] not in ('res_multistep','euler','dpmpp_2m') or result['scheduler'] not in ('simple','normal','beta'):raise ValueError('Sampler/scheduler video non supportato.')
    if type(result['offload']) is not bool:raise ValueError('Offload video: scegli attivo o disattivo.')
    if result['attention'] not in ('auto','sage','pytorch','veda','comfy_kitchen'):raise ValueError('Accelerazione video non supportata.')
    for key in ('veda_sparsity','veda_reference_sparsity'):
        v=result[key]
        if type(v) not in (int,float) or not math.isfinite(v) or not 0<=v<=99:raise ValueError('Sparsità VEDA: scegli una percentuale da 0 a 99.')
    if not isinstance(result['veda_predictor'],str) or len(result['veda_predictor'])>4096:raise ValueError('Percorso predictor VEDA non valido.')
    if result['veda_predictor']:
        from .external_models import absolute_path
        if absolute_path(result['veda_predictor']).suffix.lower()!='.safetensors':raise ValueError('VEDA richiede un predictor safetensors.')
    if type(result['attention_chunks']) is not int or not 0<=result['attention_chunks']<=56:raise ValueError('Suddivisioni attenzione: da 0 (automatico) a 56.')
    if type(result['seed']) is not int or not -1<=result['seed']<=2147483647:raise ValueError('Seed video non valido.')
    from .video_pdd import validate as validate_pdd
    validate_pdd(result)
    return result

def options(model,settings,randomize=True):
    result=apply_quality(validate(settings.get('video_overrides',{}).get(model['id'],{})),settings.get('_video_quality','high'),settings.get('_video_steps'))
    from .video_pdd import validate as validate_pdd
    validate_pdd(result)
    # Keep older 1.0 MP presets valid without exceeding the native H3 canvas.
    if result['megapixels']>NATIVE_MEGAPIXELS and not result['experimental_resolution']:
        result['requested_megapixels']=result['megapixels'];result['megapixels']=NATIVE_MEGAPIXELS
    if randomize and result['seed']==-1:result['seed']=secrets.randbelow(2**31)
    a,b=map(int,result['aspect'].split(':'));ratio=a/b
    result['width']=max(32,round(math.sqrt(result['megapixels']*1024**2*ratio)/32)*32)
    result['height']=max(32,round(math.sqrt(result['megapixels']*1024**2/ratio)/32)*32)
    result['frames']=round(result['duration']*24)
    return result

def resolve_canvas(opts,plan,image_sizes,prompt='',*,force_aspect=None):
    """Choose the output ratio before padding to the H3 latent's 32px grid.

    Keyframes own the format. Reference-only jobs can override it in the user's
    original prompt. The padded model canvas is cropped back after decoding.
    """
    matches=list(re.finditer(r'(?<![\d.:])(\d+(?:[.,]\d+)?)\s*[:/]\s*(\d+(?:[.,]\d+)?)(?![\d:]|[.,]\d)',prompt))
    # A storyboard's song clocks are not aspect ratios. Exclude whole time
    # ranges too, including unpadded clocks such as 1:6–1:9.
    clock=r'\d{1,3}:\d{1,2}(?::\d{1,2})?(?:[.,]\d+)?'
    windows=[m.span() for m in re.finditer(rf'(?<![\d.:]){clock}\s*(?:[–—-]|\bto\b|\ba\b)\s*{clock}(?![\d.:])',prompt,re.I)]
    explicit=None
    for match in matches:
        prefix=prompt[max(0,match.start()-50):match.start()]
        if any(start<=match.start()<end for start,end in windows):continue
        if ':' in match.group(0) and any(re.match(r'0\d',v) for v in match.groups()):continue
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
    if force_aspect is not None:
        if force_aspect not in ASPECTS:raise ValueError('Formato video della richiesta non valido.')
        ratio=Fraction(force_aspect.replace(':','/'));source='request';anchor=None
    elif anchor:
        width,height=image_sizes[anchor['index']-1]
        if min(width,height)<=0:raise ValueError('Dimensioni del riferimento video non valide.')
        ratio=Fraction(width,height);source='image'
    elif explicit is not None:ratio=explicit;source='prompt'
    else:ratio=Fraction(opts['aspect'].replace(':','/'));source='preset'
    area=(opts['megapixels'] if opts.get('experimental_resolution') else min(opts['megapixels'],NATIVE_MEGAPIXELS))*1024**2
    a,b=ratio.numerator,ratio.denominator
    if max(a,b)<=32:
        step=2 if a%2 or b%2 else 1
        k=max(step,round(math.sqrt(area/(a*b))/step)*step)
        output_width,output_height=a*k,b*k
    else:
        output_width=max(2,round(math.sqrt(area*float(ratio))/2)*2)
        output_height=max(2,round(output_width/float(ratio)/2)*2)
    width=math.ceil(output_width/32)*32;height=math.ceil(output_height/32)*32
    # Padding must also fit the native pixel budget while the visible result
    # retains the requested/image aspect ratio. In 16:9 this is 1344x756
    # on the native 1344x768 canvas, rather than stretched 1344x768 pixels.
    pixel_budget=math.ceil(width*height) if opts.get('experimental_resolution') else NATIVE_PIXELS
    while width*height>pixel_budget:
        if max(a,b)<=32:
            k-=step
            if k<step:raise ValueError('Formato video fuori dal canvas nativo.')
            output_width,output_height=a*k,b*k
        else:
            output_width=max(2,output_width-2);output_height=max(2,round(output_width/float(ratio)/2)*2)
        width=math.ceil(output_width/32)*32;height=math.ceil(output_height/32)*32
    if max(width,height)>8192:raise ValueError('Formato troppo allungato per il video. Usa soli riferimenti e specifica un formato nel prompt.')
    return opts|{'aspect':f'{a}:{b}','aspect_source':source,'format_image':anchor['index'] if anchor else None,
        'width':width,'height':height,'output_width':output_width,'output_height':output_height}

def validate_plan(plan,refs,duration,*,source_video=False):
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
    if any(not source_video or int(n)!=1 for n in re.findall(r'<Video\s+(\d+)>',prompt,re.I)):
        raise ValueError('Il prompt cita un Video non disponibile. Usa Modifica video per passare la clip sorgente.')
    return result


def prompt_duration(prompt,has_audio=False):
    """An explicit clip duration must not be replaced by a preset silently."""
    pattern=r'\b(?:durata|duration|dura|lasting|di|da|per|for|video|clip|filmato|animazione|animation|format|formato)\s*[:=]?\s*(\d+(?:[.,]\d+)?)\s*(second[io]|seconds?|sec|s|minut[io]|minutes?|min)\b'
    match=re.search(pattern,prompt,re.I)
    if not match:return None
    value=float(match[1].replace(',','.'))*(60 if match[2].lower().startswith('min') else 1)
    if has_audio and 0<value<=600:return value
    if not 1<=value<=15:raise ValueError(f'Video MiniMax H3: richiesti {value:g} secondi, ma un singolo clip supporta da 1 a 15 secondi. Allega una traccia audio per creare automaticamente più scene fino alla sua durata, oppure usa Manim.')
    return value


def with_prompt_duration(settings,prompt):
    if settings.get('_video_segment_seconds') is not None:return settings
    value=prompt_duration(prompt)
    if value is None:return settings
    model=settings['video_model'];presets=dict(settings.get('video_overrides',{}))
    presets[model]=dict(presets.get(model,{}))|{'duration':value}
    return settings|{'video_overrides':presets}

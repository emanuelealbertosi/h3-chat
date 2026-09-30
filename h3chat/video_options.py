"""Per-model MiniMax H3 settings and validated, immutable generation plans."""
import math
import re
import secrets

DEFAULTS = {'duration':15, 'megapixels':.7, 'aspect':'16:9', 'steps':8, 'cfg':1,
            'sampler':'res_multistep', 'scheduler':'simple', 'seed':-1,
            'shift_video':12, 'shift_audio':3, 'offload':True}
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

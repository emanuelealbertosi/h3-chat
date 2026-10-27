"""Opt-in additive GGUF control vectors; no model download or weight edits."""
import hashlib
import math
from pathlib import Path
import re
import struct

DEFAULTS={'llm_steering_enabled':False,'llm_steering_file':'','llm_steering_mode':'additive',
          'llm_steering_strength':0.0,'llm_steering_layer_start':1,'llm_steering_layer_end':0}
MAX_BYTES=16*1024**2
FORMATS={0:'B',1:'b',2:'H',3:'h',4:'I',5:'i',6:'f',7:'?',10:'Q',11:'q',12:'d'}


def validate(values):
    if values.get('llm_steering_mode','additive') not in ('additive','glp_lora'):raise ValueError('Tipo steering non valido.')
    if 'llm_steering_enabled' in values and type(values['llm_steering_enabled']) is not bool:raise ValueError('Steering: scegli attivato o disattivato.')
    path=values.get('llm_steering_file','')
    if not isinstance(path,str) or len(path)>1000 or any(ord(c)<32 for c in path):raise ValueError('Percorso vettore steering non valido.')
    strength=values.get('llm_steering_strength',0)
    if type(strength) not in (int,float) or not math.isfinite(strength) or not -10<=strength<=10:raise ValueError('Intensità steering: da -10 a 10, valore finito.')
    for key,low in (('llm_steering_layer_start',1),('llm_steering_layer_end',0)):
        v=values.get(key,DEFAULTS[key])
        if type(v) is not int or not low<=v<=999:raise ValueError('Layer steering non valido.')
    if values.get('llm_steering_layer_end',0) and values['llm_steering_layer_end']<values.get('llm_steering_layer_start',1):raise ValueError('L’ultimo layer steering precede il primo.')
    if values.get('llm_steering_enabled') and not path:raise ValueError('Seleziona il file GGUF del vettore steering.')
    if values.get('llm_steering_enabled') and values.get('llm_steering_mode')=='glp_lora' and strength!=1:
        raise ValueError('LoRA GLP: scala obbligatoria 1. Per regolare usa i layer, non aumentare alpha.')


def inspect_bytes(raw):
    """Strict bounded parser: only actual F32 direction tensors are accepted."""
    if not 24<=len(raw)<=MAX_BYTES:raise ValueError('Vettore GGUF vuoto, incompleto o oltre 16 MiB.')
    cursor=0
    def read(n):
        nonlocal cursor
        if n<0 or cursor+n>len(raw):raise ValueError('Vettore GGUF incompleto.')
        value=raw[cursor:cursor+n];cursor+=n;return value
    def number(fmt):return struct.unpack('<'+fmt,read(struct.calcsize('<'+fmt)))[0]
    def string():
        n=number('Q')
        if n>1024**2:raise ValueError('Metadati vettore troppo grandi.')
        return read(n).decode('utf8',errors='strict')
    def value(kind,depth=0):
        if kind in FORMATS:return number(FORMATS[kind])
        if kind==8:return string()
        if kind==9 and depth<2:
            subtype,count=number('I'),number('Q')
            if count>10000:raise ValueError('Array vettore troppo grande.')
            for _ in range(count):value(subtype,depth+1)
            return None
        raise ValueError('Tipo metadati vettore non supportato.')
    if read(4)!=b'GGUF' or number('I') not in (2,3):raise ValueError('File steering GGUF non valido.')
    count,kv=number('Q'),number('Q')
    if not 1<=count<=999 or kv>1000:raise ValueError('Directory vettore non valida.')
    meta={}
    for _ in range(kv):
        key=string()
        if key in meta:raise ValueError('Metadati vettore duplicati.')
        meta[key]=value(number('I'))
    if meta.get('general.architecture')!='controlvector':raise ValueError('Serve un control vector GGUF, non un modello o LoRA.')
    if any('glp' in k.lower() or ('mode' in k.lower() and str(v).lower() in ('project','projection')) for k,v in meta.items()):raise ValueError('Vettore projectivo/GLP non supportato dal motore additivo.')
    tensors=[];layers=set();embedding=None
    for _ in range(count):
        name=string();match=re.fullmatch(r'direction\.(\d+)',name)
        dims=number('I')
        if not match or dims!=1:raise ValueError('Tensore steering: atteso direction.N monodimensionale.')
        width=number('Q');kind=number('I');offset=number('Q');layer=int(match[1])
        if kind!=0 or not 1<=width<=65536 or layer in layers or layer<1:raise ValueError('Tensore steering F32 non valido o duplicato.')
        if embedding is not None and embedding!=width:raise ValueError('Dimensioni dei layer steering incoerenti.')
        embedding=width;layers.add(layer);tensors.append((offset,width))
    alignment=meta.get('general.alignment',32)
    if type(alignment) is not int or not 1<=alignment<=4096 or alignment&(alignment-1):raise ValueError('Allineamento vettore non valido.')
    start=(cursor+alignment-1)//alignment*alignment;previous_end=0;nonzero=False
    for offset,width in sorted(tensors):
        if offset<previous_end or offset%alignment or start+offset+width*4>len(raw):raise ValueError('Dati vettore incompleti o sovrapposti.')
        previous_end=offset+width*4
        for item, in struct.iter_unpack('<f',raw[start+offset:start+offset+width*4]):
            if not math.isfinite(item):raise ValueError('Il vettore contiene NaN o infinito.')
            nonzero|=item!=0
    if not nonzero:raise ValueError('Il vettore contiene soltanto zeri.')
    return {'sha256':hashlib.sha256(raw).hexdigest(),'embedding':embedding,'layers':layers,
            'model_hint':meta.get('controlvector.model_hint',''),'bytes':len(raw)}


def read_vector(path,mode='additive'):
    path=Path(path)
    if not path.is_absolute() or path.suffix.lower()!='.gguf':raise ValueError('Scegli un percorso assoluto a un vettore .gguf locale.')
    try:
        with path.open('rb') as stream:raw=stream.read(MAX_BYTES+1)
        if mode=='glp_lora':
            from .llm_steering_lora import inspect
            return raw,inspect(raw)
        return raw,inspect_bytes(raw)
    except (OSError,UnicodeError,struct.error) as exc:raise ValueError('Impossibile leggere il vettore steering GGUF.') from exc


def fingerprint(settings):
    if not settings.get('llm_steering_enabled'):return None
    validate(settings);mode=settings.get('llm_steering_mode','additive');_,info=read_vector(settings['llm_steering_file'],mode)
    return (mode,info['sha256'],settings.get('llm_steering_strength',0),settings.get('llm_steering_layer_start',1),settings.get('llm_steering_layer_end',0))


def selection(model,settings,files):
    if not settings.get('llm_steering_enabled'):return None
    validate(settings)
    if model.get('api'):raise ValueError('Steering locale non disponibile per modelli API.')
    from .models import metadata
    info=metadata(files['model']);arch=info.get('general.architecture')
    # First supported family: the exact shape of the user's Qwen 27B. Same
    # shape is necessary, not proof that a vector transfers between fine-tunes.
    width=info.get('qwen35.embedding_length');blocks=info.get('qwen35.block_count')
    if arch!='qwen35' or width!=5120 or blocks not in (64,65):raise ValueError('Steering sperimentale disponibile per Qwen qwen35 27B · 5120 dimensioni · 64 layer principali.')
    raw,vector=read_vector(settings['llm_steering_file'],settings.get('llm_steering_mode','additive'))
    if vector['embedding']!=width or vector['model_hint'] not in ('qwen35','qwen3.5','qwen3.8-27b'):raise ValueError('Architettura o dimensione del vettore diversa dal Qwen 27B selezionato.')
    first=settings.get('llm_steering_layer_start',1);last=settings.get('llm_steering_layer_end',0) or 63
    if not 1<=first<=last<=63 or max(vector['layers'])>63:raise ValueError('Steering: seleziona layer principali da 1 a 63; il blocco MTP è escluso.')
    if not set(range(first,last+1))<=vector['layers']:raise ValueError('Il vettore non contiene tutti i layer selezionati.')
    return raw,vector,first,last


def prepare(data,model,settings,files):
    if not settings.get('llm_steering_enabled'):return None
    raw,vector,first,last=selection(model,settings,files)
    folder=(Path(data)/'llm-steering/cache').resolve();folder.mkdir(parents=True,exist_ok=True)
    if settings.get('llm_steering_mode')=='glp_lora':
        from .llm_steering_lora import subset
        raw=subset(raw,vector,first,last);digest=hashlib.sha256(raw).hexdigest()
        target=folder/(digest+'.gguf')
        if not target.exists() or target.read_bytes()!=raw:target.write_bytes(raw)
        return {'cwd':folder,'sha256':digest,'args':['--lora',target.name],
                'strength':1.0,'layers':[first,last],'mode':'glp_lora'}
    name=vector['sha256']+'.gguf';target=folder/name
    if not target.exists() or target.read_bytes()!=raw:target.write_bytes(raw)
    # A content-addressed relative filename avoids the C: drive separator being
    # parsed as the strength delimiter by llama.cpp on Windows.
    return {'cwd':folder,'sha256':vector['sha256'],'args':['--control-vector-scaled',name+':'+format(settings.get('llm_steering_strength',0),'.9g'),
            '--control-vector-layer-range',first,last], 'strength':settings.get('llm_steering_strength',0),'layers':[first,last],'mode':'additive'}

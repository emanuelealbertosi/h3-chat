"""Bounded rank-one Qwen27B LoRA validation and lossless layer subsetting."""
import hashlib
import math
import re
import struct

LIMIT=16*1024**2


def inspect(raw):
    if not 24<=len(raw)<=LIMIT:raise ValueError('Adapter steering incompleto o oltre 16 MiB.')
    cursor=0
    def read(n):
        nonlocal cursor
        if n<0 or cursor+n>len(raw):raise ValueError('Adapter GGUF incompleto.')
        value=raw[cursor:cursor+n];cursor+=n;return value
    def num(fmt):return struct.unpack('<'+fmt,read(struct.calcsize('<'+fmt)))[0]
    def text():
        size=num('Q')
        if size>16000:raise ValueError('Metadati adapter troppo grandi.')
        return read(size).decode('utf8')
    if read(4)!=b'GGUF' or num('I') not in (2,3):raise ValueError('Adapter GGUF non valido.')
    count,kv=num('Q'),num('Q')
    if not 4<=count<=252 or kv>100:raise ValueError('Directory adapter non valida.')
    formats={4:'I',5:'i',6:'f',7:'?',10:'Q',11:'q',12:'d'};meta={}
    for _ in range(kv):
        key=text();kind=num('I')
        if key in meta:raise ValueError('Metadati adapter duplicati.')
        if kind==8:value=text()
        elif kind in formats:value=num(formats[kind])
        else:raise ValueError('Tipo metadati adapter non supportato.')
        meta[key]=value
    if any(meta.get(k)!=v for k,v in {'general.architecture':'qwen35','general.type':'adapter','adapter.type':'lora','adapter.lora.alpha':1.0}.items()):
        raise ValueError('Serve un LoRA GGUF qwen35 di rango 1 e alpha 1, non un vettore GLP projectivo.')
    tensors=[];names=set();coverage={}
    for _ in range(count):
        name=text();match=re.fullmatch(r'blk\.(\d+)\.(ssm_out|attn_output|ffn_down)\.weight\.lora_([ab])',name)
        dims=num('I')
        if not match or dims!=2 or name in names:raise ValueError('Tensore adapter non valido o duplicato.')
        shape=(num('Q'),num('Q'));kind=num('I');offset=num('Q')
        layer=int(match[1]);module=match[2];side=match[3]
        expected=(17408 if module=='ffn_down' else 6144,1) if side=='a' else (1,5120)
        if not 1<=layer<=63 or shape!=expected or kind!=0:raise ValueError('Layer, rango o dimensioni adapter incompatibili con Qwen27B.')
        if module!='ffn_down' and module!=('attn_output' if layer%4==3 else 'ssm_out'):
            raise ValueError('Adapter non corrispondente ai blocchi ibridi Qwen27B.')
        names.add(name);coverage.setdefault(layer,set()).add((module,side))
        tensors.append({'name':name,'shape':shape,'offset':offset,'bytes':shape[0]*shape[1]*4,'layer':layer})
    for layer,items in coverage.items():
        out='attn_output' if layer%4==3 else 'ssm_out'
        if items!={(out,'a'),(out,'b'),('ffn_down','a'),('ffn_down','b')}:
            raise ValueError('Coppie LoRA incomplete per un layer.')
    alignment=meta.get('general.alignment',32)
    if type(alignment) is not int or not 1<=alignment<=4096 or alignment&(alignment-1):raise ValueError('Allineamento adapter non valido.')
    start=(cursor+alignment-1)//alignment*alignment;end=0
    for tensor in sorted(tensors,key=lambda t:t['offset']):
        offset=tensor['offset'];size=tensor['bytes']
        if offset<end or offset%alignment or start+offset+size>len(raw):raise ValueError('Dati adapter sovrapposti o incompleti.')
        nonzero=False
        for value, in struct.iter_unpack('<f',raw[start+offset:start+offset+size]):
            if not math.isfinite(value):raise ValueError('NaN o infinito nell’adapter.')
            nonzero|=value!=0
        if not nonzero:raise ValueError('Tensore adapter vuoto.')
        end=offset+size
    return {'sha256':hashlib.sha256(raw).hexdigest(),'embedding':5120,'layers':set(coverage),
            'model_hint':'qwen35','bytes':len(raw),'mode':'glp_lora','payload_start':start,'tensors':tensors}


def subset(raw,info,first,last):
    """Keep actual layer numbers, all rank-one payload bytes and alpha=1."""
    tensors=[t for t in info['tensors'] if first<=t['layer']<=last]
    def text(s):
        b=s.encode();return struct.pack('<Q',len(b))+b
    meta={'general.architecture':'qwen35','general.type':'adapter','adapter.type':'lora'}
    output=b'GGUF'+struct.pack('<IQQ',3,len(tensors),4)
    for key,value in meta.items():output+=text(key)+struct.pack('<I',8)+text(value)
    output+=text('adapter.lora.alpha')+struct.pack('<If',6,1.)
    payload=bytearray()
    for tensor in tensors:
        payload.extend(b'\0'*((-len(payload))%32));offset=len(payload)
        start=info['payload_start']+tensor['offset'];payload.extend(raw[start:start+tensor['bytes']])
        output+=text(tensor['name'])+struct.pack('<IQQIQ',2,*tensor['shape'],0,offset)
    output+=b'\0'*((-len(output))%32)
    return output+payload

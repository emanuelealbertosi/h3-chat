"""Offline conversion of the authorized Qwen GLP-49 PEFT adapter; no model download."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import struct
import sys

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from h3chat.llm_steering_lora import inspect


def convert(folder,target):
    folder=Path(folder);target=Path(target)
    source=folder/'adapter_model.safetensors';config=folder/'adapter_config.json'
    if source.stat().st_size>16*1024**2 or config.stat().st_size>64000:raise ValueError('Adapter oltre il limite previsto.')
    raw=source.read_bytes();settings=json.loads(config.read_text())
    if settings.get('r')!=1 or settings.get('lora_alpha')!=1 or settings.get('base_model_name_or_path')!='Qwen/Qwen3.8-27B':raise ValueError('Serve l’adapter GLP-49 Qwen27B originale, rango e alpha 1.')
    if len(raw)<8:raise ValueError('Safetensors incompleto.')
    length=struct.unpack_from('<Q',raw)[0]
    if not 1<=length<=1024**2 or 8+length>len(raw):raise ValueError('Header safetensors non valido.')
    header=json.loads(raw[8:8+length]);start=8+length
    def text(value):
        value=value.encode();return struct.pack('<Q',len(value))+value
    tensors=[];payload=bytearray();regions=[];seen=set()
    mapping={'linear_attn.out_proj':'ssm_out','self_attn.o_proj':'attn_output','mlp.down_proj':'ffn_down'}
    for name,entry in header.items():
        if name=='__metadata__':continue
        match=re.fullmatch(r'base_model\.model\.model\.language_model\.layers\.(\d+)\.(linear_attn\.out_proj|self_attn\.o_proj|mlp\.down_proj)\.lora_([AB])\.weight',name)
        if not match or entry.get('dtype')!='F32':raise ValueError('Nome o tipo tensore non supportato.')
        shape=entry.get('shape');bounds=entry.get('data_offsets')
        if not isinstance(shape,list) or len(shape)!=2 or any(type(v) is not int or not 1<=v<=17408 for v in shape):raise ValueError('Dimensioni tensore non valide.')
        if not isinstance(bounds,list) or len(bounds)!=2 or any(type(v) is not int for v in bounds):raise ValueError('Offset tensore non valido.')
        first,last=bounds
        if first<0 or last-first!=shape[0]*shape[1]*4 or start+last>len(raw):raise ValueError('Dati tensore incompleti.')
        regions.append((first,last));name=f'blk.{int(match[1])}.{mapping[match[2]]}.weight.lora_{match[3].lower()}'
        if name in seen:raise ValueError('Tensore duplicato.')
        seen.add(name);payload.extend(b'\0'*((-len(payload))%32));offset=len(payload);payload.extend(raw[start+first:start+last])
        tensors.append((name,list(reversed(shape)),offset))
    previous=0
    for first,last in sorted(regions):
        if first!=previous:raise ValueError('Dati safetensors sovrapposti o non descritti.')
        previous=last
    if start+previous!=len(raw):raise ValueError('Dati aggiuntivi nel safetensors.')
    meta={'general.architecture':'qwen35','general.type':'adapter','general.name':'GLP-49 Qwen3.8-27B rank-one LoRA','adapter.type':'lora','h3.source_repository':'msuiche/Qwen3.8-27B-abliterated-cyber-GLP-49'}
    result=b'GGUF'+struct.pack('<IQQ',3,len(tensors),len(meta)+1)
    for key,value in meta.items():result+=text(key)+struct.pack('<I',8)+text(value)
    result+=text('adapter.lora.alpha')+struct.pack('<If',6,1.)
    for name,shape,offset in tensors:result+=text(name)+struct.pack('<IQQIQ',2,*shape,0,offset)
    result+=b'\0'*((-len(result))%32);result+=payload
    info=inspect(result)
    if info['layers']!=set(range(1,64)) or len(tensors)!=252:raise ValueError('GLP-49 incompleto.')
    if target.exists() and target.read_bytes()!=result:raise ValueError('Esiste già un file differente: scegli una nuova destinazione.')
    target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(result)
    return {'path':str(target),'sha256':hashlib.sha256(result).hexdigest(),'source_sha256':hashlib.sha256(raw).hexdigest(),'tensors':len(tensors),'scale':1,'lossless':True}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--adapter',type=Path,required=True);parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    print(json.dumps(convert(args.adapter,args.output),ensure_ascii=False,indent=2))

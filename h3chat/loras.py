"""Bounded indexing of user-selected LoRA folders. Original files are read only."""
from __future__ import annotations
import hashlib
import json
import math
import os
import re
import struct
import threading
import time
from functools import lru_cache
from pathlib import Path
from .external_models import absolute_path
from .image_options import compatible

MAX_SELECTED=8


def validate_directories(value):
    if not isinstance(value,list) or len(value)>20:raise ValueError('Puoi collegare fino a 20 cartelle LoRA.')
    paths=[]
    for raw in value:
        path=absolute_path(raw)
        if path.is_file():raise ValueError('Seleziona una cartella LoRA, non un file.')
        # Keep disconnected drives in the preferences so an unavailable disk
        # does not block unrelated settings; the index reports unavailable roots.
        if str(path) not in paths:paths.append(str(path))
    return paths


@lru_cache(maxsize=1024)
def _inspect(path,size,stamp):
    try:
        with open(path,'rb') as stream:
            length=struct.unpack('<Q',stream.read(8))[0]
            if not 2<=length<=min(4*1024**2,size-8):return None
            header=json.loads(stream.read(length))
        if not isinstance(header,dict) or len(header)>50000:return None
        names=set(k for k in header if k!='__metadata__')
        pairs=0
        for name in names:
            for down,up in (('.lora_down.weight','.lora_up.weight'),('.lora_A.weight','.lora_B.weight'),('.lora_A.default.weight','.lora_B.default.weight')):
                if name.endswith(down) and name[:-len(down)]+up in names:pairs+=1
        if not pairs:return None
        for name in names:
            tensor=header[name];offsets=tensor.get('data_offsets') if isinstance(tensor,dict) else None
            if not isinstance(offsets,list) or len(offsets)!=2 or any(type(x) is not int for x in offsets) or not 0<=offsets[0]<offsets[1]<=size-length-8:return None
        meta=header.get('__metadata__',{})
        if not isinstance(meta,dict):meta={}
        evidence=' '.join(str(meta.get(k,'')) for k in ('ss_base_model_version','modelspec.architecture','base_model','ss_model_type')).lower()
        family=''
        if 'anima' in evidence:family='anima'
        elif 'qwen' in evidence and 'image' in evidence:family='qwen-image'
        elif re.search(r'flux[._ -]?2',evidence):family='flux2'
        elif 'flux' in evidence:family='flux1'
        elif 'sdxl' in evidence or 'stable-diffusion-xl' in evidence:family='sdxl'
        elif any(k in evidence for k in ('sd_v1','sd1.5','sd_1.5','sd15','stable-diffusion-v1')):family='sd15'
        elif any(k in evidence for k in ('sd_v2','sd2.1','stable-diffusion-v2')):family='sd2'
        title=str(meta.get('modelspec.title',''))[:150]
        return {'family':family,'title':title,'pairs':pairs}
    except (OSError,ValueError,TypeError,struct.error):return None


def inspect(path):
    try:
        p=Path(path);st=p.stat()
        if p.suffix.lower()!='.safetensors' or not p.is_file():return None
        return _inspect(str(p),st.st_size,st.st_mtime_ns)
    except OSError:return None


def fingerprint(path):
    st=Path(path).stat();return (st.st_size,st.st_mtime_ns)


class LoraLibrary:
    def __init__(self):self.lock=threading.RLock();self.cached=None;self.key=None;self.scanned=0

    def scan(self, directories, refresh=False):
        key=tuple(directories)
        with self.lock:
            if not refresh and self.key==key and self.cached is not None and time.monotonic()-self.scanned<15:return self.cached
            items={};warnings=[];visited=set();files=0;truncated=False;deadline=time.monotonic()+8
            for raw in directories:
                root=Path(raw).resolve()
                if not root.is_dir():warnings.append('Cartella non disponibile: '+str(root));continue
                stack=[(root,0)]
                while stack:
                    folder,depth=stack.pop()
                    if folder in visited:continue
                    visited.add(folder)
                    if len(visited)>512 or files>=5000 or len(items)>=1000 or time.monotonic()>deadline:truncated=True;break
                    try:
                        with os.scandir(folder) as entries:
                            for entry in entries:
                                files+=1
                                if files>5000 or len(items)>=1000 or time.monotonic()>deadline:truncated=True;break
                                path=Path(entry.path)
                                if path.is_symlink() or (hasattr(path,'is_junction') and path.is_junction()):continue
                                path=path.resolve()
                                if not path.is_relative_to(root):continue
                                if entry.is_dir(follow_symlinks=False):
                                    if depth<8:stack.append((path,depth+1))
                                    else:truncated=True
                                    continue
                                traits=inspect(path)
                                if not traits:continue
                                size,stamp=fingerprint(path)
                                ident=hashlib.sha256(os.path.normcase(str(path)).encode()).hexdigest()[:24]
                                items[ident]={'id':ident,'name':traits['title'] or path.stem,'filename':path.name,'path':str(path),
                                              'relative':str(path.relative_to(root)),'directory':str(root),'size':size,'mtime_ns':stamp,
                                              'family':traits['family'],'note':'Famiglia rilevata dai metadati.' if traits['family'] else 'Famiglia non dichiarata: scegli il modello per cui è stato addestrato.'}
                    except OSError:warnings.append('Impossibile leggere: '+str(folder))
                if truncated:break
            if truncated:warnings.append('Scansione limitata: collega sottocartelle più precise per vedere gli altri LoRA.')
            self.cached={'items':sorted(items.values(),key=lambda v:(v['name'].casefold(),v['path'])),'warnings':warnings,'truncated':truncated}
            self.key=key;self.scanned=time.monotonic();return self.cached

    def capture(self, selections, directories, models):
        if not isinstance(selections,list) or len(selections)>MAX_SELECTED:raise ValueError('Seleziona al massimo 8 LoRA per messaggio.')
        if not selections:return []
        library={item['id']:item for item in self.scan(directories)['items']};result=[];seen=set()
        for choice in selections:
            if not isinstance(choice,dict) or set(choice)-{'id','weight','model_id'}:raise ValueError('Selezione LoRA non valida.')
            ident=choice.get('id');target=choice.get('model_id');weight=choice.get('weight',1)
            if not isinstance(ident,str) or not isinstance(target,str):raise ValueError('LoRA o modello destinatario non valido.')
            if (ident,target) in seen:raise ValueError('LoRA duplicato per lo stesso modello.')
            seen.add((ident,target))
            if type(weight) not in (int,float) or not math.isfinite(weight) or not -2<=weight<=2:raise ValueError('Peso LoRA: usa un valore tra -2 e 2.')
            item=library.get(ident);model=models.get(target)
            if not item:raise ValueError('LoRA non trovato nelle cartelle configurate: aggiorna l’elenco.')
            if not model or not any(c in model['capabilities'] for c in ('create','edit')):raise ValueError('Scegli un modello immagini per il LoRA.')
            if not compatible(item['family'],model):raise ValueError(f"{item['name']}: famiglia {item['family']} incompatibile con {model['name']}.")
            try:unchanged=fingerprint(item['path'])==(item['size'],item['mtime_ns'])
            except OSError:unchanged=False
            if not unchanged:raise ValueError('Il file LoRA è assente o cambiato: aggiorna l’elenco e selezionalo di nuovo.')
            result.append(item|{'weight':float(weight),'model_id':target,'model_name':model['name']})
        return result


def for_model(snapshot, model):
    selected=[item for item in snapshot if item['model_id']==model['id'] and item['weight']!=0]
    for item in selected:
        try:unchanged=fingerprint(item['path'])==(item['size'],item['mtime_ns'])
        except OSError:unchanged=False
        if not unchanged:raise ValueError('LoRA assente o cambiato dopo l’invio: '+item['name']+'. Selezionalo di nuovo.')
        if not compatible(item['family'],model):raise ValueError('LoRA non compatibile con il modello selezionato: '+item['name'])
    return selected


def public(items):
    return [{key:item[key] for key in ('id','name','weight','model_id','model_name')} for item in items]

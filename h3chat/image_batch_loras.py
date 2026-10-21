"""Recognize uploaded safetensors adapters and bind only compatible targets."""
import math
from pathlib import Path
from .downloads import safe_join
from .image_options import compatible
from .loras import inspect, fingerprint, for_model


def uploaded(app,media):
    result=[]
    for item in media:
        if item.get('mime','').startswith('image/'):continue
        if not item.get('name','').casefold().endswith('.safetensors'):
            raise ValueError('Nel lotto allega immagini o LoRA safetensors, non altri documenti.')
        path=safe_join(app.data,item['path']);traits=inspect(path)
        if not traits or not traits.get('family'):
            raise ValueError(item['name']+': LoRA non riconosciuto o famiglia sconosciuta. Non viene applicato a caso.')
        size,stamp=fingerprint(path)
        result.append({'id':item['id'],'name':item['name'],'path':str(path),'size':size,'mtime_ns':stamp,
                       'family':traits['family'],'weight':1.,'model_id':'','model_name':'Destinatario dal piano',
                       'auto_target':True})
    return result


def select(snapshot,model,choices=None):
    if choices is None:
        selected=[item for item in snapshot if item.get('model_id')==model['id'] or
                  (item.get('auto_target') and compatible(item['family'],model))]
    else:
        if not isinstance(choices,list) or len(choices)>8:raise ValueError('Selezione LoRA del lotto non valida.')
        selected=[];seen=set()
        for choice in choices:
            if not isinstance(choice,dict) or set(choice)-{'id','weight'} or not isinstance(choice.get('id'),str):raise ValueError('LoRA del piano non valido.')
            ident=choice['id']
            if ident in seen:raise ValueError('LoRA duplicato nella stessa immagine.')
            seen.add(ident)
            matches=[item for item in snapshot if item['id']==ident]
            item=next((m for m in matches if m.get('model_id')==model['id']),matches[0] if matches else None)
            if item is None:raise ValueError('Il piano ha scelto un LoRA non allegato o non selezionato.')
            weight=choice.get('weight',item['weight'])
            if type(weight) not in (int,float) or not math.isfinite(weight) or not -2<=weight<=2:raise ValueError('Peso LoRA tra -2 e 2.')
            selected.append(item|{'weight':float(weight)})
    bound=[]
    for item in selected:
        if not compatible(item['family'],model):raise ValueError(f'{item["name"]}: non compatibile con {model["name"]}. Nessuna immagine avviata.')
        bound.append(item|{'model_id':model['id'],'model_name':model['name']})
    if bound and model.get('remote_media'):raise ValueError('Il modello remoto non può usare i LoRA locali del lotto.')
    return for_model(bound,model)

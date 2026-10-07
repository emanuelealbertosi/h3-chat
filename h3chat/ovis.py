"""Offline Ovis checkpoint selection and reproducible retrieval formatting."""
import json,math,struct
from pathlib import Path
from .rag_profiles import visual_enabled

QUERY_INSTRUCTION='Represent this query for retrieving relevant content.'
DOCUMENT_INSTRUCTION='Represent this passage for retrieval.'
IMAGE_INSTRUCTION='Represent this visual document for retrieval.'
FORMAT_VERSION='ovis-native-text-image-v2'

def checkpoint(path):
    folder=Path(path)
    if not folder.is_absolute() or not folder.is_dir():raise ValueError('Scegli la cartella locale di Ovis-Omni-Embedding-3B.')
    # Accept the official repository layout as well as the flattened download.
    if not (folder/'config.json').is_file() and (folder/'model/config.json').is_file():folder=folder/'model'
    try:
        config=json.loads((folder/'config.json').read_text(encoding='utf-8'))
        index=json.loads((folder/'model.safetensors.index.json').read_text(encoding='utf-8'))
        if config.get('model_type')!='qwen2_5_omni' or config.get('thinker_config',{}).get('text_config',{}).get('hidden_size')!=2048:raise ValueError()
        names=set(index['weight_map'].values())
        if not names or len(names)>20:raise ValueError()
        for name in names:
            if not isinstance(name,str) or Path(name).name!=name or '/' in name or '\\' in name or not name.endswith('.safetensors'):raise ValueError()
        files=[folder/name for name in sorted(names)]
        files += [folder/name for name in ('config.json','model.safetensors.index.json','tokenizer.json','tokenizer_config.json','chat_template.jinja')]
        files += [folder/name for name in ('processor_config.json','preprocessor_config.json') if (folder/name).is_file()]
        if not all(p.is_file() and p.stat().st_size>0 for p in files):raise ValueError()
    except (OSError,ValueError,KeyError,TypeError) as error:
        raise ValueError('Cartella Ovis incompleta o incompatibile: servono configurazione, tokenizer, template e tutti i pesi safetensors.') from error
    return folder.resolve(),files

def messages(text,query,image=None):
    content=([{'type':'image','image':image}] if image else [])+[{'type':'text','text':text}]
    return [{'role':'system','content':QUERY_INSTRUCTION if query else IMAGE_INSTRUCTION if image else DOCUMENT_INSTRUCTION},
            {'role':'user','content':content}]

def runtime_ready(root):
    return all((Path(root)/'runtime/vision/packages'/p).is_file() for p in (
        'torch/__init__.py','transformers/models/qwen2_5_omni/modeling_qwen2_5_omni.py','safetensors/__init__.py'))

def memory_assessment(settings,hardware):
    if settings.get('rag_embedding_profile')!='ovis' or not settings.get('rag_embedding_model'):return None
    result={'status':'unknown','title':'Memoria Ovis non stimabile','ram_gb':None,'vram_gb':None,
            'advice':'Ovis usa un processo separato e rilascia la memoria dopo la ricerca.'}
    try:
        _,files=checkpoint(settings['rag_embedding_model']);count=0
        for path in files:
            if path.suffix!='.safetensors':continue
            with path.open('rb') as stream:
                length=struct.unpack('<Q',stream.read(8))[0]
                if not 2<=length<=16*1024**2:raise ValueError()
                header=json.loads(stream.read(length))
            for name,tensor in header.items():
                if not (name.startswith('thinker.model.') or visual_enabled(settings) and name.startswith('thinker.visual.')):continue
                shape=tensor['shape']
                if not isinstance(shape,list) or len(shape)>8 or any(type(v) is not int or not 0<=v<=10**9 for v in shape):raise ValueError()
                count+=math.prod(shape)
        if not count:raise ValueError()
        gpu=settings.get('rag_device')=='gpu';weights=count*(2 if gpu else 4)/1024**3
        ram=weights+1.5;vram=weights+1.0 if gpu else 0
        result.update(ram_gb=round(ram,1),vram_gb=round(vram,1),status='ok',title='OK stimato · Ovis')
        result['advice']='Stima del backbone '+('e del modulo immagini' if visual_enabled(settings) else 'testuale')+', con margine. '+('Calcolo GPU; nessun offload automatico. ' if gpu else 'Calcolo CPU: indicizzare molti documenti può richiedere tempo. ')+'Il modello viene rilasciato dopo la ricerca.'
        free=hardware.get('ram',{}).get('free_mb')
        if free is None:result.update(status='unknown',title='RAM libera non rilevata')
        elif ram>max(0,free/1024-.5):result.update(status='oom',title='Rischio OOM · Ovis',advice='La RAM libera è inferiore alla stima Ovis. Libera memoria o scegli un embedding più piccolo.')
        if gpu:
            devices=[g for g in hardware.get('gpu',[]) if g.get('vendor')=='NVIDIA']
            if len(devices)!=1 or devices[0].get('free_mb') is None:
                if result['status']!='oom':result.update(status='unknown',title='VRAM Ovis non misurabile')
            elif vram>max(0,devices[0]['free_mb']/1024-.5):result.update(status='oom',title='Rischio OOM GPU · Ovis',advice='Libera la GPU oppure scegli CPU per il RAG. Ovis non trasferisce automaticamente i layer in RAM durante il calcolo.')
    except (OSError,ValueError,KeyError,TypeError,struct.error):pass
    return result

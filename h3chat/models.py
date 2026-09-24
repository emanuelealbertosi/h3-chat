"""Bounded GGUF metadata inspection and automatic, folder-scoped vision pairing."""
from __future__ import annotations
import hashlib
import json
import re
import struct
from functools import lru_cache
from pathlib import Path
from .downloads import safe_join, model_ready
from .mtp import inspect_mtp, mtp_tokens

THINK_LEVELS = ('off', 'low', 'med', 'high', 'xhigh')
_FORMATS = {0:'B', 1:'b', 2:'H', 3:'h', 4:'I', 5:'i', 6:'f', 7:'?', 10:'Q', 11:'q', 12:'d'}


@lru_cache(maxsize=64)
def _metadata(path, size, stamp):
    with open(path, 'rb') as f:
        def read(n):
            if n < 0 or f.tell()+n > min(size, 64*1024**2):
                raise ValueError('Metadati GGUF troppo grandi o incompleti.')
            b=f.read(n)
            if len(b)!=n: raise ValueError('GGUF incompleto.')
            return b
        def number(fmt): return struct.unpack('<'+fmt, read(struct.calcsize('<'+fmt)))[0]
        def string(keep=True):
            n=number('Q')
            if n>8*1024**2: raise ValueError('Stringa GGUF troppo grande.')
            raw=read(n)
            return raw.decode('utf-8', 'replace') if keep else None
        def value(kind, keep=True, depth=0):
            if kind in _FORMATS: return number(_FORMATS[kind])
            if kind==8: return string(keep)
            if kind==9 and depth<2:
                subtype,count=number('I'),number('Q')
                if count>2_000_000: raise ValueError('Array GGUF troppo grande.')
                if subtype in _FORMATS:
                    read(struct.calcsize('<'+_FORMATS[subtype])*count)
                else:
                    for _ in range(count): value(subtype,False,depth+1)
                return None
            raise ValueError('Tipo GGUF non supportato.')
        if read(4)!=b'GGUF' or number('I') not in (2,3): raise ValueError('GGUF non valido.')
        tensor_count=number('Q'); count=number('Q')
        if count>10000: raise ValueError('Troppi metadati GGUF.')
        result={}
        for _ in range(count):
            key,kind=string(),number('I')
            keep=not key.startswith('tokenizer.') or key=='tokenizer.chat_template'
            item=value(kind,keep)
            if keep and item is not None: result[key]=item
        # Inspect only the bounded tensor directory, never load model weights.
        # Keep metadata usable even when a tensor directory is damaged/too large.
        names=[]
        try:
            if tensor_count>200_000: raise ValueError('Troppi tensori GGUF.')
            max_offset=-1
            for _ in range(tensor_count):
                name=string(); dims=number('I')
                if not 1<=dims<=4: raise ValueError('Dimensioni GGUF non valide.')
                for _ in range(dims):
                    if number('Q')<=0: raise ValueError('Tensore GGUF vuoto.')
                number('I'); max_offset=max(max_offset,number('Q'))
                if name.removeprefix('model_weights/').removeprefix('vae_weights/') in ('token_embd.weight','blk.0.attn_norm.weight','model.embed_tokens.weight','vae2llm.weight','llm2vae.weight','decoder.layers.0.weight','decoder.layers.0.weight_g') or '.nextn.' in name: names.append(name)
            alignment=result.get('general.alignment',32)
            if type(alignment) is not int or not 1<=alignment<=4096: raise ValueError('Allineamento GGUF non valido.')
            data_start=(f.tell()+alignment-1)//alignment*alignment
            if tensor_count and data_start+max_offset>=size: raise ValueError('Dati dei tensori GGUF incompleti.')
            result['_h3_tensor_names']=tuple(names)
            result['_h3_tensor_scan_ok']=True
        except (ValueError,struct.error):
            result['_h3_tensor_names']=()
            result['_h3_tensor_scan_ok']=False
        return result


def metadata(path):
    try:
        p=Path(path); st=p.stat()
        return dict(_metadata(str(p.resolve()),st.st_size,st.st_mtime_ns))
    except (OSError, ValueError, struct.error): return {}


def model_path(root, model, value):
    # Only registered external model descriptors opt in to absolute paths.
    # Downloads, uploads, media and exports continue to use safe_join exclusively.
    if model.get('external'):
        path=Path(value)
        sidecar=model.get('engine')=='music' and any(f['path']==value and f['role'] in ('tokenizer','model_config','generation_config','vae_config') for f in model['files'])
        if not path.is_absolute() or (path.suffix.lower() not in ('.gguf','.safetensors') and not sidecar):
            raise ValueError('Percorso del modello esterno non valido.')
        return path.resolve()
    return safe_join(root,value)


def discover_local(root):
    """One model per dedicated folder. Never pair a projector from a shared cache."""
    root=Path(root).resolve(); base=root/'models/local'; result=[]
    if not base.exists(): return result
    for p in sorted(base.glob('*/*.gguf')):
        if 'mmproj' in p.name.lower(): continue
        try:
            relative=p.resolve().relative_to(root).as_posix()
            info=metadata(p)
            if not info or info.get('general.architecture')=='clip': continue
            # Split weights are loaded from their first shard by llama.cpp.
            shard=re.search(r'-(\d{5})-of-\d{5}\.gguf$',p.name)
            if shard and int(shard[1])!=1: continue
            files=[{'role':'model','path':relative,'size':p.stat().st_size,'filename':p.name}]
            if shard:
                for extra in sorted(p.parent.glob(p.name[:shard.start()]+'-*-of-*.gguf')):
                    if extra!=p:
                        files.append({'role':'shard','path':extra.resolve().relative_to(root).as_posix(),'size':extra.stat().st_size,'filename':extra.name})
            result.append({'id':'local-'+hashlib.sha256(relative.encode()).hexdigest()[:16],
                'name':str(info.get('general.name') or p.parent.name), 'local':True,
                'capabilities':['chat'], 'description':'Modello GGUF locale. Il proiettore mmproj compatibile viene cercato nella stessa cartella.',
                'files':files,'size':sum(f['size'] for f in files),'license':'Vedi la licenza del modello originale.',
                'ram_gb':round(sum(f['size'] for f in files)/1024**3+2,1),'max_refs':4})
        except (OSError,ValueError): continue
    return result


def inspect_model(root, model):
    files={e['role']:model_path(root,model,e['path']) for e in model['files']}
    if 'chat' not in model['capabilities']:
        ready=not model.get('external_problems') and all(e.get('valid',True) and model_path(root,model,e['path']).is_file() for e in model['files']) if model.get('external') else model_ready(root,model)
        return {'ready':ready,'complete':ready}
    base=files.get('model'); info=metadata(base) if base else {}
    projector=None; warning=''; candidates=[]
    if 'mmproj' in files:
        p=files['mmproj']
        entry=next(e for e in model['files'] if e['role']=='mmproj')
        if p.is_file() and p.stat().st_size==entry['size'] and metadata(p): projector=p
    if model.get('local') and base and (not model.get('external') or model.get('projector_mode','auto')=='auto'):
        candidates=[p for p in sorted(base.parent.glob('*.gguf')) if 'mmproj' in p.name.lower() and (model.get('external') or p.resolve().is_relative_to(Path(root).resolve())) and metadata(p).get('general.architecture')=='clip']
        weights=[p for p in base.parent.glob('*.gguf') if 'mmproj' not in p.name.lower() and not re.search(r'-(?!00001)\d{5}-of-\d{5}\.gguf$',p.name)]
        if len(weights)>1 and not model.get('external'):
            warning='Più modelli nella cartella: usa una cartella separata per ogni LLM e il suo mmproj.'
        elif len(candidates)==1: projector=candidates[0]
        elif len(candidates)>1: warning='Più mmproj nella cartella: scegli il proiettore compatibile in Modifica collegamento.' if model.get('external') else 'Più mmproj nella cartella: conserva solo il proiettore compatibile con questo modello.'
    if model.get('external') and model.get('projector_mode')=='off':
        projector=None;warning='Vision disattivata per questo collegamento. Il modello usa solo testo.'
    expected='vision' in model['capabilities']
    if not projector and not warning:
        warning='Modello non vision: mmproj assente. Puoi scrivere testo, ma il modello non può leggere le immagini.'
        if expected: warning='Vision non attiva: scarica o ripristina il mmproj di questo modello. Al momento funziona solo il testo.'
    # Installed catalog weights retain their verified marker even if the projector was removed.
    ready=bool(info) if model.get('local') else model_ready(root,model)
    if not ready and info and not model.get('local'):
        try:
            verified=json.loads((Path(root)/'models'/(model['id']+'.ready.json')).read_text())['files']
            entry=next(e for e in model['files'] if e['role']=='model')
            ready=({'path':entry['path'],'size':entry['size'],'sha256':entry['sha256']} in verified and base.stat().st_size==entry['size'])
        except (OSError,ValueError,KeyError): pass
    template=info.get('tokenizer.chat_template','')
    supported=any(s in template for s in ('enable_thinking','reasoning_effort','<think>','[THINK]','<|channel|>analysis'))
    # Before download, the two Qwen3 catalog entries have documented switchable thinking.
    if not info and model['id'] in ('qwen3-06','qwen3-4'): supported=True
    thinking={'supported':supported,'mode':'native' if 'reasoning_effort' in template else 'budget',
              'native_xhigh':bool(re.search(r'[\'"]xhigh[\'"]',template)),
              'note':'Livelli tramite budget di token; il limite di risposta comprende anche il thinking.' if supported else 'Questo modello non espone un template thinking compatibile.'}
    arch=info.get('general.architecture','')
    params={key:info.get(arch+'.'+suffix) for key,suffix in {
        'layers':'block_count','embedding':'embedding_length','heads':'attention.head_count',
        'kv_heads':'attention.head_count_kv','key_length':'attention.key_length','value_length':'attention.value_length'}.items()}
    if model.get('local') and int(info.get('split.count',1))>sum(e['role'] in ('model','shard') for e in model['files']): ready=False
    if model.get('external') and model.get('external_problems'): ready=False
    return {'ready':ready, 'complete':ready if model.get('local') else model_ready(root,model), 'vision':{'enabled':bool(projector),'expected':expected,
            'projector':(str(projector.resolve()) if model.get('external') else projector.relative_to(Path(root).resolve()).as_posix()) if projector else None,
            'projector_size':projector.stat().st_size if projector else 0,
            'warning':warning, 'max_refs':max(1,model.get('max_refs',4)) if projector else 0},
            'thinking':thinking,'parameters':params,'mtp':inspect_mtp(root,model,info,ready)}


def thinking_parameters(model, settings, router=False):
    traits=model.get('thinking',{})
    level=settings.get('think_level','off') if traits.get('supported') and not router else 'off'
    if level not in THINK_LEVELS: raise ValueError('Livello thinking non valido.')
    enabled=level!='off'
    fractions={'low':.125,'med':.25,'high':.5,'xhigh':.75}
    limit=int(settings['max_tokens'])
    budget=min(int(limit*fractions.get(level,0)),max(0,limit-min(256,limit//4)))
    body={'chat_template_kwargs':{'enable_thinking':enabled},'reasoning_format':'deepseek',
          'reasoning_budget_tokens':budget}
    if not enabled: body['reasoning_effort']='none'
    elif traits.get('mode')=='native':
        body['reasoning_effort']={'med':'medium','xhigh':'xhigh' if traits.get('native_xhigh') else 'high'}.get(level,level)
    return body

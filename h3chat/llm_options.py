"""Per-LLM generation presets, with flat active values for engine snapshots."""
import copy
import math

KEYS=('context','max_tokens','temperature','think_level','gpu_layers','mtp_enabled','mtp_draft_tokens','prompt_max_tokens','music_prompt_max_tokens')
BASE={'context':4096,'max_tokens':1024,'temperature':.7,'think_level':'off','gpu_layers':20,'mtp_enabled':False,'mtp_draft_tokens':3,'prompt_max_tokens':2200,'music_prompt_max_tokens':2200}
MAX_CONTEXT=2**31-1

def defaults(profile):
    return BASE|({'context':8192,'gpu_layers':99} if profile=='balanced' else {'gpu_layers':0} if profile=='cpu' else {})

def validate(values):
    if not isinstance(values,dict) or set(values)-set(KEYS):raise ValueError('Parametri del preset LLM non validi.')
    for key,lo,hi in (('context',1024,MAX_CONTEXT),('max_tokens',64,8192),('gpu_layers',0,999),('mtp_draft_tokens',1,8),('prompt_max_tokens',256,8192),('music_prompt_max_tokens',256,8192)):
        if key in values and (type(values[key]) is not int or not lo<=values[key]<=hi):raise ValueError(f'{key}: inserisci un intero tra {lo} e {hi}.')
    if 'temperature' in values and (type(values['temperature']) not in (int,float) or not math.isfinite(values['temperature']) or not 0<=values['temperature']<=2):raise ValueError('Temperatura LLM fuori intervallo.')
    if 'think_level' in values and values['think_level'] not in ('off','low','med','high','xhigh'):raise ValueError('Thinking LLM non valido.')
    if 'mtp_enabled' in values and type(values['mtp_enabled']) is not bool:raise ValueError('MTP: scegli attivato o disattivato.')
    if values.get('max_tokens',64)>values.get('context',MAX_CONTEXT)//2:raise ValueError('I token di risposta non possono superare metà del contesto.')

def validate_presets(presets,profile):
    if not isinstance(presets,dict) or len(presets)>200:raise ValueError('Preset LLM non validi.')
    for ident,values in presets.items():
        if not isinstance(ident,str) or not 1<=len(ident)<=150:raise ValueError('Identificativo preset LLM non valido.')
        validate(values)
        validate(defaults(profile)|values)

def merge(current,patch):
    result=current|patch
    presets=copy.deepcopy(patch.get('llm_overrides',current.get('llm_overrides',{})))
    before=current.get('chat_model','');selected=result.get('chat_model','')
    if before!=selected:
        if before and before not in presets:presets[before]={k:current[k] for k in KEYS}
        active=defaults(result['profile'])|presets.get(selected,{})
    else:
        active={k:current[k] for k in KEYS}
        if 'llm_overrides' in patch and selected in presets:active=defaults(result['profile'])|presets[selected]
    changed_preset='llm_overrides' in patch and presets.get(selected)!=current.get('llm_overrides',{}).get(selected)
    for key in KEYS:
        if key in patch and not (changed_preset and patch[key]==current[key]):active[key]=patch[key]
    if selected:presets[selected]=dict(active)
    return result|active|{'llm_overrides':presets}

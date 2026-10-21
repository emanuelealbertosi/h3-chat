"""Explicit per-request attention controls; no inference or preset mutation."""
import re


def prompt_choice(prompt):
    """Only explicit video requests call this; never parse ordinary chat."""
    values=set(re.findall(r'\bveda[ \t]+(8|56)\b',prompt,re.I))
    if len(values)>1:raise ValueError('Scegli una sola modalità: VEDA 8 oppure VEDA 56.')
    choices=set()
    for match in re.finditer(r'(?im)^\s*accelerazione\s*:\s*(nessuna|off|pytorch|sage(?:attention)?|comfy\s*kitchen(?:\s+int8)?|auto|veda)\s*[.!]?\s*$',prompt):
        name=re.sub(r'\s','',match[1].lower())
        choices.add('pytorch' if name in ('nessuna','off','pytorch') else 'sage' if name.startswith('sage') else 'comfy_kitchen' if name.startswith('comfykitchen') else name)
    if re.search(r'(?im)^\s*(?:no accelerazione|nessuna accelerazione)\s*[.!]?\s*$',prompt):choices.add('pytorch')
    if len(choices)>1 or (values and choices-{'veda'}):raise ValueError('Scegli una sola accelerazione video.')
    if values:return {'attention':'veda','attention_chunks':int(values.pop()),'attention_chunks_mode':'manual'}
    if choices:return {'attention':choices.pop(),'attention_chunks':0,'attention_chunks_mode':'auto'}
    return {}


def validate(parameters):
    mode=parameters.get('attention_chunks_mode','auto')
    if mode not in ('auto','manual'):raise ValueError('Gruppi attenzione: scegli automatici o espliciti.')
    if mode=='manual' and (parameters.get('attention')!='veda' or parameters.get('attention_chunks') not in (8,56)):
        raise ValueError('Scelta esplicita: usa VEDA 8 oppure VEDA 56.')

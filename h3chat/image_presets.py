"""Named MOSS recipes; saving a library never changes generation defaults."""
import re
from .image_options import validate_overrides, options, MOSS_NEGATIVE_PROMPT

MOSS_RECIPES = (
    {'id':'moss-official','name':'Ufficiale','parameters':{
        'steps':50,'cfg':3,'sampler':'euler','scheduler':'sgm_uniform','negative_prompt':MOSS_NEGATIVE_PROMPT},
     'description':'Campionamento ufficiale: Euler / sgm_uniform · 50 passi · CFG 3. Negativo generale dell’app modificabile; mantiene megapixel, formato e seed attuali.'},
    {'id':'moss-fizgig','name':'Fizgig','parameters':{
        'steps':30,'cfg':4,'sampler':'res_multistep','scheduler':'simple','negative_prompt':MOSS_NEGATIVE_PROMPT},
     'description':'res_multistep / simple · 30 passi · CFG 4. Alternativa sperimentale con negativo generale modificabile; mantiene megapixel, formato e seed attuali.'},
)


def validate_presets(value, settings):
    if not isinstance(value,list) or len(value)>50:
        raise ValueError('Puoi salvare al massimo 50 preset MOSS.')
    ids=set();names={x['name'].casefold() for x in MOSS_RECIPES}
    model={'id':'moss','architecture':'moss','engine':'vision','width':1024,'height':1024,
           'steps':50,'cfg':3,'sampler':'euler','scheduler':'sgm_uniform','strength':1}
    for item in value:
        if not isinstance(item,dict) or set(item)!={'id','name','parameters'}:
            raise ValueError('Preset MOSS non valido.')
        ident,name=item['id'],item['name']
        if not isinstance(ident,str) or not re.fullmatch(r'[a-f0-9]{32}',ident) or ident in ids:
            raise ValueError('Identificativo preset MOSS non valido.')
        if not isinstance(name,str) or not 1<=len(name)<=80 or name!=name.strip() or any(ord(c)<32 for c in name) or name.casefold() in names:
            raise ValueError('Usa un nome unico di massimo 80 caratteri; Ufficiale e Fizgig sono riservati.')
        parameters=item['parameters']
        if not isinstance(parameters,dict) or not parameters:
            raise ValueError('Il preset deve contenere i parametri MOSS.')
        validate_overrides({'moss':parameters},{'moss':model})
        options(model,settings|{'image_overrides':{'moss':parameters}})
        ids.add(ident);names.add(name.casefold())

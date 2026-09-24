"""YuE2 defaults and limits from H3-Music; requests capture their own settings."""
import math
import secrets

NUMBERS = {
 'cfg_scale':(0,20,1.0), 'num_inference_steps':(1,128,32),
 'abc_temperature':(0,5,.7), 'abc_top_p':(.001,1,.9), 'abc_top_k':(1,1000,30),
 'abc_repetition_penalty':(.01,10,1.005), 'abc_penalty_window':(1,10000,100),
 'abc_min_tokens':(0,4096,32), 'abc_max_tokens':(32,8192,4096),
 'semantic_temperature':(0,5,1), 'semantic_top_p':(.001,1,.95), 'semantic_top_k':(1,1000,100),
 'semantic_repetition_penalty':(.01,10,1.2), 'semantic_penalty_window':(1,10000,50),
 'semantic_min_tokens':(0,9000,200), 'semantic_max_tokens':(200,12000,9000),
}
INTEGER = {'num_inference_steps'} | {k for k in NUMBERS if any(s in k for s in ('top_k','window','tokens'))}
DEFAULTS = {k:v[2] for k,v in NUMBERS.items()} | {'cot':'full','seed':831001}


def validate(value, *, partial=False):
 if not isinstance(value,dict) or set(value)-set(DEFAULTS):raise ValueError('Parametri musica non riconosciuti.')
 result=DEFAULTS|value
 if result['cot'] not in ('off','melody','full'):raise ValueError('Pianificazione musicale non valida.')
 if type(result['seed']) is not int or not -1<=result['seed']<2**53:raise ValueError('Seed musica: usa -1 oppure un intero tra 0 e 2^53-1.')
 for k,(lo,hi,_) in NUMBERS.items():
  v=result[k]
  if type(v) not in (int,float) or not math.isfinite(v) or not lo<=v<=hi or (k in INTEGER and type(v) is not int):raise ValueError('Parametro musica fuori intervallo: '+k)
 for prefix in ('abc','semantic'):
  if result[prefix+'_min_tokens']>result[prefix+'_max_tokens']:raise ValueError('Musica: il limite massimo di token deve essere maggiore del minimo.')
 return dict(value) if partial else result


def options(model,settings,*,randomize=True):
 value=validate(settings.get('music_overrides',{}).get(model['id'],{}))
 if randomize and value['seed']==-1:value['seed']=secrets.randbelow(2**31)
 return value


def validate_fields(value):
 if not isinstance(value,dict) or set(value)-{'title','style','lyrics','abc','instrumental'}:raise ValueError('Campi della canzone non validi.')
 result={}
 for key,limit in (('title',120),('style',4000),('lyrics',16000),('abc',50000)):
  v=value.get(key,'')
  if not isinstance(v,str) or len(v)>limit:raise ValueError('Musica: '+key+' troppo lungo o non valido.')
  result[key]=v.strip()
 if type(value.get('instrumental',False)) is not bool:raise ValueError('Scegli se il brano è strumentale.')
 result['instrumental']=value.get('instrumental',False)
 return result

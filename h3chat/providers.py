"""User-configured Chat Completions endpoints; keys never enter model metadata."""
import base64
import ctypes as C
import ipaddress
import json
import os
import re
from urllib.parse import urlsplit,urlunsplit
from .store import uid

PRESETS={
    'deepseek':{'name':'DeepSeek','base_url':'https://api.deepseek.com','model':'deepseek-flash','format':'json_object','thinking':'deepseek'},
    'openrouter':{'name':'OpenRouter','base_url':'https://openrouter.ai/api/v1','model':'','format':'json_object','thinking':'openrouter'},
    'custom':{'name':'Personalizzato · Chat Completions','base_url':'','model':'','format':'json_object','thinking':'none'},
}

class Blob(C.Structure):
    _fields_=[('size',C.c_ulong),('data',C.POINTER(C.c_ubyte))]

def endpoint(value):
    if not isinstance(value,str) or len(value)>2000 or any(ord(c)<33 for c in value):raise ValueError('Indirizzo API non valido.')
    p=urlsplit(value)
    try:port=p.port
    except ValueError:raise ValueError('Porta API non valida.')
    if p.scheme not in ('http','https') or not p.hostname or p.username or p.password or p.query or p.fragment or port==0:
        raise ValueError('Usa un indirizzo base API http/https, senza credenziali o query.')
    local=p.hostname.lower()=='localhost'
    try:
        address=ipaddress.ip_address(p.hostname)
        local=local or address.is_loopback or any(address in ipaddress.ip_network(net) for net in ('10.0.0.0/8','172.16.0.0/12','192.168.0.0/16') if address.version==4)
    except ValueError:pass
    if p.scheme=='http' and not local:raise ValueError('Per servizi esterni usa HTTPS. HTTP è consentito per localhost o indirizzi IP della rete privata.')
    path=p.path.rstrip('/')
    if path.endswith('/chat/completions'):path=path[:-len('/chat/completions')]
    return urlunsplit((p.scheme,p.netloc,path,'',''))

def protect(value,decode=False):
    # This application is distributed for Windows: DPAPI binds keys to the OS user.
    if not value:return ''
    if os.name!='nt':raise ValueError('La protezione delle chiavi API richiede Windows.')
    raw=base64.b64decode(value) if decode else value.encode('utf-8')
    buffer=C.create_string_buffer(raw);source=Blob(len(raw),C.cast(buffer,C.POINTER(C.c_ubyte)));target=Blob()
    function=C.windll.crypt32.CryptUnprotectData if decode else C.windll.crypt32.CryptProtectData
    function.argtypes=[C.POINTER(Blob),C.c_void_p,C.c_void_p,C.c_void_p,C.c_void_p,C.c_ulong,C.POINTER(Blob)]
    function.restype=C.c_int
    if not function(C.byref(source),None,None,None,None,1,C.byref(target)):
        raise ValueError('Chiave API non accessibile per questo utente Windows. Inseriscila di nuovo nelle impostazioni.')
    try:
        data=C.string_at(target.data,target.size)
        return data.decode('utf-8') if decode else base64.b64encode(data).decode('ascii')
    finally:
        C.windll.kernel32.LocalFree.argtypes=[C.c_void_p];C.windll.kernel32.LocalFree(C.cast(target.data,C.c_void_p))

def validate(body,ident=None):
    allowed={'id','name','base_url','model','vision','max_refs','thinking','format','api_key','clear_key','preset'}
    if not isinstance(body,dict) or set(body)-allowed:raise ValueError('Configurazione provider non valida.')
    if any(not isinstance(body.get(k,''),str) for k in ('name','model')):raise ValueError('Nome e modello API devono essere testo.')
    if body.get('id') is not None and (not isinstance(body['id'],str) or not re.fullmatch(r'api-[a-f0-9]{32}',body['id'])):raise ValueError('Identificativo provider non valido.')
    result={'id':ident or 'api-'+uid(),'name':body.get('name','').strip(),'base_url':endpoint(body.get('base_url','')),
            'model':body.get('model','').strip(),'vision':body.get('vision',False),'max_refs':body.get('max_refs',4),
            'thinking':body.get('thinking','none'),'format':body.get('format','json_object')}
    preset=body.get('preset','custom');result['preset']=preset if isinstance(preset,str) and preset in PRESETS else 'custom'
    for key,limit in (('name',100),('model',200)):
        if not isinstance(result[key],str) or not 1<=len(result[key])<=limit or any(ord(c)<32 for c in result[key]):raise ValueError('Inserisci nome del collegamento e ID modello API.')
    if result['thinking'] not in ('none','deepseek','openrouter','effort') or result['format'] not in ('json_object','json_schema','prompt'):raise ValueError('Thinking o formato JSON del provider non valido.')
    if type(result['vision']) is not bool or type(result['max_refs']) is not int or not 1<=result['max_refs']<=9:raise ValueError('Vision: scegli attivo/disattivo e da 1 a 9 riferimenti.')
    key=body.get('api_key','')
    if not isinstance(key,str) or len(key)>8192 or any(ord(c)<33 or ord(c)>126 for c in key):raise ValueError('Chiave API non valida: usa il token senza spazi.')
    if type(body.get('clear_key',False)) is not bool:raise ValueError('Opzione chiave non valida.')
    return result,key

class Providers:
    def __init__(self,store):self.store=store
    def list(self):
        return [json.loads(row['config'])|{'has_key':bool(row['secret'])} for row in self.store.all('SELECT config,secret FROM api_providers ORDER BY id')]
    def resolve(self,body):
        if not isinstance(body,dict):raise ValueError('Configurazione provider non valida.')
        validate(body,body.get('id'))
        ident=body.get('id');row=self.store.one('SELECT config,secret FROM api_providers WHERE id=?',(ident,)) if ident else None
        if ident and not row:raise ValueError('Provider non trovato.')
        config,key=validate(body,ident)
        if key:secret=protect(key)
        elif row and not body.get('clear_key'):
            if endpoint(json.loads(row['config'])['base_url'])!=config['base_url']:raise ValueError('Indirizzo cambiato: inserisci nuovamente la chiave API oppure scegli Rimuovi chiave.')
            secret=row['secret']
        else:secret=''
        return config,secret
    def save(self,body):
        config,secret=self.resolve(body)
        self.store.execute('INSERT OR REPLACE INTO api_providers VALUES (?,?,?)',(config['id'],json.dumps(config),secret))
        return config|{'has_key':bool(secret)}
    def credentials(self,ident):
        row=self.store.one('SELECT config,secret FROM api_providers WHERE id=?',(ident,))
        if not row:raise ValueError('Provider non trovato. Controlla le impostazioni API.')
        return json.loads(row['config']),protect(row['secret'],decode=True)
    def model(self,config):
        return {'id':config['id'],'name':config['name']+' · '+config['model']+' · API','api':True,'api_config':config,
                'local':True,'files':[],'capabilities':['chat'],'max_refs':config['max_refs'],'size':0,'ram_gb':0,
                'description':'Chat, router e Assistant tramite il provider API scelto. Conversazione ed eventuali riferimenti vengono inviati al servizio.',
                'license':'Condizioni e tariffe del provider API.'}

def traits(model):
    config=model['api_config'];vision=config['vision'];thinking=config['thinking']!='none'
    note=('DeepSeek: low → low, med/high → high, xhigh → max; Off disattiva thinking.' if config['thinking']=='deepseek' else
          'Il provider traduce i livelli di reasoning; supporto e limiti dipendono dal modello scelto.')
    return {'ready':True,'complete':True,'vision':{'enabled':vision,'expected':vision,'projector':None,'projector_size':0,
            'warning':'' if vision else 'Vision non abilitata per questo modello API. Attivala nel collegamento solo se il modello accetta immagini.', 'max_refs':config['max_refs'] if vision else 0},
            'thinking':{'supported':thinking,'mode':'api','note':note if thinking else 'Thinking non configurato per questo provider.'},
            'parameters':{'context_length':None},'mtp':{'supported':False,'note':'MTP e layer GPU sono gestiti dal provider, non dal PC.'}}

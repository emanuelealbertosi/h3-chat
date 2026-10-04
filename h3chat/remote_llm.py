"""Bounded, cancellable Chat Completions transport; no redirects or key logging."""
import json
import queue
import socket
import threading
import time
import urllib.error
import urllib.request
from .downloads import Cancelled

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):raise ValueError('Il provider reindirizza la richiesta. Imposta direttamente il suo indirizzo API finale.')

def check_schema(value,schema):
    kind=schema.get('type');types={'object':dict,'array':list,'string':str,'boolean':bool,'integer':int,'number':(int,float),'null':type(None)}
    if kind and (not isinstance(value,types[kind]) or kind in ('integer','number') and isinstance(value,bool)):raise ValueError('Risposta API non conforme allo schema JSON richiesto.')
    if 'enum' in schema and value not in schema['enum']:raise ValueError('Valore API fuori dallo schema JSON.')
    if isinstance(value,dict):
        if set(schema.get('required',[]))-set(value):raise ValueError('La risposta API JSON è incompleta.')
        props=schema.get('properties',{})
        if schema.get('additionalProperties') is False and set(value)-set(props):raise ValueError('Campi API JSON non previsti.')
        for key,item in value.items():
            if key in props:check_schema(item,props[key])
    if isinstance(value,list):
        if len(value)<schema.get('minItems',0) or len(value)>schema.get('maxItems',1000000):raise ValueError('Numero di elementi API JSON non valido.')
        for item in value:check_schema(item,schema.get('items',{}))
    if type(value) in (int,float) and not schema.get('minimum',float('-inf'))<=value<=schema.get('maximum',float('inf')):raise ValueError('Valore numerico API JSON non valido.')

def request_body(config,messages,settings,stream,schema):
    body={'model':config['model'],'messages':[dict(m) for m in messages],'max_tokens':settings['max_tokens'] if stream or not schema else 768,'stream':stream}
    level=settings.get('think_level','off') if stream else 'off';mode=config['thinking']
    if mode=='deepseek':
        body['thinking']={'type':'disabled' if level=='off' else 'enabled'}
        body['reasoning_effort']={'off':'none','low':'low','med':'high','high':'high','xhigh':'max'}[level]
    elif mode=='openrouter':body['reasoning']={'effort':{'off':'none','med':'medium'}.get(level,level)}
    elif mode=='effort':body['reasoning_effort']={'off':'none','med':'medium'}.get(level,level)
    if mode=='none' or level=='off':body['temperature']=settings['temperature']
    if schema:
        body['messages']=[{'role':'system','content':'Return only a JSON object following this JSON schema. No Markdown fences or commentary.\n'+json.dumps(schema,ensure_ascii=False)}]+body['messages']
        if config['format']=='json_schema':body['response_format']={'type':'json_schema','json_schema':{'name':'h3_output','strict':True,'schema':schema}}
        elif config['format']=='json_object':body['response_format']={'type':'json_object'}
    return body

class Client:
    def __init__(self):self.lock=threading.Lock();self.requests={}
    def abort(self):
        with self.lock:items=list(self.requests.items())
        for stop,response in items:
            stop.set()
            if response:
                try:response.fp.raw._sock.shutdown(socket.SHUT_RDWR)
                except (AttributeError,OSError):pass
    def exchange(self,config,key,cancel,*,body=None,path='/models',on_event=None,timeout=300,max_bytes=4*1024**2,content_type='application/json'):
        if cancel.is_set():raise Cancelled()
        events=queue.Queue(maxsize=64);stop=threading.Event();deadline=time.monotonic()+timeout
        def emit(kind,value):
            while not stop.is_set():
                try:events.put((kind,value),timeout=.1);return
                except queue.Full:pass
        def work():
            response=None
            with self.lock:self.requests[stop]=None
            try:
                headers={'Accept':'text/event-stream, application/json','Content-Type':content_type,'User-Agent':'H3-Chat'}
                if key:headers['Authorization']='Bearer '+key
                request=urllib.request.Request(config['base_url']+path,data=None if body is None else body if isinstance(body,bytes) else json.dumps(body,ensure_ascii=False).encode('utf-8'),headers=headers)
                response=urllib.request.build_opener(NoRedirect()).open(request,timeout=min(timeout,300))
                with self.lock:self.requests[stop]=response
                if stop.is_set():return
                if isinstance(body,dict) and body.get('stream'):
                    while not stop.is_set():
                        line=response.readline(2*1024**2+1)
                        if len(line)>2*1024**2:raise ValueError('Evento API troppo grande.')
                        if not line:break
                        if line.startswith(b'data:'):
                            raw=line[5:].strip()
                            if raw==b'[DONE]':break
                            if raw:emit('event',json.loads(raw))
                    emit('done',None)
                else:
                    raw=response.read(max_bytes+1)
                    if len(raw)>max_bytes:raise ValueError('Risposta API troppo grande.')
                    emit('result',json.loads(raw))
            except urllib.error.HTTPError as exc:
                # Providers may echo headers or request text. Never persist their raw errors.
                labels={400:'Richiesta o parametri non supportati: verifica modello, Vision, thinking e formato JSON.',401:'Chiave API non valida.',403:'Accesso al modello non consentito.',404:'Indirizzo API o modello non trovato.',429:'Limite richieste o credito del provider: riprova più tardi.'}
                emit('error',RuntimeError('Provider API '+str(exc.code)+': '+labels.get(exc.code,'Servizio non disponibile. Riprova più tardi.')))
                exc.close()
            except Exception as exc:
                message=str(exc).replace(key,'[chiave]') if key else str(exc)
                emit('error',RuntimeError('Connessione API: '+message[:400]))
            finally:
                if response:response.close()
                with self.lock:self.requests.pop(stop,None)
        worker=threading.Thread(target=work,daemon=True);worker.start()
        try:
            while True:
                if cancel.is_set() or stop.is_set():raise Cancelled()
                if time.monotonic()>deadline:raise RuntimeError('Il provider API non ha completato la richiesta entro il limite di tempo.')
                try:kind,value=events.get(timeout=.1)
                except queue.Empty:continue
                if kind=='error':raise value
                if kind=='result':return value
                if kind=='done':return None
                if on_event:on_event(value)
        finally:
            stop.set()
            with self.lock:response=self.requests.get(stop)
            if response:
                try:response.fp.raw._sock.shutdown(socket.SHUT_RDWR)
                except (AttributeError,OSError):pass
    def completion(self,config,key,messages,settings,cancel,on_text=None,schema=None,on_reasoning=None):
        body=request_body(config,messages,settings,on_text is not None,schema);content='';finish=None
        def event(value):
            nonlocal content,finish
            if value.get('error'):raise RuntimeError('Il provider ha segnalato un errore durante la risposta. Controlla modello e credito API.')
            choices=value.get('choices') or []
            if not choices:return
            delta=choices[0].get('delta',{})
            if (delta.get('reasoning_content') or delta.get('reasoning')) and on_reasoning:on_reasoning()
            piece=delta.get('content') or ''
            if not isinstance(piece,str):raise ValueError('Formato dello stream API non supportato.')
            content+=piece
            if len(content)>1000000:raise ValueError('Risposta API troppo lunga.')
            finish=choices[0].get('finish_reason') or finish
            if on_text:on_text(content)
        value=self.exchange(config,key,cancel,body=body,path='/chat/completions',on_event=event,timeout=settings.get('llm_timeout',1800))
        if on_text is None:
            try:content=value['choices'][0]['message']['content'];finish=value['choices'][0].get('finish_reason')
            except (KeyError,IndexError,TypeError):raise RuntimeError('Risposta API non compatibile con Chat Completions.')
        if not isinstance(content,str) or not content.strip():raise RuntimeError('Il provider ha restituito una risposta vuota.')
        if finish is None:raise RuntimeError('Il provider ha interrotto la risposta prima di completarla.')
        if finish not in ('stop','length'):raise RuntimeError('Risposta API non completata: '+str(finish)[:60])
        if schema and finish!='length':
            try:parsed=json.loads(content);check_schema(parsed,schema)
            except (ValueError,TypeError,KeyError):raise ValueError('Il provider non ha rispettato il formato JSON richiesto per router, Assistant o canvas. Cambia formato JSON nelle impostazioni API o scegli un altro modello.')
        return (content,finish) if on_text else content

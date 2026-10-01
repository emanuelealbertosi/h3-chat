"""Authenticated optional H3 endpoint; exposes inference, never filesystem/admin APIs."""
import base64
import json
import secrets
import threading
import time
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from .store import DEFAULTS
from .downloads import safe_join
from .video_options import validate_plan
from .music_options import validate_fields

class MediaServer:
    def __init__(self,app):self.app=app;self.server=None;self.key='';self.lock=threading.RLock()
    def status(self):return {'running':self.server is not None,'host':self.server.server_address[0] if self.server else '', 'port':self.server.server_port if self.server else None}
    def start(self,body):
        with self.lock:
            if self.server:raise ValueError('Il server è già attivo.')
            host=body.get('host','127.0.0.1');port=body.get('port',8790)
            if host not in ('127.0.0.1','0.0.0.0') or type(port) is not int or not 1024<=port<=65535:raise ValueError('Indirizzo o porta server non validi.')
            key=body.get('api_key') or secrets.token_urlsafe(32)
            if not isinstance(key,str) or not 24<=len(key)<=200 or any(ord(c)<33 or ord(c)>126 for c in key):raise ValueError('Token server: almeno 24 caratteri senza spazi.')
            server=ThreadingHTTPServer((host,port),RemoteHandler);server.daemon_threads=True;server.app=self.app;server.secret=key
            self.server=server;self.key=key;threading.Thread(target=server.serve_forever,daemon=True).start()
            return self.status()|{'api_key':key}
    def close(self):
        with self.lock:
            server=self.server;self.server=None;self.key=''
        if server:
            server.shutdown();server.server_close()
            for job in self.app.store.all("SELECT id FROM jobs WHERE status IN ('queued','running') AND json_extract(payload,'$.settings._remote_job')=1"):self.app.cancel(job['id'])
    def enqueue(self,body):
        app=self.app;task=body.get('task');model_id=body.get('model');device=body.get('device','gpu');cap='edit' if task=='edit' else 'create' if task=='create' else task
        if task not in ('create','edit','music','video') or device not in ('cpu','gpu') or task=='video' and device!='gpu':raise ValueError('Modalità generazione non valida.')
        app.refresh_models();model=app.engine.require_model(model_id,cap)
        if model.get('remote_media'):raise ValueError('Il server H3 richiede un modello standalone locale.')
        assets=body.get('assets',[])
        if not isinstance(assets,list) or len(assets)>12:raise ValueError('Troppi allegati.')
        media=[app.upload(asset) for asset in assets]
        if task=='edit' and not media:raise ValueError('Allega un’immagine per l’edit.')
        prompt=body.get('prompt','')
        if not isinstance(prompt,str) or len(prompt)>24000:raise ValueError('Prompt non valido.')
        parameters=body.get('parameters',{})
        if not isinstance(parameters,dict):raise ValueError('Parametri non validi.')
        patch={}
        if task in ('create','edit'):patch.update(create_model=model_id,edit_model=model_id,image_device=device,image_overrides={model_id:parameters})
        elif task=='music':patch.update(music_model=model_id,music_backend='cpu' if device=='cpu' else 'cuda',music_overrides={model_id:parameters})
        else:patch.update(video_model=model_id,video_overrides={model_id:parameters})
        settings=app.validate_settings(patch)|{'_assistant':False,'_web':False,'_transcribe':False,'_rag':False,'_remote_job':True,'_image_model':model_id if task in ('create','edit') else '', '_music':task=='music','_video':task=='video'}
        if task=='music':settings['_music_fields']=validate_fields(body.get('composition') or {});prompt=prompt or 'Genera musica'
        if task=='video':
            if body.get('plan'):
                from .video_options import options
                settings['_video_plan']=validate_plan(body['plan'],media,options(model,settings,False)['duration'])
            prompt=prompt or 'Crea un video'
        with app.lock:
            if app.store.one("SELECT id FROM jobs WHERE status IN ('queued','running')"):raise ValueError('Server occupato. Attendi il lavoro corrente e riprova.')
            chat=app.store.create_chat('Server · '+task);ident=app.store.enqueue(chat['id'],prompt or 'Crea immagine',media,settings);app.wake.set()
        return {'id':ident,'status':'queued'}
    def llm(self,body):
        app=self.app;messages=body.get('messages');model_id=body.get('model')
        if not isinstance(messages,list) or not 1<=len(messages)<=200:raise ValueError('Messaggi non validi.')
        for m in messages:
            if not isinstance(m,dict) or m.get('role') not in ('system','user','assistant') or not isinstance(m.get('content'),(str,list)):raise ValueError('Formato messaggi non supportato.')
            if isinstance(m['content'],list):
                for part in m['content']:
                    if part.get('type')=='image_url' and not re_image(part.get('image_url',{}).get('url','')):raise ValueError('Vision accetta solo immagini data URL, senza download esterni.')
        app.refresh_models();model=app.engine.require_model(model_id,'chat')
        if model.get('api'):raise ValueError('Il server LLM richiede un modello standalone locale.')
        patch={'chat_model':model_id,'max_tokens':body.get('max_tokens',1024),'temperature':body.get('temperature',.7)}
        effort=body.get('reasoning_effort')
        if effort is not None:
            levels={'none':'off','off':'off','low':'low','medium':'med','med':'med','high':'high','xhigh':'xhigh','max':'xhigh'}
            if not isinstance(effort,str) or effort not in levels:raise ValueError('Livello thinking non supportato.')
            patch['think_level']=levels[effort]
        settings=app.validate_settings(patch)
        schema=None;fmt=body.get('response_format',{})
        if fmt.get('type')=='json_schema':schema=fmt.get('json_schema',{}).get('schema')
        elif fmt.get('type')=='json_object':schema={'type':'object'}
        settings.update(_api_messages=messages,_api_schema=schema,_remote_job=True)
        with app.lock:
            if app.store.one("SELECT id FROM jobs WHERE status IN ('queued','running')"):raise ValueError('Server occupato.')
            chat=app.store.create_chat('Server · LLM');ident=app.store.enqueue(chat['id'],'Richiesta LLM via server',[],settings);app.wake.set()
        return ident
    def job(self,ident):
        job=self.app.store.one("SELECT * FROM jobs WHERE id=? AND json_extract(payload,'$.settings._remote_job')=1",(ident,))
        if not job:raise ValueError('Lavoro non trovato.')
        return job

def re_image(value):return isinstance(value,str) and value.startswith(('data:image/png;base64,','data:image/jpeg;base64,')) and len(value)<=20*1024**2

class RemoteHandler(BaseHTTPRequestHandler):
    def log_message(self,*args):pass
    def json(self,value,status=200):
        data=json.dumps(value,ensure_ascii=False).encode();self.send_response(status);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(data)));self.send_header('Cache-Control','no-store');self.end_headers();self.wfile.write(data)
    def handle_request(self):
        try:
            if self.headers.get('Origin'):raise PermissionError('Il server accetta client API, non richieste browser da altri siti.')
            if not secrets.compare_digest(self.headers.get('Authorization',''),'Bearer '+self.server.secret):raise PermissionError('Token server non valido.')
            app=self.server.app;server=app.media_server;path=self.path
            if self.command=='GET' and path in ('/v1/h3/models','/v1/models'):
                models=[m for m in app.refresh_models() if m['ready'] and not m.get('api') and not m.get('remote_media')]
                return self.json({'data':[{'id':m['id'],'name':m['name'],'capabilities':m['capabilities']} for m in models]})
            if self.command=='GET' and path.startswith('/v1/h3/jobs/'):
                ident=path.split('/')[-1];job=server.job(ident);value={k:job[k] for k in ('id','status','stage')}
                if job['status']=='done':
                    message=app.store.one('SELECT media FROM messages WHERE id=?',(job['message_id'],));media=json.loads(message['media'])
                    if not media:raise ValueError('Output non disponibile.')
                    item=media[0];file=safe_join(app.data,item['path'])
                    if file.stat().st_size>90*1024**2:raise ValueError('Output oltre 90 MB.')
                    value['media']={k:item[k] for k in ('name','mime')};value['media'].update(data=base64.b64encode(file.read_bytes()).decode(),generation=item.get('generation',{}))
                return self.json(value)
            if self.command!='POST':return self.json({'error':'Endpoint non disponibile.'},404)
            length=int(self.headers.get('Content-Length','0'))
            if not 0<length<=90*1024**2:raise ValueError('Richiesta troppo grande.')
            body=json.loads(self.rfile.read(length))
            if not isinstance(body,dict):raise ValueError('Richiesta non valida.')
            if path=='/v1/h3/generations':return self.json(server.enqueue(body),202)
            if path.startswith('/v1/h3/jobs/') and path.endswith('/cancel'):
                ident=path.split('/')[-2];server.job(ident);return self.json(app.cancel(ident))
            if path=='/v1/chat/completions':
                ident=server.llm(body);stream=body.get('stream',False);sent='';deadline=time.monotonic()+1800
                if stream:self.send_response(200);self.send_header('Content-Type','text/event-stream');self.send_header('Cache-Control','no-store');self.end_headers()
                try:
                    while time.monotonic()<deadline:
                        job=server.job(ident);m=app.store.one('SELECT content,meta FROM messages WHERE id=?',(job['message_id'],));text=m['content']
                        if stream and text!=sent:
                            event={'choices':[{'delta':{'content':text[len(sent):]},'finish_reason':None}]};self.wfile.write(('data: '+json.dumps(event)+'\n\n').encode());self.wfile.flush();sent=text
                        if job['status']=='done':
                            finish=json.loads(m['meta']).get('finish_reason','stop')
                            if stream:self.wfile.write(('data: '+json.dumps({'choices':[{'delta':{},'finish_reason':finish}]})+'\n\ndata: [DONE]\n\n').encode());self.wfile.flush();return
                            return self.json({'choices':[{'message':{'role':'assistant','content':text},'finish_reason':finish}]})
                        if job['status'] in ('failed','cancelled','interrupted'):raise ValueError('Il motore LLM ha interrotto la richiesta.')
                        time.sleep(.15)
                    raise ValueError('Tempo massimo della richiesta superato.')
                except Exception:
                    app.cancel(ident)
                    if stream:self.wfile.write(b'data: {"error":{"message":"Generazione interrotta sul server"}}\n\n');return
                    raise
            return self.json({'error':'Endpoint non disponibile.'},404)
        except (BrokenPipeError,ConnectionResetError):pass
        except PermissionError as e:self.json({'error':str(e)},403)
        except Exception as e:self.json({'error':str(e)},400)
    do_GET=do_POST=handle_request

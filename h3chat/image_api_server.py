"""Loopback AUTOMATIC1111 adapter for the authenticated H3 inference API.

No model processes or app databases are opened here. The existing H3 queue
owns generation, presets, output storage and cancellation.
"""
import base64
import binascii
import json
import secrets
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from urllib.parse import urlsplit


class APIError(ValueError):
    def __init__(self,message,status=400):super().__init__(message);self.status=status


class H3Client:
    def __init__(self,url,key):
        parsed=urlsplit(url)
        if parsed.scheme!='http' or parsed.hostname not in ('127.0.0.1','localhost') or parsed.username or parsed.password:
            raise ValueError('Il collegamento immagini richiede il server H3 su questo PC.')
        self.url=url.rstrip('/');self.key=key

    def call(self,path,body=None):
        req=urllib.request.Request(self.url+path,data=None if body is None else json.dumps(body).encode(),
            headers={'Authorization':'Bearer '+self.key,'Content-Type':'application/json'})
        try:
            with urllib.request.urlopen(req,timeout=30) as response:
                raw=response.read(128*1024**2+1)
                if len(raw)>128*1024**2:raise APIError('Risposta H3 troppo grande.',502)
                return json.loads(raw)
        except urllib.error.HTTPError as exc:
            try:detail=json.loads(exc.read(4096)).get('error','Errore del server H3.')
            except (ValueError,AttributeError):detail='Errore del server H3.'
            raise APIError(detail,409 if 'occupato' in detail.lower() else exc.code) from None
        except urllib.error.URLError:
            raise APIError('Server H3 non raggiungibile. Riattiva il server immagini da H3-Chat.',503) from None


SAMPLERS={'Automatic':'auto','Euler':'euler','Euler a':'euler_ancestral','Heun':'heun','DPM++ 2M':'dpmpp_2m','DPM++ 2M SDE':'dpmpp_2m_sde','LCM':'lcm','Res Multistep':'res_multistep'}
SCHEDULERS={'Automatic':'auto','Simple':'simple','Normal':'normal','Karras':'karras','Exponential':'exponential','SGM Uniform':'sgm_uniform','Beta':'beta','Qwen 2.1 Turbo':'qwen21_turbo'}
NATIVE_SAMPLERS={'euler_ancestral':'euler_a','dpmpp_2m':'dpm++2m','dpmpp_2m_sde':'dpm++2m_sde'}


def choice(value,choices,label):
    for name,ident in choices.items():
        if isinstance(value,str) and value.lower() in (name.lower(),ident.lower()):return ident
    raise APIError(label+' non supportato dal collegamento H3.')


class ImageAPI:
    def __init__(self,client,config):
        self.client=client;self.config=config;self.model=config['model'];self.lock=threading.Lock();self.active=None

    def models(self):
        models=[m for m in self.client.call('/v1/h3/models')['data'] if 'create' in m.get('capabilities',[])]
        aliases=[]
        for model in models:
            descriptor=self.config.get('models',{}).get(model['id'],{})
            if descriptor.get('architecture')=='moss' and self.config.get('moss_dmd2_ready'):
                aliases.append(model|{'id':model['id']+'::dmd2','name':model['name']+' · Turbo DMD2',
                                      'base_model_id':model['id'],'moss_turbo':True})
        return models+aliases

    def resolve(self,value=None):
        models=self.models();value=value or self.model
        matches=[m for m in models if value in (m['id'],m['name'])]
        if len(matches)!=1:raise APIError('Modello immagini assente o ambiguo. Aggiorna l’elenco modelli.')
        return matches[0]

    def options(self):
        model=self.resolve();return {'sd_model_checkpoint':model['name'],'sd_vae':'Automatic','samples_save':True,'h3_model_id':model['id']}

    def set_options(self,body):
        if set(body)-{'sd_model_checkpoint','sd_vae','CLIP_stop_at_last_layers'}:raise APIError('Opzione server non supportata.')
        if body.get('sd_vae','Automatic') not in ('Automatic','auto',None):raise APIError('H3 usa il VAE collegato al modello selezionato.')
        if body.get('CLIP_stop_at_last_layers',1)!=1:raise APIError('CLIP skip non supportato da questo collegamento.')
        if body.get('sd_model_checkpoint'):self.model=self.resolve(body['sd_model_checkpoint'])['id']
        return {}

    def generate(self,body):
        if not self.lock.acquire(blocking=False):raise APIError('Collegamento immagini occupato.',409)
        ident=None
        try:
            if body.get('batch_size',1)!=1 or body.get('n_iter',1)!=1:raise APIError('Genera una immagine per richiesta.')
            if body.get('enable_hr') or body.get('restore_faces') or body.get('tiling') or body.get('alwayson_scripts'):
                raise APIError('High-res fix, restauro volti, tiling e script WebUI non sono disponibili in H3.')
            override=body.get('override_settings') or {}
            if not isinstance(override,dict):raise APIError('Override modello non valido.')
            if set(override)-{'sd_model_checkpoint','sd_vae','CLIP_stop_at_last_layers'}:raise APIError('Override WebUI non supportato.')
            if override.get('sd_vae','Automatic') not in ('Automatic','auto',None) or override.get('CLIP_stop_at_last_layers',1)!=1:
                raise APIError('VAE personalizzato e CLIP skip non supportati dal collegamento.')
            model=self.resolve(override.get('sd_model_checkpoint'))
            base_id=model.get('base_model_id',model['id'])
            descriptor=self.config.get('models',{}).get(base_id,{})
            opts=dict(descriptor.get('parameters',{}))
            if descriptor.get('architecture')=='moss' and not model.get('moss_turbo'):
                opts.update(opts.pop('moss_turbo_previous',{}));opts['moss_turbo']=False
            for key in ('width','height','steps','seed','negative_prompt'):
                if key in body:opts[key]=body[key]
            if 'cfg_scale' in body:opts['cfg']=body['cfg_scale']
            if body.get('sampler_name'):opts['sampler']=choice(body['sampler_name'],SAMPLERS,'Sampler')
            if body.get('scheduler'):opts['scheduler']=choice(body['scheduler'],SCHEDULERS,'Scheduler')
            # Anima/SD use stable-diffusion.cpp names; MOSS/Qwen/Ming/Krea use
            # the private Torch runtime. Both are exposed by the same client.
            if descriptor.get('engine','native')!='vision':
                opts['sampler']=NATIVE_SAMPLERS.get(opts.get('sampler'),opts.get('sampler','auto'))
            # Explicit client dimensions must not be replaced by a saved MP/ratio.
            if 'width' in body or 'height' in body:
                opts.pop('megapixels',None);opts['aspect']='auto'
            if model.get('moss_turbo'):
                from .moss_dmd2 import RECIPE
                opts.update(RECIPE,moss_turbo=True)
            elif descriptor.get('architecture')=='moss':
                # A normal entry always selects normal inference, independently
                # of the flag saved in the owner's chat preferences.
                opts['moss_turbo']=False
                opts.pop('moss_turbo_previous',None)
            prompt=body.get('prompt','')
            if not isinstance(prompt,str) or not prompt.strip():raise APIError('Scrivi il prompt dell’immagine.')
            ticket=self.client.call('/v1/h3/generations',{'task':'create','model':base_id,'prompt':prompt,'parameters':opts,'device':'gpu'})
            ident=ticket['id'];self.active=ident;deadline=time.monotonic()+1800
            while time.monotonic()<deadline:
                job=self.client.call('/v1/h3/jobs/'+ident)
                if job['status']=='done':
                    media=job['media']
                    if not media['mime'].startswith('image/'):raise APIError('H3 non ha restituito un’immagine.',502)
                    parameters=media.get('generation') or opts
                    info={**parameters,'prompt':prompt,'negative_prompt':opts.get('negative_prompt',''),'sd_model_name':model['name'],'h3_job_id':ident}
                    return {'images':[media['data']],'parameters':opts|{'prompt':prompt},'info':json.dumps(info,ensure_ascii=False)}
                if job['status'] in ('failed','cancelled','interrupted'):
                    raise APIError('Generazione H3 '+job['status']+': '+job.get('stage','consulta i log H3.'),409)
                time.sleep(.5)
            self.client.call('/v1/h3/jobs/'+ident+'/cancel',{})
            raise APIError('Tempo massimo immagini superato.',504)
        finally:self.active=None;self.lock.release()

    def interrupt(self):
        ident=self.active
        if ident:self.client.call('/v1/h3/jobs/'+ident+'/cancel',{})
        return {}

    def progress(self):
        ident=self.active
        job=self.client.call('/v1/h3/jobs/'+ident) if ident else None
        return {'progress':0,'eta_relative':0,'current_image':None,'textinfo':job.get('stage','') if job else '',
                'state':{'job_count':int(bool(ident)),'job':job.get('stage','') if job else '', 'sampling_step':0,'sampling_steps':0}}


class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args):pass
    def json(self,value,status=200):
        raw=json.dumps(value,ensure_ascii=False).encode();self.send_response(status)
        self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(raw)))
        self.send_header('Cache-Control','no-store');self.end_headers();self.wfile.write(raw)

    def authenticated(self):
        if self.headers.get('Origin'):return False
        header=self.headers.get('Authorization','');key=self.server.secret
        if secrets.compare_digest(header,'Bearer '+key):return True
        if not header.startswith('Basic '):return False
        try:raw=base64.b64decode(header[6:],validate=True).decode()
        except (ValueError,UnicodeError,binascii.Error):return False
        return secrets.compare_digest(raw,'h3:'+key)

    def handle_api(self):
        try:
            if not self.authenticated():raise APIError('Autenticazione richiesta.',403)
            api=self.server.api;path=urlsplit(self.path).path
            if self.command=='GET':
                if path=='/sdapi/v1/sd-models':return self.json([{'title':m['name'],'model_name':m['name'],'hash':None,'sha256':None,'filename':m['id'],'config':None} for m in api.models()])
                if path=='/sdapi/v1/options':return self.json(api.options())
                if path=='/sdapi/v1/samplers':return self.json([{'name':k,'aliases':[v],'options':{}} for k,v in SAMPLERS.items()])
                if path=='/sdapi/v1/schedulers':return self.json([{'name':k,'label':k,'aliases':[v]} for k,v in SCHEDULERS.items()])
                if path=='/sdapi/v1/upscalers':return self.json([{'name':'None','model_name':None,'model_path':None,'model_url':None,'scale':1}])
                if path in ('/sdapi/v1/latent-upscale-modes','/sdapi/v1/sd-vae','/sdapi/v1/sd-modules','/sdapi/v1/loras'):return self.json([])
                if path=='/sdapi/v1/embeddings':return self.json({'loaded':{},'skipped':{}})
                if path=='/sdapi/v1/progress':return self.json(api.progress())
            if self.command=='POST':
                length=int(self.headers.get('Content-Length','0'))
                if not 0<=length<=1024**2:raise APIError('Richiesta troppo grande.')
                body=json.loads(self.rfile.read(length) or '{}')
                if not isinstance(body,dict):raise APIError('Richiesta non valida.')
                if path=='/sdapi/v1/options':return self.json(api.set_options(body))
                if path=='/sdapi/v1/txt2img':return self.json(api.generate(body))
                if path=='/sdapi/v1/interrupt':return self.json(api.interrupt())
            raise APIError('Endpoint non disponibile.',404)
        except (BrokenPipeError,ConnectionResetError):pass
        except APIError as exc:self.json({'error':str(exc),'detail':str(exc)},exc.status)
        except (ValueError,TypeError,KeyError) as exc:self.json({'error':str(exc)},400)
    do_GET=do_POST=handle_api


def serve(config,key):
    if config.get('host','127.0.0.1')!='127.0.0.1':raise ValueError('Il collegamento SillyTavern ascolta solo su questo PC.')
    server=ThreadingHTTPServer(('127.0.0.1',config.get('port',8791)),Handler);server.daemon_threads=True
    server.secret=key;server.api=ImageAPI(H3Client(config['upstream'],key),config)
    try:server.serve_forever()
    finally:server.server_close()

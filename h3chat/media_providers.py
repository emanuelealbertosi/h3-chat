"""Remote media adapters; no local weights and no secrets in chat/job metadata."""
import base64
import json
import re
import secrets
import threading
import time
from pathlib import Path
from .providers import endpoint,protect
from .remote_llm import Client
from .downloads import Cancelled,safe_join
from .store import uid

class MediaProviders:
    def __init__(self,store):self.store=store;self.client=Client()
    def list(self):return [json.loads(r['config'])|{'has_key':bool(r['secret'])} for r in self.store.all('SELECT config,secret FROM media_providers')]
    def save(self,body):
        allowed={'id','name','base_url','model','role','adapter','api_key','clear_key','max_refs','prompt_format','device'}
        if not isinstance(body,dict) or set(body)-allowed:raise ValueError('Configurazione server multimediale non valida.')
        ident=body.get('id') or 'media-'+uid()
        if not isinstance(ident,str) or not re.fullmatch(r'media-[a-f0-9]{32}',ident):raise ValueError('Identificativo server non valido.')
        previous=self.store.one('SELECT * FROM media_providers WHERE id=?',(ident,))
        if body.get('id') and not previous:raise ValueError('Server non trovato.')
        cfg={k:body.get(k,d) for k,d in [('name',''),('model',''),('role','image'),('adapter','h3'),('max_refs',4),('prompt_format','natural'),('device','gpu')]};cfg.update(id=ident,base_url=endpoint(body.get('base_url','')))
        for k in ('name','model'):
            if not isinstance(cfg[k],str) or not 1<=len(cfg[k].strip())<=200 or any(ord(c)<32 for c in cfg[k]):raise ValueError('Inserisci nome del server e ID modello.')
            cfg[k]=cfg[k].strip()
        if cfg['role'] not in ('image','music','video') or cfg['adapter'] not in ('h3','openai-images','forge'):raise ValueError('Tipo o protocollo del server non valido.')
        if cfg['role']!='image' and cfg['adapter']!='h3':raise ValueError('Musica e video richiedono il protocollo H3.')
        if cfg['device'] not in ('cpu','gpu') or cfg['role']=='video' and cfg['device']!='gpu':raise ValueError('Video è disponibile solo su GPU.')
        if cfg['prompt_format'] not in ('natural','tags') or type(cfg['max_refs']) is not int or not 1<=cfg['max_refs']<=9:raise ValueError('Prompt o riferimenti non validi.')
        if cfg['adapter']=='forge':cfg['max_refs']=1
        key=body.get('api_key','')
        if not isinstance(key,str) or len(key)>8192 or any(ord(c)<33 or ord(c)>126 for c in key) or type(body.get('clear_key',False)) is not bool:raise ValueError('Chiave API non valida.')
        if key:secret=protect(key)
        elif previous and not body.get('clear_key'):
            if json.loads(previous['config'])['base_url']!=cfg['base_url']:raise ValueError('Indirizzo cambiato: reinserisci o rimuovi la chiave.')
            secret=previous['secret']
        else:secret=''
        self.store.execute('INSERT OR REPLACE INTO media_providers VALUES (?,?,?)',(ident,json.dumps(cfg),secret));return cfg|{'has_key':bool(secret)}
    def credentials(self,ident):
        row=self.store.one('SELECT * FROM media_providers WHERE id=?',(ident,))
        if not row:raise ValueError('Server non trovato.')
        return json.loads(row['config']),protect(row['secret'],decode=True)
    def model(self,cfg):
        role=cfg['role'];caps=['create','edit'] if role=='image' else [role]
        return {'id':cfg['id'],'name':cfg['name'],'remote_media':True,'architecture':'sdxl' if cfg['prompt_format']=='tags' else 'remote-image' if role=='image' else 'yue2' if role=='music' else 'minimax-h3','engine':'remote','files':[],'size':0,'capabilities':caps,'max_refs':cfg['max_refs'],'description':'Server esterno · '+cfg['adapter'],'license':'Licenza e disponibilità del provider','ready':True,'complete':True,'parameters':{}}
    def probe(self,ident):
        cfg,key=self.credentials(ident);cancel=threading.Event();path='/v1/h3/models' if cfg['adapter']=='h3' else '/sdapi/v1/sd-models' if cfg['adapter']=='forge' else '/models'
        value=self.client.exchange(cfg,key,cancel,path=path,timeout=35)
        return {'ok':True,'models':value.get('data',[]) if isinstance(value,dict) else value}
    def generate(self,model,settings,prompt,refs,job_id,cancel,stage,*,composition=None,plan=None):
        cfg,key=self.credentials(model['id']);task='video' if plan is not None else 'music' if composition is not None else 'edit' if refs else 'create'
        stage('Server esterno · '+cfg['name']+' · '+task)
        assets=[{'name':r['name'],'data':base64.b64encode(safe_join(self.store.root,r['path']).read_bytes()).decode()} for r in refs]
        if cfg['adapter']=='h3':
            params=settings.get('image_overrides',{}).get(model['id'],{}) if task in ('create','edit') else settings.get('music_overrides',{}).get(model['id'],{}) if task=='music' else settings.get('video_overrides',{}).get(model['id'],{})
            if task=='music' and params.get('max_duration') is None:params={k:v for k,v in params.items() if k!='max_duration'}
            if task=='video':
                from .video_options import apply_quality
                params=apply_quality(params,settings.get('_video_quality','high'))
                if plan and any(a['role']=='lipsync' for a in plan.get('audios',[])) and 'steps' in params:
                    params['steps']=max(8,params['steps'])
            ticket=self.client.exchange(cfg,key,cancel,path='/v1/h3/generations',body={'task':task,'model':cfg['model'],'prompt':prompt,'assets':assets,'parameters':params,'device':cfg['device'],'composition':composition,'plan':plan},timeout=60)
            ident=ticket.get('id')
            if not isinstance(ident,str) or not re.fullmatch(r'[a-f0-9]{32}',ident):raise ValueError('Il server non ha restituito un lavoro valido.')
            deadline=time.monotonic()+7200
            try:
                while True:
                    if cancel.wait(.6):raise Cancelled()
                    value=self.client.exchange(cfg,key,cancel,path='/v1/h3/jobs/'+ident,timeout=35,max_bytes=128*1024**2)
                    stage('Server · '+str(value.get('stage','Elaborazione'))[:250])
                    if value.get('status')=='done':result=value['media'];break
                    if value.get('status') in ('failed','cancelled','interrupted'):raise ValueError('Il server ha interrotto la generazione. Consulta i log sul server.')
                    if time.monotonic()>deadline:raise ValueError('Tempo massimo della generazione remota superato.')
            except Exception:
                try:self.client.exchange(cfg,key,threading.Event(),path='/v1/h3/jobs/'+ident+'/cancel',body={},timeout=5)
                except Exception:pass
                raise
        elif cfg['adapter']=='forge':
            opts=settings['_image_options'];body={k:opts[k] for k in ('steps','width','height','seed','negative_prompt')};body.update(prompt=prompt,cfg_scale=opts['cfg'],override_settings={'sd_model_checkpoint':cfg['model']},override_settings_restore_afterwards=True)
            if opts['sampler']!='auto':body['sampler_name']=opts['sampler']
            if opts['scheduler']!='auto':body['scheduler']=opts['scheduler']
            if refs:body.update(init_images=[assets[0]['data']],denoising_strength=opts['strength'])
            value=self.client.exchange(cfg,key,cancel,path='/sdapi/v1/img2img' if refs else '/sdapi/v1/txt2img',body=body,timeout=1800,max_bytes=24*1024**2)
            result={'data':value['images'][0],'mime':'image/png','name':'immagine.png','generation':opts}
        else:
            body={'model':cfg['model'],'prompt':prompt,'size':f"{settings['_image_options']['width']}x{settings['_image_options']['height']}",'n':1,'response_format':'b64_json'};ctype='application/json'
            if refs:
                boundary='h3'+secrets.token_hex(16);parts=[]
                for field,text in body.items():parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{field}"\r\n\r\n{text}\r\n'.encode())
                for index,(ref,asset) in enumerate(zip(refs,assets)):
                    field='image' if len(refs)==1 else 'image[]';ext='jpg' if ref['mime']=='image/jpeg' else 'png'
                    parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{field}"; filename="reference-{index}.{ext}"\r\nContent-Type: {ref["mime"]}\r\n\r\n'.encode()+base64.b64decode(asset['data'])+b'\r\n')
                parts.append(f'--{boundary}--\r\n'.encode());body=b''.join(parts);ctype='multipart/form-data; boundary='+boundary
            value=self.client.exchange(cfg,key,cancel,path='/images/edits' if refs else '/images/generations',body=body,content_type=ctype,timeout=1800,max_bytes=24*1024**2)
            item=value['data'][0]
            if not item.get('b64_json'):raise ValueError('Il provider deve restituire immagini b64_json; le risposte con solo URL non sono supportate.')
            result={'data':item['b64_json'],'mime':'image/png','name':'immagine.png','generation':{'remote':True,'size':body.get('size') if isinstance(body,dict) else 'edit'}}
        raw=base64.b64decode(result['data'],validate=True)
        mime=result.get('mime');ext={'image/png':'png','image/jpeg':'jpg','audio/wav':'wav','audio/mpeg':'mp3','video/mp4':'mp4'}.get(mime)
        if not ext or not raw or len(raw)>90*1024**2:raise ValueError('Output remoto non valido o troppo grande.')
        expected='image/' if task in ('create','edit') else 'audio/' if task=='music' else 'video/'
        if not mime.startswith(expected):raise ValueError('Il server ha restituito un formato diverso dalla modalità richiesta.')
        if task in ('create','edit') and not (raw.startswith(b'\x89PNG\r\n\x1a\n') or raw.startswith(b'\xff\xd8\xff')):raise ValueError('Il server non ha restituito un’immagine valida.')
        if task in ('create','edit'):mime,ext=('image/jpeg','jpg') if raw.startswith(b'\xff\xd8\xff') else ('image/png','png')
        if mime=='audio/wav' and not (raw.startswith(b'RIFF') and raw[8:12]==b'WAVE'):raise ValueError('Audio WAV non valido.')
        if mime=='video/mp4' and raw[4:8]!=b'ftyp':raise ValueError('Video MP4 non valido.')
        relative=f'outputs/{job_id}/remote.{ext}';target=safe_join(self.store.root,relative);target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(raw)
        return {'id':uid(),'path':relative,'name':result.get('name','output.'+ext),'mime':mime,'generation':result.get('generation',{})|{'remote':True}|({'quality':settings.get('_video_quality','high')} if task=='video' else {})}

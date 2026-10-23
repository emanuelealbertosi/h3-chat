"""Enable the owner's optional local inference and SillyTavern image endpoints."""
import argparse,base64,json,os,secrets,subprocess,sys,threading,time,urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from h3chat.access import Access,digest
from h3chat.providers import protect
from h3chat.image_options import configured,OVERRIDE_KEYS
from h3chat.image_api_server import H3Client


class Control:
    def __enter__(self):
        self.port=json.loads((ROOT/'data/port.json').read_text())
        self.access=Access.__new__(Access);self.access.data=ROOT/'data';self.access.path=self.access.data/'access.sqlite';self.access.lock=threading.RLock()
        with self.access.connect() as db:
            owner=db.execute("SELECT id,name,role,epoch FROM users WHERE role='owner' AND enabled=1").fetchone()
            if owner is None:raise ValueError('Configura prima l’account proprietario in H3-Chat.')
            user=dict(owner)
        self.raw,self.csrf=self.access.session(user);return self
    def __exit__(self,*args):
        with self.access.connect() as db:db.execute('DELETE FROM sessions WHERE hash=?',(digest(self.raw),))
    def call(self,path,body=None):
        req=urllib.request.Request(f'http://127.0.0.1:{self.port}/api'+path,
            data=None if body is None else json.dumps(body).encode(),headers={'Cookie':'h3_session='+self.raw,'X-H3-Token':self.csrf,'Content-Type':'application/json'})
        with urllib.request.urlopen(req,timeout=45) as response:return json.load(response)


def start(settings_path=None):
    configure_client=settings_path is not None
    config_path=ROOT/'data/image-api-server.json'
    config=json.loads(config_path.read_text(encoding='utf-8')) if config_path.exists() else {}
    key=protect(config['credential'],decode=True) if config.get('credential') else secrets.token_urlsafe(32)
    with Control() as control:
        state=control.call('/state');server=state.get('media_server',{})
        if not server.get('running'):server=control.call('/server/start',{'host':'127.0.0.1','port':8790,'api_key':key})
        if server.get('host')!='127.0.0.1':raise ValueError('È già attivo un server con configurazione diversa. Gestiscilo dalle impostazioni H3.')
        upstream='http://127.0.0.1:'+str(server['port'])
        H3Client(upstream,key).call('/v1/h3/models')
        models=[m for m in state['models'] if m.get('ready') and 'create' in m.get('capabilities',[]) and not m.get('remote_media')]
        model=next((m for m in models if m['id']==state['settings']['create_model']),None)
        if model is None:raise ValueError('Seleziona prima un modello immagini locale pronto in H3-Chat.')
        parameters=lambda m:{k:v for k,v in configured(m,state['settings']).items() if k in OVERRIDE_KEYS}
        config.update(host='127.0.0.1',port=8791,upstream=upstream,credential=protect(key),model=model['id'],
            moss_dmd2_ready=state.get('image_options',{}).get('moss_dmd2',{}).get('ready',False),
            models={m['id']:{'name':m['name'],'engine':m.get('engine','native'),'architecture':m.get('architecture'),'parameters':parameters(m)} for m in models})
    if settings_path is None and config.get('sillytavern_settings'):settings_path=Path(config['sillytavern_settings'])
    if settings_path is not None:
        settings_path=settings_path.resolve()
        if settings_path.name!='settings.json' or not settings_path.is_file():raise ValueError('Seleziona il settings.json del profilo SillyTavern.')
        settings=json.loads(settings_path.read_text(encoding='utf-8'))
        sd=settings.setdefault('extension_settings',{}).setdefault('sd',{})
        backup=ROOT/'data/image-api-sillytavern-backup.json'
        if not backup.exists():backup.write_text(json.dumps({'path':str(settings_path),'sd':protect(json.dumps(sd))},indent=2),encoding='utf-8')
        preset=parameters(model)
        sd.update(auto_url='http://127.0.0.1:8791',auto_auth='h3:'+key)
        if configure_client:
            sd.update(source='auto',model=model['name'],sampler='Euler',scheduler='Simple',steps=preset['steps'],scale=preset['cfg'],
                width=preset['width'],height=preset['height'],seed=preset['seed'],clip_skip=1,
                enable_hr=False,restore_faces=False,adetailer_face=False,vae='Automatic')
        part=settings_path.with_name('settings.h3-image-api.tmp');part.write_text(json.dumps(settings,ensure_ascii=False,indent=2),encoding='utf-8');os.replace(part,settings_path)
        config['sillytavern_settings']=str(settings_path)
    part=config_path.with_suffix('.tmp');part.write_text(json.dumps(config,ensure_ascii=False,indent=2),encoding='utf-8');os.replace(part,config_path)
    auth='Basic '+base64.b64encode(('h3:'+key).encode()).decode();url='http://127.0.0.1:8791'
    def check():
        request=urllib.request.Request(url+'/sdapi/v1/options',headers={'Authorization':auth})
        with urllib.request.urlopen(request,timeout=5) as response:return json.load(response)
    try:result=check()
    except OSError:
        logdir=ROOT/'data/logs';logdir.mkdir(exist_ok=True)
        with (logdir/'image-api-server.log').open('ab') as log:
            process=subprocess.Popen([str(ROOT/'runtime/python/python.exe'),'-X','utf8',str(ROOT/'scripts/image-api-server.py')],cwd=ROOT,
                stdout=log,stderr=subprocess.STDOUT,creationflags=0x08000000 if os.name=='nt' else 0)
        (ROOT/'data/image-api-server.pid').write_text(str(process.pid),encoding='ascii')
        for _ in range(40):
            if process.poll() is not None:raise RuntimeError('Avvio del collegamento fallito. Consulta data/logs/image-api-server.log.')
            try:result=check();break
            except OSError:time.sleep(.25)
        else:raise RuntimeError('Il collegamento non risponde.')
    if str(result.get('h3_model_id','')).removesuffix('::dmd2') not in {m['id'] for m in models}:raise RuntimeError('Un altro servizio occupa la porta 8791.')
    report={'running':True,'url':url,'model':result['sd_model_checkpoint'],'sillytavern_configured':settings_path is not None,'generations_started':0}
    (ROOT/'data/image-api-server-status.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--sillytavern',type=Path)
    try:start(parser.parse_args().sillytavern)
    except Exception as exc:print('Server immagini: '+str(exc),file=sys.stderr);raise SystemExit(1)

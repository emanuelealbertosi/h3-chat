"""H3 catalog downloads and validated per-model recipes, never arbitrary installers."""
def definitions():
    def s(n=300):return {'type':'string','maxLength':n}
    def obj(p,r=()):return {'type':'object','properties':p,'required':list(r),'additionalProperties':False}
    params=obj({'steps':{'type':'integer','minimum':1,'maximum':100},'cfg':{'type':'number','minimum':0,'maximum':30},'seed':{'type':'integer','minimum':-1,'maximum':2147483647},
        'sampler':s(50),'scheduler':s(50),'moss_turbo':{'type':'boolean'},'aspect':s(10),'megapixels':{'type':'number','minimum':.2,'maximum':16},'width':{'type':'integer','minimum':256,'maximum':4096},'height':{'type':'integer','minimum':256,'maximum':4096},'negative_prompt':dict(s(8000),minLength=0),
        'shift_video':{'type':'number','minimum':.01,'maximum':100},'shift_audio':{'type':'number','minimum':.01,'maximum':100},'duration':{'type':'number','minimum':1,'maximum':15},'attention':s(30)})
    return {
        'list_model_catalog':('Elenca i modelli H3 installati/collegati e quelli scaricabili dal catalogo verificato, con ID e dimensione. Non installa software o pesi da URL arbitrari; per un’architettura nuova non supportata serve prima integrare il motore.',obj({'query':s(200)})),
        'download_catalog_model':('Avvia il download H3 di un modello del catalogo verificato, con dimensione e SHA256. Solo proprietario. Non sceglie quel modello come default e non lo carica. Il download continua in background: usa model_download_status e non dichiararlo installato prima del completamento.',obj({'model_id':s(150)},['model_id'])),
        'model_download_status':('Leggi stato, progresso e errori del download H3 indicato. Una partenza non è una conclusione; non ripetere download già in corso o conclusi.',obj({'model_id':s(150)},['model_id'])),
        'set_model_preset':('Salva un preset immagini/video per il modello scelto usando i validatori H3. Puoi lasciare il modello opzionale (make_default=false). Sampler/scheduler devono essere supportati. Per FastH3 Omni mantieni 8 passi Euler/simple CFG1 shift12/3 VSA; non avvia inferenza. Non cambia il cervello LLM o le credenziali.',obj({'model_id':s(150),'parameters':params,'make_default':{'type':'boolean'}},['model_id','parameters']))}

WRITES={'download_catalog_model','set_model_preset'}

def execute(ctx,name,args):
    app=ctx.app;models=app.refresh_models()
    if name=='list_model_catalog':
        query=args.get('query','').casefold();rows=[]
        for model in models:
            if query and query not in (model['id']+' '+model['name']).casefold():continue
            rows.append({'id':model['id'],'name':model['name'],'capabilities':model['capabilities'],'ready':model.get('ready',False),'downloadable':not(model.get('local') or model.get('remote') or model.get('remote_media')) and bool(model.get('files')) and all(f.get('sha256') and f.get('size') for f in model.get('files',[])), 'bytes':model.get('size',sum(f.get('size',0) for f in model.get('files',[])))})
        return {'models':rows[:100],'truncated':len(rows)>100}
    model=app.catalog.get(args['model_id'])
    if not model:raise ValueError('Modello non presente nel catalogo H3: non scaricare o installare componenti inventati.')
    if name=='model_download_status':
        task=next((v for v in app.downloads.snapshot() if v['id']==model['id']),None)
        return {'model_id':model['id'],'task':task,'ready':next((m.get('ready',False) for m in models if m['id']==model['id']),False)}
    if name=='download_catalog_model':
        from .agent_computer import owner
        owner(app)
        if model.get('local') or model.get('remote') or model.get('remote_media'):raise ValueError('Questo modello è un collegamento locale/API: nessun download dal catalogo.')
        existing=next((v for v in app.downloads.snapshot() if v['id']==model['id']),None)
        if existing:return {'task':existing,'reused':True}
        if next((m.get('ready',False) for m in models if m['id']==model['id']),False):return {'model_id':model['id'],'already_available':True}
        ident=app.downloads.start(model['id']);return {'model_id':ident,'started':True,'complete':False,'note':'Il gestore H3 verifica tutti i file e gli SHA256; controlla lo stato prima di usare il modello.'}
    if name=='set_model_preset':
        from .agent_computer import owner
        owner(app);values=args['parameters'];live=app.store.settings();video='video' in model['capabilities'];key='video_overrides' if video else 'image_overrides'
        if not video and not set(model['capabilities'])&{'create','edit'}:raise ValueError('Questo strumento configura preset immagini o video, non LLM o musica.')
        allowed={'duration','megapixels','aspect','steps','cfg','sampler','scheduler','seed','shift_video','shift_audio','attention'} if video else {'megapixels','aspect','width','height','steps','cfg','sampler','scheduler','seed','negative_prompt','moss_turbo'}
        if set(values)-allowed:raise ValueError('Parametri non applicabili al tipo di modello scelto.')
        if not video and 'moss_turbo' in values:
            from .image_options import configured
            from .moss_dmd2 import RECIPE
            previous=configured(model,live)
            if not values['moss_turbo'] and previous.get('moss_turbo_previous'):values=previous['moss_turbo_previous']|values
            elif values['moss_turbo'] and not previous.get('moss_turbo'):values=values|{'moss_turbo_previous':{k:previous[k] for k in RECIPE}}
        patch={key:live[key]|{model['id']:live[key].get(model['id'],{})|values}}
        if video:
            from .video_options import options
            options(model,live|patch,False)
        if args.get('make_default'):patch['video_model' if video else 'create_model' if 'create' in model['capabilities'] else 'edit_model']=model['id']
        saved=app.save_settings(patch);ctx.settings.update({k:saved[k] for k in patch})
        return {'model_id':model['id'],'parameters':saved[key][model['id']],'default_changed':bool(args.get('make_default')),'inference_started':False}
    raise ValueError('Strumento modelli sconosciuto.')

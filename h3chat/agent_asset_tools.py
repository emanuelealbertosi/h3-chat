"""Public file downloads and validated LoRA installation through H3 tools."""
import hashlib
import mimetypes
from pathlib import Path
import re
import shutil


def definitions():
    def obj(p,r):return {'type':'object','properties':p,'required':r,'additionalProperties':False}
    text=lambda n:{'type':'string','maxLength':n}
    common={'url':text(2000),'name':text(140),'sha256':text(64),'max_megabytes':{'type':'integer','minimum':1,'maximum':32768}}
    return {
        'download_web_file':('Scarica un file da un URL pubblico diretto negli output H3, con progresso, dimensione e SHA256. Non apre né esegue il file e non estrae archivi. Richiede Web. Per una pagina che contiene un link usa prima read_web_page. Non inventare URL. Default 512 MiB, limite configurabile e spazio verificato.',obj(common,['url','name'])),
        'install_lora_from_url':('Scarica un LoRA .safetensors da un URL pubblico diretto, ne controlla struttura e compatibilità col model_id disponibile e lo installa nella libreria LoRA H3. Solo proprietario, richiede Web. Non esegue codice, non seleziona automaticamente il LoRA e non sovrascrive file. Per architetture nuove serve integrare il motore. Gli accessi protetti non vengono aggirati.',obj(common|{'model_id':text(150),'folder_number':{'type':'integer','minimum':1,'maximum':32}},['url','name','model_id']))}


WRITES=set(definitions())


def filename(value):
    if not isinstance(value,str) or not re.fullmatch(r'[\w ()+.,@-]{1,140}',value) or value.startswith('.') or value.endswith((' ','.')) or re.match(r'(?i)^(CON|PRN|AUX|NUL|COM[0-9]|LPT[0-9])(?:\.|$)',value):raise ValueError('Usa un nome file semplice, senza cartelle o nomi riservati.')
    return value


def execute(ctx,name,args):
    from .agent_computer import owner
    from .downloads import safe_join
    owner(ctx.app)
    if not ctx.settings.get('_web',ctx.settings.get('web_auto',True)):raise PermissionError('Attiva Web per scaricare file o LoRA.')
    selected=filename(args['name']);expected=args.get('sha256')
    ceiling=getattr(ctx,'state',{}).get('config',{}).get('max_download_megabytes',8192)
    maximum=args.get('max_megabytes',min(ceiling,8192 if name=='install_lora_from_url' else 512))
    if maximum>ceiling:raise ValueError('Il download supera il limite scelto nelle Preferenze Agente. Aumentalo prima di una nuova richiesta.')
    if expected is not None and not re.fullmatch('[a-fA-F0-9]{64}',expected):raise ValueError('SHA256 atteso non valido.')
    model=None;root=None
    if name=='install_lora_from_url':
        if Path(selected).suffix.lower()!='.safetensors':raise ValueError('Installa soltanto LoRA .safetensors, non pickle, script o archivi.')
        model=ctx.app.catalog.get(args['model_id'])
        if not model or not set(model.get('capabilities',[]))&{'create','edit','video'}:raise ValueError('Scegli un modello H3 immagini/video disponibile e compatibile.')
        roots=ctx.app.store.settings().get('lora_dirs',[])
        number=args.get('folder_number',1)
        if roots:
            if number>len(roots):raise ValueError('Cartella LoRA non disponibile nelle preferenze.')
            root=Path(roots[number-1]).resolve()
            if not root.is_dir():raise ValueError('La cartella LoRA scelta non è disponibile.')
        else:
            if number!=1:raise ValueError('Non esiste questa cartella LoRA.')
            root=(ctx.app.root/'models/loras/Agent').resolve()
        if (root/selected).exists():raise ValueError('Questo nome esiste già nella libreria LoRA. Scegli un nome diverso; nessun file sovrascritto.')
    result=ctx.engine.tool_call('agent-asset-worker.py',{'data':str(ctx.app.data),'id':ctx.action['id'],'url':args['url'],'name':selected,
        'sha256':expected,'max_megabytes':maximum},ctx.cancel,ctx.stage,ctx.log_path,timeout=min(600,max(1,ctx.remaining())))
    source=safe_join(ctx.app.data,result['path'])
    if not source.is_file() or source.stat().st_size!=result['bytes']:raise ValueError('File scaricato non disponibile o incompleto.')
    if model:
        from .loras import inspect
        from .image_options import compatible
        traits=inspect(source)
        if not traits or not compatible(traits['family'],model):raise ValueError('Il file non è un LoRA riconosciuto compatibile con il modello. È rimasto negli output, non installato.')
        root.mkdir(parents=True,exist_ok=True);target=root/selected
        # Exclusive creation: a concurrent file is never overwritten.
        created=False
        if shutil.disk_usage(root).free<source.stat().st_size+512*1024**2:raise ValueError('Spazio insufficiente nella libreria LoRA. Download conservato negli output.')
        try:
            with source.open('rb') as src:
                with target.open('xb') as dst:
                    created=True
                    while block:=src.read(1024**2):ctx.check();dst.write(block)
            with target.open('rb') as stream:digest=hashlib.file_digest(stream,'sha256').hexdigest()
            if digest!=result['sha256']:raise ValueError('Checksum della copia LoRA diverso dal download.')
        except FileExistsError:raise ValueError('Il nome LoRA è stato occupato nel frattempo; nessuna sovrascrittura.') from None
        except BaseException:
            if created:target.unlink(missing_ok=True)
            raise
        live=ctx.app.store.settings()
        if str(root) not in live['lora_dirs']:ctx.app.save_settings({'lora_dirs':[*live['lora_dirs'],str(root)]})
        listing=ctx.app.loras.scan(ctx.app.store.settings()['lora_dirs'],refresh=True)
        return {'installed':True,'name':selected,'sha256':result['sha256'],'bytes':result['bytes'],'family':traits['family'],'model_id':model['id'],
                'selected_for_generation':False,'inference_started':False,'available_in_lora_library':any(v['path']==str(target) for v in listing['items'])}
    item={'id':ctx.action['id'],'name':selected,'path':result['path'],'mime':mimetypes.guess_type(selected)[0] or 'application/octet-stream'}
    ctx.app.store.gallery.register([item])
    ctx.tool_app.save_artifact(ctx.job['chat_id'],title='File · '+selected,content='File scaricato; non aperto né eseguito. SHA256: '+result['sha256'],media=[item])
    return ctx.artifact_result({'title':'File · '+selected})|{'downloaded':True,'executed':False,'bytes':result['bytes'],'sha256':result['sha256'],'expected_hash_verified':bool(expected)}

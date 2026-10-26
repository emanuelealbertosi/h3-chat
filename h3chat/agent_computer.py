"""Host-owned Agent capabilities. Model arguments can never grant a scope."""
import hashlib
import json
import os
from pathlib import Path
import re
import time
from .store import uid

SCOPES=('h3','sandbox','global')

def owner(app):
    if getattr(app,'execution_owner',app) is not app:raise PermissionError('Controllo del computer riservato al proprietario locale.')

def folder(app):return app.data/'agent-computer-grants'

def public(app):
    import sys
    from .posix_computer import sandbox_backend
    supported=os.name=='nt' or sys.platform=='darwin' or sys.platform.startswith('linux')
    sandbox=os.name=='nt' or bool(sandbox_backend())
    return {'scopes':[s for s in SCOPES if s!='sandbox' or sandbox] if supported else ['h3'],
            'sandbox_execution':sandbox,'uac':os.name=='nt','admin':supported,
            'admin_label':'UAC' if os.name=='nt' else 'macOS' if sys.platform=='darwin' else 'Polkit',
            'sandbox_network':'public' if os.name=='nt' else 'h3-tools'}

def check_root(app,value):
    from .external_models import absolute_path
    raw=Path(value)
    for p in (raw,*raw.parents):
        if p.exists() and (p.is_symlink() or getattr(p.lstat(),'st_file_attributes',0)&0x400):raise ValueError('Scegli una cartella reale, senza collegamenti nel percorso.')
    root=absolute_path(value)
    if not root.is_dir() or root==root.parent:raise ValueError('Scegli una cartella esistente, non un intero disco.')
    private=[app.root.resolve(),app.data.resolve()]
    if any(root.is_relative_to(p) or p.is_relative_to(root) for p in private):raise ValueError('Scegli una cartella separata dall’installazione e dai dati H3.')
    # Reparse points and existing hard links may grant the container an alias to
    # another object when an inherited ACL is applied. Admit ordinary trees only.
    count=0
    for base,dirs,files in os.walk(root,followlinks=False):
        for name in dirs+files:
            p=Path(base)/name;st=p.lstat();count+=1
            if count>100000:raise ValueError('Cartella troppo grande da verificare: scegli una sottocartella di lavoro.')
            if getattr(st,'st_file_attributes',0)&0x400 or p.is_symlink() or not p.is_dir() and st.st_nlink>1:raise ValueError('La cartella contiene collegamenti: usa una cartella di lavoro senza link o junction.')
    return root

def create(app,body):
    owner(app);scope=body.get('scope')
    if scope not in SCOPES:raise ValueError('Scegli H3, Sandbox o Globale.')
    if scope=='h3':return {'scope':'h3','grant_id':'','root':''}
    if scope not in public(app)['scopes']:raise ValueError('Questa modalità richiede l’isolamento nativo del sistema. Nessun accesso libero di ripiego.')
    if body.get('confirmed') is not True:raise ValueError('Conferma esplicitamente l’accesso al computer.')
    root=check_root(app,body.get('root','')) if scope=='sandbox' else None
    ident=uid();record={'id':ident,'scope':scope,'root':str(root) if root else '',
        'root_identity':[root.stat().st_dev,root.stat().st_ino] if root else None,'created':time.time(),'revoked':False}
    folder(app).mkdir(parents=True,exist_ok=True)
    (folder(app)/(ident+'.json')).write_text(json.dumps(record),encoding='utf8')
    return {k:record[k] for k in ('scope','root')}|{'grant_id':ident}

def grant(app,config):
    owner(app);scope=config.get('scope','h3');ident=config.get('grant_id','')
    if scope=='h3':raise PermissionError('In H3 usa gli strumenti dell’app. Per file e comandi scegli Sandbox o Globale.')
    if not re.fullmatch('[a-f0-9]{32}',ident):raise PermissionError('Autorizza la modalità dalla finestra Agent sul PC locale.')
    try:record=json.loads((folder(app)/(ident+'.json')).read_text(encoding='utf8'))
    except (OSError,ValueError):raise PermissionError('Autorizzazione al computer non disponibile: seleziona di nuovo la modalità.')
    if record.get('revoked') or record.get('scope')!=scope:raise PermissionError('Autorizzazione al computer revocata o non valida.')
    if scope=='sandbox':
        root=Path(record['root']);st=root.stat()
        if [st.st_dev,st.st_ino]!=record['root_identity'] or root.is_symlink() or getattr(st,'st_file_attributes',0)&0x400:raise PermissionError('La cartella autorizzata è cambiata: selezionala di nuovo.')
    return record

def revoke(app,ident):
    owner(app)
    if not re.fullmatch('[a-f0-9]{32}',ident):raise ValueError('Autorizzazione non valida.')
    path=folder(app)/(ident+'.json')
    if path.exists():
        record=json.loads(path.read_text());record['revoked']=True;path.write_text(json.dumps(record),encoding='utf8')
    if getattr(app,'store',None):
        for job in app.store.all("SELECT id FROM jobs WHERE status IN ('queued','running') AND json_extract(payload,'$.settings._agent.options.grant_id')=?",(ident,)):
            app.cancel(job['id'])
    return {'revoked':True}

def definitions():
    def s(n=4000):return {'type':'string','maxLength':n}
    def obj(p,r):return {'type':'object','properties':p,'required':r,'additionalProperties':False}
    return {
      'import_computer_file':('Copia un file dalla cartella/PC autorizzato negli allegati H3 della chat (max 20 MiB). Poi usa l’artefatto con read_attachment, inspect_image, trascrizione, RAG o creazione contenuti. Non legge il contenuto nel prompt da solo.',obj({'path':s()},['path'])),
      'export_computer_file':('Copia un file di un artefatto/allegato H3 nella destinazione autorizzata (max 20 MiB), senza sovrascrivere file esistenti. artifact_id identifica un artefatto della chat; number è il numero del file. Per generare PDF/slide/immagini usa prima il tool H3.',obj({'path':s(),'artifact_id':s(32),'number':{'type':'integer','minimum':1,'maximum':128}},['path','number'])),
      'computer_files':('File del computer nel perimetro autorizzato. In Sandbox percorsi relativi alla cartella scelta; in Globale percorsi assoluti. Op list/read/search/write/replace/mkdir/copy/move/remove. Leggi prima di sostituire o cancellare un file e passa expected_sha256. Nessuna cancellazione ricorsiva.',obj({'operation':{'type':'string','enum':['list','read','search','write','replace','mkdir','copy','move','remove']},'path':s(),'target':s(),'text':dict(s(16000),minLength=0),'find':s(8000),'expected_sha256':s(64)},['operation','path'])),
      'computer_run':('Esegui codice/comandi e osserva uscita ed exit code. Usa prima il tool H3. Python è comune; shell usa /bin/sh su Mac/Linux, cmd e powershell sono Windows. In Sandbox executable deve stare nella cartella. Su Mac/Linux la rete Sandbox passa dai tool Web H3 e import/export. Nessun successo dichiarato senza exit code e verifica.',obj({'engine':{'type':'string','enum':['python','shell','powershell','cmd','executable']},'code':s(16000),'executable':s(),'arguments':{'type':'array','items':s(),'maxItems':30},'workdir':s(),'timeout':{'type':'integer','minimum':1,'maximum':600}},['engine'])),
      'request_admin':('Solo Globale. Prepara un comando concreto e motivo e attendi conferma umana H3 e poi nativa (UAC Windows/PowerShell; macOS o Polkit Linux/shell POSIX). Non puoi approvare o elevare da solo.',obj({'command':s(12000),'reason':s(1000)},['command','reason']))}

WRITES=set(definitions())

def execute(ctx,name,args):
    record=grant(ctx.app,ctx.state['config'])
    if record['scope']=='sandbox':check_root(ctx.app,record['root'])
    if name=='request_admin':
        if record['scope']!='global':raise PermissionError('Amministratore disponibile soltanto in Globale.')
        if ctx.action.get('admin_approved'):
            return ctx.engine.tool_call('agent-admin-worker.py',{'command':args['command'],'folder':str(ctx.app.data/'agent-computer-jobs'/ctx.action['id']), 'timeout':min(600,max(1,int(ctx.remaining())-15))},ctx.cancel,ctx.stage,ctx.log_path,timeout=max(1,ctx.remaining()))
        ctx.action.update(status='awaiting_admin',admin={'command':args['command'],'reason':args['reason']})
        ctx.state.update(status='awaiting_admin',message='Agent attende l’approvazione del comando e la conferma amministratore del sistema.')
        ctx.persist();raise AwaitAdmin()
    request={'op':name,'args':args,'scope':record['scope'],'root':record['root'],'app_root':str(ctx.app.root),
             'folder':str(ctx.app.data/'agent-computer-jobs'/ctx.action['id'])}
    if name=='export_computer_file':
        import base64
        from .agent_inputs import selected
        from .downloads import safe_join
        item=selected(ctx,args);source=safe_join(ctx.app.data,item['path'])
        if source.stat().st_size>20*1024**2:raise ValueError('File oltre il limite di trasferimento di 20 MiB. Nessuna copia eseguita.')
        request['op']='transfer_write';request['args']={'path':args['path'],'data':base64.b64encode(source.read_bytes()).decode('ascii')}
    if name=='import_computer_file':request['op']='transfer_read'
    result=ctx.engine.tool_call('agent-computer-worker.py',request,ctx.cancel,ctx.stage,ctx.log_path,timeout=min(args.get('timeout',60)+30,max(1,ctx.remaining())))
    if name=='import_computer_file':
        import base64
        raw=base64.b64decode(result.pop('data'),validate=True)
        if len(raw)>20*1024**2:raise ValueError('File oltre il limite di importazione.')
        ident=uid();temporary=ctx.app.uploads.folder/(ident+'.partial')
        try:
            temporary.write_bytes(raw);item=ctx.app.uploads.publish(ident,temporary,result['name'])
        finally:temporary.unlink(missing_ok=True)
        value={'title':'File · '+result['name'],'content':'File copiato dal computer autorizzato. Non ancora letto o analizzato.','media':[item]}
        ctx.tool_app.save_artifact(ctx.job['chat_id'],**value)
        return ctx.artifact_result(value)|{'imported':True,'sha256':result['sha256']}
    return result

class AwaitAdmin(RuntimeError):pass

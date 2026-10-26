"""Create source projects in the workspace's managed outputs; never execute them."""
import ast
import json
import re
import zipfile
from pathlib import Path,PurePosixPath
from .store import uid
from .downloads import safe_join

EXTENSIONS={'.txt','.md','.csv','.json','.py','.js','.ts','.tsx','.jsx','.html','.css','.svg','.xml','.yaml','.yml','.toml','.ini','.sql','.c','.cpp','.h','.hpp','.rs','.go','.java','.sh','.ps1','.bat'}

def definitions():
    def s(n):return {'type':'string','maxLength':n}
    def obj(p,r):return {'type':'object','properties':p,'required':r,'additionalProperties':False}
    return {
      'create_files':('Crea file sorgente, programmi o documenti testuali scaricabili e un archivio ZIP, senza eseguirli. Scrive solo negli output gestiti di H3; niente percorsi del PC. Per slide, immagini, audio e PDF usa i relativi strumenti H3 e dichiaralo.',obj({'title':s(150),'files':{'type':'array','minItems':1,'maxItems':20,'items':obj({'name':s(180),'content':s(24000)|{'minLength':0}},['name','content'])}},['title','files'])),
      'create_pdf':('Crea un PDF tramite il renderer PDF nativo H3, su CPU. Fornisci HTML con stili inline; niente script, reti o percorsi esterni. Per creare una presentazione usa prima create_slides, non imitare le slide con file generici.',obj({'title':s(150),'html':s(24000)},['title','html'])),
    }

def filename(name):
    if '\\' in name or ':' in name or any(ord(c)<32 for c in name):raise ValueError('Nome file non valido.')
    parts=PurePosixPath(name).parts
    if not parts or str(PurePosixPath(name))!=name or name.startswith('/') or any(p in ('.','..') or p.endswith((' ','.')) or re.fullmatch(r'(?i)(?:con|prn|aux|nul|com[0-9]|lpt[0-9])(?:\..*)?',p) for p in parts):raise ValueError('Nome file non valido.')
    if Path(name).suffix.lower() not in EXTENSIONS:raise ValueError('Formato non testuale: usa lo strumento H3 dedicato. I programmi vengono salvati come sorgenti, non eseguiti o compilati.')
    return name

def execute(ctx,name,args):
    if name=='create_pdf':
        result=ctx.engine.tool_call('agent-pdf-worker.py',{'data':str(ctx.app.data),'body':{'title':args['title'],'html':args['html']}},ctx.cancel,ctx.stage,ctx.log_path,timeout=120)
        item={'id':uid(),'name':result['name'],'path':result['url'].lstrip('/'),'mime':'application/pdf'}
        value={'title':args['title'],'content':'PDF creato con il renderer PDF di H3.','media':[item]}
    else:
        files=args['files'];seen=set();checked=[]
        if sum(len(f['content'].encode()) for f in files)>512*1024:raise ValueError('Progetto troppo grande per un solo passaggio: dividilo in più parti.')
        for f in files:
            path=filename(f['name']);canonical=path.casefold()
            if canonical in seen:raise ValueError('Nomi file duplicati nel progetto.')
            seen.add(canonical);kind=Path(path).suffix.lower()
            if kind=='.py':
                try:ast.parse(f['content'])
                except SyntaxError as error:raise ValueError('Sintassi Python non valida in '+path+': '+error.msg) from error
                checked.append(path)
            if kind=='.json':json.loads(f['content']);checked.append(path)
        folder=safe_join(ctx.app.data,'exports/'+ctx.action['id']);folder.mkdir(parents=True,exist_ok=False)
        media=[]
        for f in files:
            ctx.check();path=safe_join(folder,f['name']);path.parent.mkdir(parents=True,exist_ok=True);path.write_text(f['content'],encoding='utf8',newline='\n')
            media.append({'id':uid(),'name':f['name'],'path':path.relative_to(ctx.app.data).as_posix(),'mime':'text/plain'})
        archive=folder/'progetto.zip'
        with zipfile.ZipFile(archive,'x',compression=zipfile.ZIP_DEFLATED) as out:
            for f in files:out.write(safe_join(folder,f['name']),f['name'])
        media.append({'id':uid(),'name':args['title']+'.zip','path':archive.relative_to(ctx.app.data).as_posix(),'mime':'application/zip'})
        value={'title':args['title'],'content':'## '+args['title']+'\n\nFile sorgente creati; nessun programma eseguito o installato.\n\n'+
               '\n'.join('- '+f['name'] for f in files)+'\n\nControllo sintattico Python/JSON: '+(', '.join(checked) or 'non applicabile')+'. Non è un test funzionale.','media':media}
    ctx.tool_app.save_artifact(ctx.job['chat_id'],**value)
    return ctx.artifact_result(value)|{'files':[{'number':i+1,'name':m['name'],'mime':m['mime']} for i,m in enumerate(value['media'])],'executed':False}

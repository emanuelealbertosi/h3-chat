"""Dedicated single-video download; the Agent does not invent streaming URLs."""
import re
from urllib.parse import urlsplit,parse_qs

WRITES={'download_online_video'}

def youtube_url(value):
    if not isinstance(value,str) or len(value)>4096 or any(ord(c)<33 for c in value):raise ValueError('URL video non valido.')
    part=urlsplit(value);host=(part.hostname or '').lower()
    if part.scheme not in ('http','https') or part.username or part.password or part.port not in (None,80,443):raise ValueError('URL video non valido.')
    if host in ('youtu.be','www.youtu.be'):ident=part.path.strip('/').split('/')[0]
    elif host in ('youtube.com','www.youtube.com','m.youtube.com','music.youtube.com'):
        segments=part.path.strip('/').split('/')
        ident=parse_qs(part.query).get('v',[''])[0] if part.path=='/watch' else segments[1] if len(segments)==2 and segments[0] in ('shorts','live','embed') else ''
    else:raise ValueError('Questo strumento scarica singoli video YouTube. Per un file pubblico diretto usa download_web_file o il browser Agent.')
    if not re.fullmatch(r'[A-Za-z0-9_-]{11}',ident):raise ValueError('Indica un singolo video YouTube, non una playlist o un canale.')
    return 'https://www.youtube.com/watch?v='+ident

def definitions():
    return {'download_online_video':('Scarica un singolo video pubblico YouTube nel formato disponibile fino all’altezza scelta, audio incluso. Usa yt-dlp verificato e FFmpeg locale su CPU; se manca installa il solo piccolo componente privato verificato. Non scarica playlist né usa cookie personali, login o contenuti protetti. Non genera video. Richiede Web su consenso o policy autoapprova, rispetta Stop e limite download. Conserva originale e provenienza come artefatto H3.',
        {'type':'object','properties':{'url':{'type':'string','maxLength':4096},'name':{'type':'string','maxLength':120},'max_height':{'type':'integer','enum':[360,480,720,1080,1440,2160]},'max_megabytes':{'type':'integer','minimum':1,'maximum':32768}},'required':['url'],'additionalProperties':False})}

def execute(ctx,name,args):
    from .agent_asset_tools import filename
    from .downloads import safe_join
    from .file_uploads import identify
    if not ctx.settings.get('_web'):raise PermissionError('Il downloader richiede Web autorizzato per questo lavoro.')
    url=youtube_url(args['url']);limit=ctx.state['config'].get('max_download_megabytes',8192);maximum=args.get('max_megabytes',min(512,limit))
    if maximum>limit:raise ValueError('Il limite richiesto supera quello delle Preferenze Agente.')
    name=filename(args.get('name','Video YouTube'))
    result=ctx.engine.tool_call('agent-online-video-worker.py',{'data':str(ctx.app.data),'id':ctx.action['id'],'url':url,'max_height':args.get('max_height',1080),'max_megabytes':maximum},ctx.cancel,ctx.stage,ctx.log_path,timeout=min(1800,max(1,ctx.remaining())))
    path=safe_join(ctx.app.data,result['path']);extension,mime=identify(path,path.name)
    if not mime.startswith('video/') or path.stat().st_size!=result['bytes']:raise ValueError('Il downloader non ha restituito un video completo.')
    title=result.get('title') or name
    item={'id':ctx.action['id'],'name':name+extension,'path':result['path'],'mime':mime,'source_url':url}
    value={'title':'Video scaricato · '+title[:100],'content':'Video originale scaricato da '+url+'. Audio incluso se disponibile. SHA256: '+result['sha256'],'media':[item]}
    ctx.tool_app.save_artifact(ctx.job['chat_id'],**value)
    return ctx.artifact_result(value)|{k:result[k] for k in ('bytes','sha256','duration','width','height','audio') if k in result}|{'downloaded':True,'source_url':url,'generated':False}

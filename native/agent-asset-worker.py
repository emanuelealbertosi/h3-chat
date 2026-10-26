"""Pinned-public-DNS streaming download; never executes or extracts files."""
import hashlib
import http.client
import ipaddress
import json
import os
from pathlib import Path
import re
import shutil
import socket
import ssl
import sys
from urllib.parse import urlsplit,urljoin
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from h3chat.downloads import safe_join
from h3chat.agent_asset_tools import filename
wire=sys.stdout;sys.stdout=sys.stderr


def emit(event,**kw):wire.write(json.dumps({'event':event,**kw})+'\n');wire.flush()


def run(request):
    if not re.fullmatch('[a-f0-9]{32}',request['id']):raise ValueError('ID download non valido.')
    name=filename(request['name']);limit=request.get('max_megabytes',512)
    if type(limit) is not int or not 1<=limit<=32768:raise ValueError('Limite download non valido.')
    target=safe_join(Path(request['data']),'outputs/'+request['id']+'/asset/'+name);target.parent.mkdir(parents=True,exist_ok=True)
    if target.exists():raise ValueError('Il download è già presente: non sovrascrivere o ripetere.')
    part=target.with_name(target.name+'.partial');url=request['url'];reserve=512*1024**2
    try:
        for _ in range(6):
            parsed=urlsplit(url)
            if parsed.scheme not in ('http','https') or not parsed.hostname or parsed.username or parsed.password or parsed.port not in (None,80,443) or any(ord(c)<33 for c in url):raise ValueError('Serve un URL HTTP(S) pubblico senza credenziali.')
            port=parsed.port or (443 if parsed.scheme=='https' else 80);addresses=socket.getaddrinfo(parsed.hostname,port,type=socket.SOCK_STREAM)
            if not addresses or any(not ipaddress.ip_address(a[4][0]).is_global for a in addresses):raise ValueError('Download consentito solo da indirizzi Internet pubblici.')
            connection=http.client.HTTPSConnection(parsed.hostname,port,timeout=20) if parsed.scheme=='https' else http.client.HTTPConnection(parsed.hostname,port,timeout=20)
            sock=socket.create_connection((addresses[0][4][0],port),timeout=20)
            connection.sock=ssl.create_default_context().wrap_socket(sock,server_hostname=parsed.hostname) if parsed.scheme=='https' else sock
            try:
                connection.request('GET',(parsed.path or '/')+('?' +parsed.query if parsed.query else ''),headers={'User-Agent':'H3-Chat','Accept-Encoding':'identity'})
                response=connection.getresponse()
                if response.status in (301,302,303,307,308):url=urljoin(url,response.getheader('Location',''));continue
                if response.status!=200:raise ValueError('Download HTTP '+str(response.status)+': accesso protetto o link non diretto; nessun accesso aggirato.')
                if response.getheader('Content-Encoding','identity').lower()!='identity':raise ValueError('Codifica del download non supportata.')
                total=int(response.getheader('Content-Length','0'))
                if total>limit*1024**2 or total and shutil.disk_usage(target.parent).free<total+reserve:raise ValueError('File troppo grande o spazio insufficiente per il download.')
                checksum=hashlib.sha256();size=0;reported=0
                with part.open('xb') as stream:
                    while block:=response.read(1024**2):
                        size+=len(block)
                        if size>limit*1024**2 or shutil.disk_usage(target.parent).free<len(block)+reserve:raise ValueError('Raggiunto il limite del download o dello spazio libero.')
                        stream.write(block);checksum.update(block)
                        if size-reported>=16*1024**2:emit('stage',message='Download file · '+str(size//1024**2)+' MiB'+(' / '+str(total//1024**2)+' MiB' if total else ''));reported=size
                if not size or total and size!=total:raise ValueError('Download incompleto.')
                digest=checksum.hexdigest()
                if request.get('sha256') and digest!=request['sha256'].lower():raise ValueError('SHA256 diverso da quello atteso. File non pubblicato.')
                # Atomic exclusive publication on the same filesystem.
                if os.name=='nt':part.rename(target) # Windows rename refuses an existing destination.
                else:os.link(part,target);part.unlink()
                return {'path':target.relative_to(Path(request['data']).resolve()).as_posix(),'bytes':size,'sha256':digest}
            finally:connection.close()
        raise ValueError('Troppi reindirizzamenti del download.')
    finally:part.unlink(missing_ok=True)


if __name__=='__main__':
    emit('hello',engine='agent-public-asset-cpu')
    try:emit('result',result=run(json.loads(sys.stdin.readline())))
    except Exception as exc:emit('error',message=str(exc))

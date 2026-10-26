"""Public HTTP(S) image download with pinned DNS, bounded bytes and CPU validation."""
import http.client
import io
import ipaddress
import json
from pathlib import Path
import socket
import ssl
import sys
from urllib.parse import urlsplit,urljoin
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'runtime/tools/documents')]
wire=sys.stdout;sys.stdout=sys.stderr
def emit(event,**kw):wire.write(json.dumps({'event':event,**kw})+'\n');wire.flush()

def download(url,accept='image/png,image/jpeg,image/webp'):
    for _ in range(6):
        p=urlsplit(url)
        if p.scheme not in ('http','https') or not p.hostname or p.username or p.password or p.port not in (None,80,443) or any(ord(c)<33 for c in url):raise ValueError('URL immagine non consentito.')
        port=p.port or (443 if p.scheme=='https' else 80)
        addresses=socket.getaddrinfo(p.hostname,port,type=socket.SOCK_STREAM)
        if not addresses or any(not ipaddress.ip_address(a[4][0]).is_global for a in addresses):raise ValueError('Solo immagini da Internet pubblico; indirizzi privati non consentiti.')
        connection=http.client.HTTPSConnection(p.hostname,port,timeout=12) if p.scheme=='https' else http.client.HTTPConnection(p.hostname,port,timeout=12)
        sock=socket.create_connection((addresses[0][4][0],port),timeout=12)
        connection.sock=ssl.create_default_context().wrap_socket(sock,server_hostname=p.hostname) if p.scheme=='https' else sock
        try:
            connection.request('GET',(p.path or '/')+('?' +p.query if p.query else ''),headers={'User-Agent':'H3-Chat','Accept':accept,'Accept-Encoding':'identity'})
            response=connection.getresponse()
            if response.status in (301,302,303,307,308):url=urljoin(url,response.getheader('Location',''));continue
            if response.status!=200:raise ValueError('Download immagine: HTTP '+str(response.status))
            if response.getheader('Content-Encoding','identity').lower()!='identity':raise ValueError('Codifica immagine non supportata.')
            output=bytearray()
            while block:=response.read(65536):
                output.extend(block)
                if len(output)>20*1024**2:raise ValueError('Immagine oltre il limite di 20 MiB.')
            return bytes(output)
        finally:connection.close()
    raise ValueError('Troppi reindirizzamenti immagine.')

def run(request):
    from PIL import Image
    from h3chat.downloads import safe_join
    import re
    if not re.fullmatch('[a-f0-9]{32}',request['id']) or not re.fullmatch('outputs/[a-f0-9]{32}',request['folder']):raise ValueError('Destinazione immagine non valida.')
    if request.get('op')=='document':
        name=request['name']
        if not isinstance(name,str) or len(name)>150 or re.search(r'[\\/:\x00-\x1f]',name) or name.endswith((' ','.')) or re.match(r'(?i)^(CON|PRN|AUX|NUL|COM[0-9]|LPT[0-9])(?:\.|$)',name):raise ValueError('Usa un nome semplice per il documento.')
        suffix=Path(name).suffix.lower()
        if suffix not in ('.pdf','.docx','.txt','.md'):raise ValueError('Scarica documenti PDF, DOCX, TXT o Markdown.')
        raw=download(request['url'],accept='application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document,text/plain,text/markdown,*/*;q=0.5')
        if suffix=='.pdf':
            if not raw.startswith(b'%PDF-') or b'%%EOF' not in raw[-2048:]:raise ValueError('Il server non ha restituito un PDF completo.')
        elif suffix=='.docx':
            import zipfile
            with zipfile.ZipFile(io.BytesIO(raw)) as z:
                if 'word/document.xml' not in z.namelist() or sum(v.file_size for v in z.infolist())>100*1024**2:raise ValueError('Documento Word non valido o troppo grande.')
        else:
            text=raw.decode('utf8')
            if '\0' in text or re.search(r'(?i)<(?:html|!doctype)',text[:500]):raise ValueError('Il server ha restituito una pagina Web, non il documento richiesto.')
        relative=request['folder']+'/'+request['id']+suffix;target=safe_join(Path(request['data']),relative);target.parent.mkdir(parents=True,exist_ok=True)
        with target.open('xb') as out:out.write(raw)
        return {'id':request['id'],'name':name,'path':relative,'mime':{'.pdf':'application/pdf','.docx':'application/vnd.openxmlformats-officedocument.wordprocessingml.document','.txt':'text/plain','.md':'text/markdown'}[suffix],'source_url':request['url'],'bytes':len(raw)}
    raw=download(request['url'])
    with Image.open(io.BytesIO(raw)) as image:
        suffix={'PNG':'.png','JPEG':'.jpg','WEBP':'.webp'}.get(image.format)
        if not suffix or image.width*image.height>64000000:raise ValueError('Formato immagine non supportato o oltre 64 MP.')
        width,height=image.size;image.verify()
    relative=request['folder']+'/'+request['id']+suffix;target=safe_join(Path(request['data']),relative);target.parent.mkdir(parents=True,exist_ok=True)
    with target.open('xb') as out:out.write(raw)
    return {'id':request['id'],'name':'immagine-web'+suffix,'path':relative,'mime':{'.png':'image/png','.jpg':'image/jpeg','.webp':'image/webp'}[suffix],'web_download':{'width':width,'height':height,'bytes':len(raw)}}
if __name__=='__main__':
    emit('hello',engine='agent-web-image-cpu')
    try:emit('result',result=run(json.loads(sys.stdin.readline())))
    except Exception as error:emit('error',message=str(error))

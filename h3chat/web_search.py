"""Bounded public web retrieval. No keys, cookies, browser or remote model."""
import ipaddress
import re
import socket
import threading
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from .downloads import Cancelled

def public_url(url):
    if any(ord(c)<33 for c in url):raise ValueError('URL web non valido.')
    p=urllib.parse.urlsplit(url)
    if p.scheme not in ('http','https') or not p.hostname or p.username or p.password or p.port not in (None,80,443):
        raise ValueError('URL web non consentito.')
    addresses=socket.getaddrinfo(p.hostname,p.port or (443 if p.scheme=='https' else 80),type=socket.SOCK_STREAM)
    if not addresses or any(not ipaddress.ip_address(x[4][0]).is_global for x in addresses):
        raise ValueError('La lettura web accetta soltanto pagine Internet pubbliche.')
    return url

class Redirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,req,fp,code,msg,headers,newurl):
        public_url(newurl)
        return super().redirect_request(req,fp,code,msg,headers,newurl)

def fetch(url,cancel,*,local_provider=False):
    if cancel.is_set():raise Cancelled()
    if not local_provider:public_url(url)
    else:
        p=urllib.parse.urlsplit(url)
        if p.scheme not in ('http','https') or not p.hostname or p.username or p.password:raise ValueError('Indirizzo SearXNG non valido.')
    req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0 (compatible; H3-Chat)','Accept':'text/html,application/rss+xml,application/json','Accept-Encoding':'identity'})
    with urllib.request.build_opener(Redirects()).open(req,timeout=12) as r:
        if r.headers.get('Content-Encoding','identity').lower()!='identity':raise ValueError('La pagina richiede una decodifica non supportata.')
        mime=r.headers.get_content_type()
        if mime not in ('text/html','text/plain','application/rss+xml','text/xml','application/xml','application/json'):raise ValueError('Pagina web non testuale.')
        chunks=[];size=0
        while block:=r.read(32768):
            if cancel.is_set():raise Cancelled()
            size+=len(block)
            if size>1024*1024:break
            chunks.append(block)
        return b''.join(chunks).decode(r.headers.get_content_charset() or 'utf-8',errors='replace')

class Text(HTMLParser):
    def __init__(self):super().__init__(convert_charrefs=True);self.skip=0;self.parts=[]
    def handle_starttag(self,tag,attrs):
        if tag in ('script','style','noscript','svg'):self.skip+=1
        if tag in ('p','div','h1','h2','h3','li','br'):self.parts.append('\n')
    def handle_endtag(self,tag):
        if tag in ('script','style','noscript','svg'):self.skip=max(0,self.skip-1)
    def handle_data(self,data):
        if not self.skip:self.parts.append(data)
    def text(self):return re.sub(r'[ \t]+',' ',''.join(self.parts)).strip()

class Results(HTMLParser):
    def __init__(self):super().__init__(convert_charrefs=True);self.items=[];self.current=None;self.title=False;self.snippet=False
    def handle_starttag(self,tag,attrs):
        attrs=dict(attrs);classes=attrs.get('class','').split()
        if tag=='a' and 'result-link' in classes:
            url=attrs.get('href','');p=urllib.parse.urlsplit(url);url=urllib.parse.parse_qs(p.query).get('uddg',[url])[0]
            self.current={'title':'','url':url,'snippet':''};self.items.append(self.current);self.title=True
        if tag=='td' and 'result-snippet' in classes:self.snippet=True
    def handle_endtag(self,tag):
        if tag=='a':self.title=False
        if tag=='td':self.snippet=False
    def handle_data(self,data):
        if self.current and self.title:self.current['title']+=data
        if self.current and self.snippet:self.current['snippet']+=data

def query_text(prompt):
    return re.sub(r'^\s*(?:(?:puoi|per favore)\s+)?(?:cerca|ricerca|verifica|search|look up)\s*(?:(?:sul |nel |su )?(?:web|internet|online)\s*)?[:,-]?\s*','',prompt,flags=re.I).strip()[:500]

def relevant(item,query):
    site=re.search(r'\bsite:([\w.-]+)',query,re.I)
    if site:
        host=urllib.parse.urlsplit(item['url']).hostname or '';domain=site[1].lower()
        if host!=domain and not host.endswith('.'+domain):return False
    stop=set('cosa come quando dove quali quale ultimo ultime ultimi notizie news about what how when where documentation docs official sito sito web internet online search ricerca cerca verifica puoi informazioni sulle sulla sugli degli della dello delle che con per del dei nel sul una uno the and for from with'.split())
    terms=set(re.findall(r'\w{3,}',re.sub(r'\bsite:[\w.-]+','',query.lower())))-stop
    evidence=(item['title']+' '+item['snippet']+' '+item['url']).lower()
    return not terms or any(t in evidence for t in terms)

def requested(prompt,settings):
    if settings.get('_web'):return True
    if not settings.get('web_auto',True):return False
    opening=prompt.strip().lower()[:300]
    if re.search(r'\b(non cercare|senza (?:web|internet)|come (?:posso )?cercare|scrivi (?:un )?codice)\b',opening):return False
    return bool(re.search(r'\b(?:cerca|ricerca|verifica|search|look up)\b.{0,60}\b(?:web|internet|online|sul sito)\b',opening))

def search(query,settings,cancel,stage):
    import json
    query=query_text(query)
    if not query:raise ValueError('Scrivi cosa vuoi cercare sul web.')
    stage('Ricerca web · recupero delle fonti')
    if settings['web_provider']=='searxng':
        base=settings['web_searxng_url'].rstrip('/')
        if not base:raise ValueError('Configura l’indirizzo SearXNG nelle preferenze oppure scegli Bing.')
        raw=json.loads(fetch(base+'/search?'+urllib.parse.urlencode({'q':query,'format':'json'}),cancel,local_provider=True))
        candidates=[{'title':x.get('title',''),'url':x.get('url',''),'snippet':x.get('content','')} for x in raw.get('results',[])]
    elif settings['web_provider']=='duckduckgo':
        try:
            parser=Results();parser.feed(fetch('https://lite.duckduckgo.com/lite/?'+urllib.parse.urlencode({'q':query}),cancel));candidates=parser.items
        except Cancelled:raise
        except Exception:candidates=[]
        if not candidates:
            raw=fetch('https://www.bing.com/search?'+urllib.parse.urlencode({'q':query,'format':'rss'}),cancel)
            root=ET.fromstring(raw);candidates=[{'title':x.findtext('title',''),'url':x.findtext('link',''),'snippet':x.findtext('description','')} for x in root.findall('./channel/item')]
    else:
        raw=fetch('https://www.bing.com/search?'+urllib.parse.urlencode({'q':query,'format':'rss'}),cancel)
        root=ET.fromstring(raw)
        candidates=[{'title':x.findtext('title',''),'url':x.findtext('link',''),'snippet':x.findtext('description','')} for x in root.findall('./channel/item')]
    results=[];seen=set()
    for item in candidates[:20]:
        if cancel.is_set():raise Cancelled()
        if not all(isinstance(item.get(k),str) for k in ('title','url','snippet')):continue
        if not relevant(item,query):continue
        try:public_url(item['url'])
        except (ValueError,OSError):continue
        if item['url'] in seen:continue
        seen.add(item['url']);item={k:str(v)[:4000] for k,v in item.items()};item['read']=False
        stage('Ricerca web · lettura fonte '+str(len(results)+1))
        try:
            parser=Text();parser.feed(fetch(item['url'],cancel));item['text']=parser.text()[:16000]
            if len(item['text'])<2500 and re.search(r'client\s*challenge|enable javascript|verify.{0,20}human|checking your browser|access denied|just a moment|security verification',item['text'],re.I):raise ValueError('La pagina richiede un browser o blocca la lettura.')
            item['read']=bool(item['text'])
            if not item['read']:item['text']=item['snippet']
        except Cancelled:raise
        except Exception:item['text']=item['snippet']
        results.append(item)
        if len(results)>=settings['web_max_results']:break
    if not results:raise ValueError('Nessuna fonte web recuperata. Riprova o cambia provider; non è stata simulata una ricerca.')
    return results

def sources_markdown(sources):
    # Titles are inert labels; URLs originate from the verified provider response.
    return '\n\nFonti consultate:\n'+''.join(f"\n- [{i}. {re.sub(r'[\[\]\\\n\r]',' ',s['title']) or 'Fonte'}]({s['url'].replace(' ','%20').replace('(','%28').replace(')','%29')})"+(' · solo estratto' if not s['read'] else '') for i,s in enumerate(sources,1))

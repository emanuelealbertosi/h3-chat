"""Search public image candidates and import verified web material into H3."""
import json
import re
from html.parser import HTMLParser
from urllib.parse import urljoin,urlencode
from pathlib import Path
from .downloads import Cancelled
from .store import uid

WRITES={'import_web_images','import_web_sources','download_web_document'}


def page_links(html,base):
    from urllib.parse import urlsplit
    class Links(HTMLParser):
        def __init__(self):super().__init__();self.rows=[];self.current=None
        def handle_starttag(self,tag,attrs):
            if tag=='a':self.current={'url':urljoin(base,dict(attrs).get('href','')),'label':''}
        def handle_data(self,value):
            if self.current:self.current['label']+=value[:200]
        def handle_endtag(self,tag):
            if tag=='a' and self.current:
                p=urlsplit(self.current['url'])
                if p.scheme in ('http','https') and p.hostname and not p.username and not p.password and len(self.rows)<60:self.rows.append(self.current)
                self.current=None
    parser=Links();parser.feed(html);seen=set();result=[]
    for row in parser.rows:
        if row['url'] not in seen:seen.add(row['url']);result.append({'url':row['url'][:2000],'label':row['label'].strip()[:200]})
    return result

def definitions():
    def s(n=1000):return {'type':'string','maxLength':n}
    def obj(p,r):return {'type':'object','properties':p,'required':r,'additionalProperties':False}
    return {
     'download_web_document':('Scarica e salva un documento pubblico originale PDF, DOCX, TXT o Markdown, conservando l’URL. Non esegue il contenuto. Non richiede un progetto: poi puoi usare read_attachment sul risultato o importarlo nel RAG.',obj({'url':s(2000),'name':s(150)},['url','name'])),
     'read_web_page':('Leggi una pagina Internet pubblica, senza login o interazione browser, e conserva testo/URL fra le fonti Web del run. Se la pagina blocca la lettura dichiaralo.',obj({'url':s(2000)},['url'])),
     'search_web_images':('Cerca immagini tramite SearXNG se configurato, altrimenti recupera candidati dalle pagine trovate dal servizio Web H3. Restituisce ID, URL, pagina e descrizioni web, non una verifica visiva. Usa import_web_images per scaricarle in un lotto.',obj({'query':s(1200),'count':{'type':'integer','minimum':1,'maximum':20}},['query'])),
     'import_web_images':('Scarica le immagini scelte tramite ID restituiti da search_web_images, verificando il formato reale su CPU. Le aggiunge al lotto indicato per nome esatto o ID, creando il lotto se manca. Conserva provenienza e originali; non genera immagini e non inventa caption Vision.',obj({'image_ids':{'type':'array','items':s(32),'minItems':1,'maxItems':20},'lot_name':s(150),'lot_id':s(32)},['image_ids','lot_name'])),
     'import_web_sources':('Copia nel progetto le fonti Web numerate del run come documenti Markdown con URL. Accetta solo pagine realmente lette, non semplici snippet. Conserva duplicati per URL senza moltiplicarli. Usa poi index_project per indicizzare e verificare.',obj({'project_id':s(32),'numbers':{'type':'array','items':{'type':'integer','minimum':1,'maximum':20},'minItems':1,'maxItems':20}},['project_id','numbers'])),
    }

class Images(HTMLParser):
    def __init__(self):super().__init__(convert_charrefs=True);self.items=[]
    def handle_starttag(self,tag,attrs):
        a=dict(attrs);url='';label=''
        if tag=='meta' and a.get('property',a.get('name','')).lower() in ('og:image','twitter:image'):url=a.get('content','')
        if tag=='img':url=a.get('data-src') or a.get('src','');label=a.get('alt','')
        if tag=='a' and re.search(r'\.(?:png|jpe?g|webp)(?:\?|$)',a.get('href',''),re.I):url=a['href'];label=a.get('title','')
        if url and len(self.items)<30:self.items.append((url,label[:500]))

def remember(ctx,rows):
    saved=ctx.state.setdefault('web_sources',[])
    for row in rows:
        previous=next((s for s in saved if s['url']==row['url']),None)
        if previous:
            if row.get('read'):previous.update(row)
        elif len(saved)<20:saved.append(row)

def execute(ctx,name,args):
    from .web_search import fetch,public_url,Text,search
    from .agent_knowledge_tools import locked,activate,report
    if not ctx.settings.get('_web'):raise PermissionError('Attiva Web nella chat per cercare, leggere o importare materiali da Internet.')
    if name=='download_web_document':
        item=ctx.engine.tool_call('agent-web-image-worker.py',{'op':'document','data':str(ctx.app.data),'url':args['url'],'name':args['name'],'id':uid(),'folder':'outputs/'+ctx.action['id']},ctx.cancel,ctx.stage,ctx.log_path,timeout=60)
        value={'title':args['name'],'content':'Documento originale scaricato da '+args['url']+'. Leggilo con read_attachment prima di citarne il contenuto.','media':[item]}
        ctx.tool_app.save_artifact(ctx.job['chat_id'],**value)
        return ctx.artifact_result(value)|{'downloaded':True,'read':False,'source_url':args['url']}
    if name=='read_web_page':
        html=fetch(args['url'],ctx.cancel);parser=Text();parser.feed(html);text=parser.text()[:16000]
        if not text or re.search(r'enable javascript|verify.{0,20}human|checking your browser|access denied|just a moment',text[:2500],re.I):raise ValueError('La pagina blocca la lettura pubblica o richiede un browser. Nessun contenuto simulato.')
        row={'title':args['url'],'url':args['url'],'text':text,'snippet':'','read':True};remember(ctx,[row])
        number=next((i for i,s in enumerate(ctx.state['web_sources'],1) if s['url']==row['url']),None)
        if number is None:raise ValueError('Raggiunto il limite di 20 fonti Web per questa sessione Agent.')
        return {'source':row|{'number':number},'links':page_links(html,args['url']),'data_only':True}
    if name=='search_web_images':
        count=args.get('count',12);candidates=[]
        if ctx.settings['web_provider']=='searxng':
            base=ctx.settings['web_searxng_url'].rstrip('/')
            if not base:raise ValueError('Configura SearXNG nelle impostazioni Web.')
            data=json.loads(fetch(base+'/search?'+urlencode({'q':args['query'],'format':'json','categories':'images'}),ctx.cancel,local_provider=True))
            candidates=[{'url':v.get('img_src',''),'page':v.get('url',''),'label':v.get('title','')} for v in data.get('results',[])[:60]]
        else:
            rows=search(args['query'],ctx.settings,ctx.cancel,ctx.stage);remember(ctx,rows)
            for page in rows:
                try:
                    parser=Images();parser.feed(fetch(page['url'],ctx.cancel))
                    candidates.extend({'url':urljoin(page['url'],url),'page':page['url'],'label':label or page['title']} for url,label in parser.items)
                except Cancelled:raise
                except (OSError,ValueError):continue
        saved=ctx.state.setdefault('web_images',[]);result=[];seen=set()
        for item in candidates:
            ctx.check()
            if not all(isinstance(item.get(k),str) for k in ('url','page','label')) or item['url'] in seen:continue
            try:public_url(item['url']);public_url(item['page'])
            except (OSError,ValueError):continue
            seen.add(item['url']);previous=next((v for v in saved if v['url']==item['url']),None)
            if not previous:
                if len(saved)>=100:break
                previous={'id':uid(),**{k:v[:2000] for k,v in item.items()},'query':args['query']};saved.append(previous)
            result.append(previous)
            if len(result)>=count:break
        if not result:raise ValueError('Nessuna immagine pubblica recuperata. Prova una ricerca più specifica o un provider SearXNG con ricerca immagini; non sono stati inventati URL.')
        return {'images':result,'visual_review':False,'note':'Descrizioni provenienti dalle pagine, non analisi Vision.'}
    if name=='import_web_images':
        import time
        from .image_collections import listing,get,store_value
        selected=[]
        for ident in args['image_ids']:
            item=next((i for i in ctx.state.get('web_images',[]) if i['id']==ident),None)
            if not item:raise ValueError('Scegli solo ID immagini restituiti dalla ricerca di questa sessione.')
            selected.append(item)
        matches=[v for v in listing(ctx.app,limit=None)['items'] if v['name'].casefold()==args['lot_name'].strip().casefold()]
        if len(matches)>1 and not args.get('lot_id'):raise ValueError('Più lotti hanno questo nome: indica lot_id.')
        lot=get(ctx.app,args['lot_id']) if args.get('lot_id') else matches[0] if matches else {'id':ctx.action['id'],'name':args['lot_name'].strip(),'kind':'images','created':time.time(),'status':'done','images':[]}
        if lot.get('kind')!='images' or lot.get('status') in ('running','queued','cancelling'):raise ValueError('Scegli un lotto immagini disponibile e completato.')
        if len(lot['images'])+len(selected)>128:raise ValueError('Il lotto supererebbe il limite di 128 immagini.')
        done=[];errors=[]
        for source in selected:
            ctx.check()
            existing=next((i['media'] for i in lot['images'] if i.get('web_source',{}).get('url')==source['url']),None)
            try:
                if existing:item=existing
                else:
                    item=ctx.engine.tool_call('agent-web-image-worker.py',{'data':str(ctx.app.data),'url':source['url'],'id':uid(),'folder':'outputs/'+ctx.action['id']},ctx.cancel,ctx.stage,ctx.log_path,timeout=60)
                    item['web_source']={k:source[k] for k in ('url','page','label','query')}
                    lot['images'].append({'media':item,'caption':'','web_source':item['web_source']})
                    lot.update(total=len(lot['images']),status='done');store_value(ctx.app,lot)
                done.append(item)
            except (ValueError,RuntimeError,OSError) as error:errors.append({'id':source['id'],'error':str(error)[:350]})
            value={'title':'Lotto · '+lot['name'],'content':'Immagini scaricate: '+str(len(done))+'\n\n'+ '\n'.join(i.get('web_source',{}).get('page','') for i in done),'media':done}
            ctx.tool_app.save_artifact(ctx.job['chat_id'],**value);ctx.persist()
        return ctx.artifact_result(value)|{'lot_id':lot['id'] if done else None,'downloaded':len(done),'errors':errors,'visual_review':False}
    if name=='import_web_sources':
        k=ctx.app.knowledge;ident=args['project_id'];saved=ctx.state.get('web_sources',[]);selected=[]
        for n in args['numbers']:
            if n>len(saved) or not saved[n-1].get('read'):raise ValueError('Importa solo pagine realmente lette. Prima usa read_web_page per una fonte rimasta solo snippet.')
            selected.append(saved[n-1])
        records=[]
        with locked(ctx):
            k.mutable(ident,active_job=ctx.job['id'])
            for source in selected:
                ctx.check();existing=ctx.app.store.one('SELECT id,name FROM project_sources WHERE project_id=? AND source_url=?',(ident,source['url']))
                if existing:records.append(dict(existing)|{'url':source['url'],'duplicate':True});continue
                temporary=k.uploads.folder/(uid()+'.partial');label=re.sub(r'[^\w .()\-]','_',source['title'])[:170]+'.md'
                try:
                    temporary.write_text('# '+source['title']+'\n\nFonte: '+source['url']+'\n\n'+source['text'],encoding='utf8')
                    item=k.register_import(ident,{'name':label,'defer':True},temporary,active_job=ctx.job['id'])
                    ctx.app.store.execute('UPDATE project_sources SET source_url=? WHERE id=? AND project_id=?',(source['url'],item['id'],ident))
                    records.append(item|{'url':source['url']});report(ctx,'Fonti Web importate',{'project_id':ident,'sources':records,'indexed':False})
                finally:temporary.unlink(missing_ok=True)
        activate(ctx,ident);return report(ctx,'Fonti Web importate',{'project_id':ident,'sources':records,'indexed':False})
    raise ValueError('Strumento Web non disponibile.')

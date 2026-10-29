"""CPU-only typography revision of an existing shared poster plan."""
import copy,hashlib,json
from html.parser import HTMLParser
from .poster_type import DEFAULTS
from .posters import options
from .slides import PREFIX,FORMATS,encode,validate_content
from .poster_visual import validate,compose

class ZoneText(HTMLParser):
    def __init__(self,line_spans=True):super().__init__();self.zone=None;self.parts={};self.stack=[];self.line_spans=line_spans
    def handle_starttag(self,tag,attrs):
        if tag not in ('br','img','hr','input','meta','link'):self.stack.append((tag,self.zone))
        if tag=='section' and dict(attrs).get('data-poster-zone'):
            self.zone=dict(attrs)['data-poster-zone'];self.parts.setdefault(self.zone,[])
        if tag=='br' and self.zone:self.parts[self.zone].append(' ')
    def handle_endtag(self,tag):
        if self.zone and (tag in ('p','div','h1','h2','h3','h4','li','section','article','text') or tag=='span' and self.line_spans):self.parts[self.zone].append(' ')
        for n in range(len(self.stack)-1,-1,-1):
            if self.stack[n][0]==tag:self.zone=self.stack[n][1];self.stack=self.stack[:n];break
    def handle_data(self,value):
        if self.zone:self.parts[self.zone].append(value)

def loaded(app,chat_id,body):
    value=app.store.canvas_history.get(chat_id,body.get('artifact_id'));validate_content(value['content'],value['media'])
    if not value['content'].startswith(PREFIX):raise ValueError('Scegli una locandina con piano grafico condiviso.')
    deck=json.loads(value['content'][len(PREFIX):-4]);index=body.get('page',1)
    if deck.get('document_kind')!='poster' or type(index) is not int or not 1<=index<=len(deck['pages']):raise ValueError('Pagina locandina non valida.')
    page=deck['pages'][index-1];layout=page.get('poster_layout')
    if not layout or not page.get('poster_background'):raise ValueError('Questa locandina non conserva un piano condiviso. Usa Modifica grafica o rigenera la variante con le nuove impostazioni.')
    changes=body.get('typography',{})
    if not isinstance(changes,dict) or set(changes)-set(DEFAULTS):raise ValueError('Modifica tipografia non valida.')
    parsed=ZoneText(line_spans=not page.get('poster_fragments'));parsed.feed(page['html'])
    normalize=lambda s:' '.join(s.split())
    for zone in layout['zones']:
        if zone['renderer']=='html' and normalize(' '.join(parsed.parts.get(zone['id'],[])))!=normalize(zone['text']):raise ValueError('Il testo è stato modificato manualmente dopo il piano. Per conservarlo usa Modifica grafica: non sostituisco la pagina con testi precedenti.')
    return value,deck,page,layout,index,options(value=deck['poster']|changes)

def revise(app,chat_id,body):
    if app.store.one("SELECT id FROM jobs WHERE chat_id=? AND status IN ('queued','running') AND json_extract(payload,'$.canvas')=1",(chat_id,)):raise ValueError('Attendi o interrompi la creazione prima di cambiare la tipografia.')
    value,deck,page,layout,index,opts=loaded(app,chat_id,body)
    opts=opts|{'typography_engine':'preset'}
    width,height=FORMATS[deck['format']]
    styled=validate(layout,width,height,opts['safe_margin'],app.root,opts)
    original={z['id']:z for z in layout['zones'] if z['renderer']=='moss'}
    styled['zones']=[original.get(z['id'],z) for z in styled['zones']]
    page.pop('poster_fragments',None)
    page.update(poster_layout=styled,html=compose(styled,page['poster_background'],width,height));deck['poster']=opts;deck['active']=index-1
    return app.store.canvas_history.save(chat_id,{'title':value['title'],'content':encode(deck),'media':value['media']},editable=True)

def enqueue_creative(app,chat_id,body):
    """Queue a text-only creative revision, preserving the exact saved image."""
    value,_,_,_,index,opts=loaded(app,chat_id,body)
    prompt=body.get('prompt','')
    if not isinstance(prompt,str) or len(prompt)>2000:raise ValueError('Direzione tipografica troppo lunga.')
    settings=app.effective_settings(app.store.settings())
    app.engine.require_model(settings['chat_model'],'chat')
    spec={'artifact_id':value['id'],'page':index,'typography':{k:opts[k] for k in DEFAULTS},'prompt':prompt,'source_hash':hashlib.sha256(value['content'].encode()).hexdigest()}
    # No _posters flag: this operation must work in CPU mode with an API LLM
    # as well, and must never route to MOSS or resident image preparation.
    local=settings|{'_poster_creative':spec,'_rag':False,'_assistant':False,'_lab':'poster','vision_enabled':False}
    job=app.store.enqueue(chat_id,'Locandina · rinnova la tipografia della pagina '+str(index)+' mantenendo lo sfondo',[],local,True,[]);app.wake.set()
    return {'job_id':job,'intent':'poster_typography','canvas':True}

def run_creative(app,job,payload,settings,cancel,stage,log_path):
    from . import poster_overlay
    from .downloads import Cancelled
    spec=settings['_poster_creative'];value,deck,page,layout,index,opts=loaded(app,job['chat_id'],spec)
    if hashlib.sha256(value['content'].encode()).hexdigest()!=spec['source_hash']:raise ValueError('La locandina è cambiata dopo la richiesta. Ripeti la revisione sulla versione attuale per conservare le modifiche.')
    if cancel.is_set():raise Cancelled()
    width,height=FORMATS[deck['format']];opts=opts|{'typography_engine':'expressive'}
    styled=validate(copy.deepcopy(layout),width,height,opts['safe_margin'],app.root,opts)
    original={z['id']:z for z in layout['zones'] if z['renderer']=='moss'}
    styled['zones']=[original.get(z['id'],z) for z in styled['zones']]
    local=settings|{'memory_policy':'on_demand','ram_cache_gb':0}
    app.engine.configure(local);model=app.engine.require_model(local['chat_model'],'chat')
    app.engine.start_llama(model,local,log_path,cancel,stage=stage)
    proof=[];folder=app.data/'outputs'/job['id']
    def verify(fragments,attempt):
        stage('Locandina · verifica CPU dei testi')
        proof.append(poster_overlay.measure(app,styled,fragments,deck['format'],width,height,folder/f'typography-{attempt+1}',cancel,stage,log_path))
    fragments=poster_overlay.plan(app.engine,[],styled,opts|{'_settings':local,'_revision_prompt':spec.get('prompt','')},width,height,cancel,stage,verify)
    if cancel.is_set():raise Cancelled()
    page.update(html=poster_overlay.compose(styled,page['poster_background'],width,height,fragments),poster_layout=styled,poster_fragments=fragments,status='ready')
    deck['poster']=opts;deck['active']=index-1;content=encode(deck);validate_content(content,value['media'])
    # Always a new artifact identity: existing versions and image pixels survive.
    result=app.store.canvas_history.save(job['chat_id'],{'title':value['title'],'content':content,'media':value['media']},key='job:'+job['id'],message_id=job['message_id'])
    artifact={k:result[k] for k in ('title','content','media')}
    app.store.update_answer(job,'Nuova tipografia pronta nel canvas. Sfondo e versione precedente conservati. Le scritte già dipinte nell’immagine restano identiche.','done',[],{'intent':'poster_typography','artifact':artifact,'poster_typography_checks':proof,'source_artifact_id':value['id']})
    app.store.execute("UPDATE jobs SET status='done',stage='Tipografia locandina pronta' WHERE id=?",(job['id'],))

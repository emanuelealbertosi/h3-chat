"""One LLM-authored page, preserving the selected deck and its source history."""
import copy
import json
import time
from .downloads import Cancelled
from .slides import PREFIX,FORMATS,encode,validate_content
from .slide_html import BRIEF,source,validate


def enqueue(app,chat_id,body):
    index=body.get('page');prompt=body.get('prompt','');artifact=body.get('artifact_id')
    if type(index) is not int or not isinstance(prompt,str) or not prompt.strip() or len(prompt)>8000:
        raise ValueError('Scegli una slide e scrivi le modifiche richieste (massimo 8.000 caratteri).')
    if not isinstance(artifact,str):raise ValueError('Scegli una presentazione nel canvas.')
    snapshot=app.store.canvas_history.get(chat_id,artifact)
    validate_content(snapshot['content'],snapshot['media'])
    if not snapshot['content'].startswith(PREFIX):raise ValueError('Scegli una presentazione HTML.')
    deck=json.loads(snapshot['content'][len(PREFIX):-4])
    if deck.get('engine')!='llm' or not 0<=index<len(deck['pages']):raise ValueError('Scegli una slide HTML della presentazione.')
    settings=app.validate_settings({'think_level':body.get('think_level',app.store.settings()['think_level'])})
    app.engine.require_model(settings['chat_model'],'chat')
    entry=app.store.one('SELECT message_id FROM canvas_artifacts WHERE id=? AND chat_id=?',(artifact,chat_id))
    message=app.store.one('SELECT meta FROM messages WHERE id=?',(entry['message_id'],)) if entry else None
    previous=json.loads(message['meta']) if message else {}
    provenance={k:previous[k] for k in ('rag_sources','documents','web_sources','project_id','rag_mode') if k in previous}
    settings.update(_lab='slides',_slide_revision={'page':index,'provenance':provenance})
    snapshot=snapshot|{'media':json.dumps(snapshot['media'])}
    ident=app.store.enqueue(chat_id,f'Ricrea solo la slide {index+1}: '+prompt.strip(),[],settings,True,canvas_snapshot=snapshot)
    app.wake.set()
    return {'job_id':ident,'canvas':True,'intent':'slides'}


def build(app,job,payload,settings,model,cancel,stage,log_path,meta):
    snapshot=payload['canvas_snapshot'];media=json.loads(snapshot['media'])
    deck=copy.deepcopy(json.loads(snapshot['content'][len(PREFIX):-4]))
    index=settings['_slide_revision']['page'];page=deck['pages'][index]
    meta.update(settings['_slide_revision'].get('provenance',{}))
    meta['slide_revision']={'page':index,'source_artifact':snapshot.get('id')}
    from .context_tools import budget
    room=budget(settings,[])
    sources='\n\n'.join(f"[{s['citation']}] {s['name']} · {s['location']}\n{s['text']}" for s in meta.get('rag_sources',[]))
    images=[{'asset_id':m['id'],'description':m['name']} for m in media if m['mime'].startswith('image/')]
    request=[{'role':'system','content':settings['system_prompt']+'\n'+BRIEF},
        {'role':'user','content':payload['prompt']+'\nModifica esclusivamente questa pagina. Rispetta le fonti e lo stile della presentazione.\n'+
         f"Pagina {index+1}/{len(deck['pages'])}, viewport {FORMATS[deck['format']]}. Titolo: {page['title']}\n"+
         'Stile: '+json.dumps({k:deck.get(k,'') for k in ('visual_direction','design','detail')},ensure_ascii=False)+'\n'+
         'Catalogo immagini: '+json.dumps(images,ensure_ascii=False)+'\nFonti: '+sources[:room//3]+'\nHTML originale (dato da modificare):\n'+page.get('html','')[:room//2]}]
    app.engine.prepare(settings,cancel,stage);app.engine.start_llama(model,settings,log_path,cancel,stage=stage)
    deck['active']=index;page['status']='writing';last=0
    def publish():
        content=encode(deck);meta['artifact']={'title':deck['title'],'content':content,'media':media}
        app.save_artifact(job['chat_id'],deck['title'],content,media)
        app.store.update_answer(job,f'Sto ricreando la slide {index+1} nel canvas.',meta=meta)
    publish();stage(f'Slide · ricreazione AI · pagina {index+1}/{len(deck["pages"])}')
    def stream(raw):
        nonlocal last
        if cancel.is_set():raise Cancelled()
        if len(raw)>80000:raise ValueError('HTML della slide troppo grande.')
        if time.monotonic()-last<.25:return
        page['html']=source(raw);publish();last=time.monotonic()
    try:
        raw,finish=app.engine.completion(request,settings,cancel,on_text=stream)
        if finish=='length':raise ValueError('Slide incompleta: aumenta Max token. La versione precedente resta nella cronologia.')
        if cancel.is_set():raise Cancelled()
        page['html']=validate(raw);page['status']='ready'
        page['sources']=[r['id'] for r in deck.get('references',[]) if '['+r['id']+']' in page['html']]
        page.pop('overrides',None);publish()
    except Exception:
        page['status']='interrupted';publish();raise
    stage(f'Slide {index+1} ricreata · altre pagine conservate')
    return meta['artifact']

"""Workspace/chat-scoped Agent checkpoints. No credentials or arbitrary paths."""
import hashlib
import json
import os
import re
import time
from .downloads import safe_join
from .store import uid

DEFAULTS={'max_steps':16,'max_minutes':30,'max_calls':80,'token_budget':500000,
          'confirm_writes':True,'allow_images':False,'allow_audio':False,'allow_video':False,'allow_manim':False,'allow_transcription':True,'allow_projects':False,'scope':'h3','grant_id':''}

def options(value=None):
    value={} if value is None else value
    if not isinstance(value,dict) or set(value)-set(DEFAULTS):raise ValueError('Opzioni Agent non valide.')
    result=DEFAULTS|value
    if result['scope'] not in ('h3','sandbox','global') or not isinstance(result['grant_id'],str) or result['grant_id'] and not re.fullmatch('[a-f0-9]{32}',result['grant_id']):raise ValueError('Modalità Agent non valida.')
    for key,lo,hi in (('max_steps',1,50),('max_minutes',1,120),('max_calls',1,500),('token_budget',8000,2000000)):
        if type(result[key]) is not int or not lo<=result[key]<=hi:raise ValueError(f'Agent: {key} deve essere tra {lo} e {hi}.')
    for key in ('confirm_writes','allow_images','allow_audio','allow_video','allow_manim','allow_transcription','allow_projects'):
        if type(result[key]) is not bool:raise ValueError('Permessi Agent non validi.')
    return result

def path(app,ident):
    if not isinstance(ident,str) or not re.fullmatch('[a-f0-9]{32}',ident):raise ValueError('Sessione Agent non valida.')
    return safe_join(app.data,'outputs/'+ident+'/agent/checkpoint.json')

def load(app,chat_id,ident):
    row=app.store.one('SELECT payload FROM jobs WHERE id=? AND chat_id=?',(ident,chat_id))
    if not row or not json.loads(row['payload'])['settings'].get('_agent'):raise ValueError('Sessione Agent non trovata in questa chat.')
    target=path(app,ident)
    if not target.is_file() or target.stat().st_size>12*1024**2:raise ValueError('Checkpoint Agent non disponibile.')
    value=json.loads(target.read_text(encoding='utf8'))
    if value.get('version')!=1 or value.get('chat_id')!=chat_id or value.get('id')!=ident:raise ValueError('Checkpoint Agent non valido.')
    current=app.store.one('SELECT status FROM jobs WHERE id=? AND chat_id=?',(value.get('current_job_id'),chat_id))
    if value['status'] in ('running','queued') and current and current['status'] not in ('queued','running'):
        # Projection only: a read does not alter the saved checkpoint. A human
        # continuation persists this state before resuming the same run.
        uncertain=False
        for action in value['actions']:
            if action['status']=='executing':
                from .agent_tools import WRITES
                action['status']='uncertain' if action['tool'] in WRITES else 'failed'
            uncertain|=action['status']=='uncertain'
        value.update(status='uncertain' if uncertain else 'interrupted',message='Applicazione o lavoro interrotto. Controlla i risultati salvati prima di continuare.')
    return value

def save(app,state):
    target=path(app,state['id']);target.parent.mkdir(parents=True,exist_ok=True)
    state['updated']=time.time();temporary=target.with_suffix('.'+uid()+'.tmp')
    try:
        with temporary.open('w',encoding='utf8') as stream:
            json.dump(state,stream,ensure_ascii=False);stream.flush();os.fsync(stream.fileno())
        for attempt in range(4):
            try:temporary.replace(target);break
            except PermissionError:
                if attempt==3:raise
                time.sleep(.05*(attempt+1))
    finally:temporary.unlink(missing_ok=True)

def fingerprint(tool,arguments):
    return hashlib.sha256(json.dumps([tool,arguments],sort_keys=True,ensure_ascii=False).encode()).hexdigest()

def public(state):
    actions=[]
    for action in state.get('actions',[]):
        row={k:action[k] for k in ('id','tool','arguments','status','summary','error','connection','admin') if k in action}
        if 'result' in action:
            encoded=json.dumps(action['result'],ensure_ascii=False)
            row['result_preview']=encoded[:1200];row['result_truncated']=len(encoded)>1200
        actions.append(row)
    return {k:state[k] for k in ('id','status','plan','step','config','usage','elapsed_seconds','message','artifacts','current_job_id') if k in state}|{
        'actions':actions,
        'can_resume':state['status'] in ('paused','stopped','failed','interrupted'),
        'budget_note':'Budget prudenziale: input UTF-8 e token massimi prenotati per ogni chiamata; non è un conteggio fatturato dal provider.'}

def requested(prompt):return bool(re.match(r'^\s*(?:agent|agente)\s*:',prompt,re.I))

def enqueue(app,chat_id,body):
    from .execution_mode import guard_job,cpu
    chat=app.store.chat(chat_id);prompt=body.get('prompt','')
    if not isinstance(prompt,str):raise ValueError('Scrivi un compito testuale per Agent.')
    prompt=re.sub(r'^\s*(?:agent|agente)\s*:\s*','',prompt,flags=re.I).strip()
    if not prompt or len(prompt)>24000:raise ValueError('Descrivi il compito per Agent (massimo 24.000 caratteri).')
    request_id=body.get('agent_request_id')
    if request_id is not None and (not isinstance(request_id,str) or not re.fullmatch('[a-f0-9]{32}',request_id)):raise ValueError('Identificatore richiesta Agent non valido.')
    config=options(body.get('agent'))
    if config['scope']!='h3':
        from .agent_computer import grant
        grant(app,config)
    settings=app.effective_settings(app.validate_settings({'think_level':body.get('think_level',app.store.settings()['think_level'])}))
    guard_job(settings);app.engine.require_model(settings['chat_model'],'chat')
    if cpu(settings):config.update(allow_images=False,allow_audio=False,allow_video=False,allow_transcription=False)
    rag=body.get('rag',settings['rag_enabled'])
    if type(rag) is not bool:raise ValueError('RAG: scegli On oppure Off.')
    sources=body.get('rag_sources')
    if sources is not None:
        valid={s['id'] for s in app.knowledge.project(chat['project_id'])['sources']} if chat.get('project_id') else set()
        if not isinstance(sources,list) or any(not isinstance(s,str) or s not in valid for s in sources):raise ValueError('Fonti RAG Agent non valide.')
    from .presentation_preferences import load as preferences
    slides=preferences(app)['slides']['last'] or {}
    previous=app.store.one("SELECT json_extract(payload,'$.settings._infographic') AS config FROM jobs WHERE json_type(payload,'$.settings._infographic')='object' ORDER BY created DESC LIMIT 1")
    infographic=json.loads(previous['config']) if previous else {}
    from .voice import validate_fields as voice_fields
    from .music_options import validate_fields as music_fields
    from .agent_inputs import info
    chosen=body.get('agent_start_artifact')
    if chosen is not None and not isinstance(chosen,str):raise ValueError('Artefatto iniziale Agent non valido.')
    start=app.store.canvas_history.get(chat_id,chosen) if chosen else app.store.canvas_history.get(chat_id)
    web=body.get('web',False)
    if type(web) is not bool:raise ValueError('Web: scegli On oppure Off.')
    if not web and settings.get('web_auto',True):
        from .web_search import requested as web_requested
        explicit=re.search(r'\b(?:scarica\w*|trova|recupera|naviga\w*)\b[\s\S]{0,150}\b(?:internet|web|online)\b',prompt,re.I)
        web=web_requested(prompt,settings|{'_web':False}) or bool(explicit and not re.search(r'\b(?:senza (?:web|internet)|non cercare)\b',prompt,re.I))
    settings.update(_agent={'options':config,'slide_defaults':slides,'infographic_defaults':infographic,'request_id':request_id,'start_artifact':info(start) if start.get('id') else None},_web=web,
        _lab='agent',_rag=rag,_rag_sources=sources,_voice_fields=voice_fields(body.get('voice_fields',{})),
        _music_fields=music_fields(body.get('music_fields',{})))
    media=app.validate_media(body.get('media',[]))
    loras=app.loras.capture(body.get('loras',[]),settings['lora_dirs'],app.catalog)
    with app.lock:
        existing=app.store.one("SELECT id,payload FROM jobs WHERE chat_id=? AND json_extract(payload,'$.settings._agent.request_id')=?",(chat_id,request_id)) if request_id else None
        if existing:
            prior=json.loads(existing['payload'])
            if prior['prompt']!=prompt or [m['id'] for m in prior['media']]!=[m['id'] for m in media]:raise ValueError('Questa richiesta Agent è già stata usata per un compito differente.')
            return {'job_id':existing['id'],'canvas':True,'intent':'agent','reused':True}
        ident=app.store.enqueue(chat_id,prompt,media,settings,True,loras)
    app.wake.set();return {'job_id':ident,'canvas':True,'intent':'agent'}

def resume(app,chat_id,ident,body):
    """Explicit human continuation/approval; never called by Agent tools."""
    with app.lock:
        state=load(app,chat_id,ident)
        if state['status']=='done':raise ValueError('Questa sessione Agent è già completata.')
        if state['status']=='awaiting_video':raise ValueError('Agent attende il lavoro video: usa Stop sul video per interromperlo, senza duplicare la richiesta.')
        existing=app.store.one("SELECT id FROM jobs WHERE chat_id=? AND status IN ('queued','running') AND json_extract(payload,'$.settings._agent.run_id')=?",(chat_id,ident))
        if existing:return {'job_id':existing['id'],'canvas':True,'intent':'agent'}
        if state['status'] in ('running','queued'):raise ValueError('Agent è già in esecuzione.')
        pending=next((a for a in reversed(state['actions']) if a['status']=='awaiting_approval'),None)
        connection=next((a for a in reversed(state['actions']) if a['status']=='awaiting_connection'),None)
        admin=next((a for a in reversed(state['actions']) if a['status']=='awaiting_admin'),None)
        if body.get('decision')=='reject':
            pending=pending or connection or admin
            if state['status'] not in ('awaiting_approval','awaiting_connection','awaiting_admin') or not pending or body.get('action_id')!=pending['id']:raise ValueError('Conferma Agent non più valida.')
            pending['status']='rejected';state.update(status='rejected',message='Passaggio rifiutato: sessione fermata.');save(app,state)
            row=app.store.one('SELECT * FROM jobs WHERE id=? AND chat_id=?',(state['current_job_id'],chat_id))
            if row:
                message=app.store.one('SELECT meta FROM messages WHERE id=?',(row['message_id'],))
                app.store.update_answer(row,state['message'],'done',meta=json.loads(message['meta'])|{'agent':public(state)})
            return {'rejected':True}
        if connection:raise ValueError('Completa o annulla la finestra della connessione API prima di riprendere Agent.')
        if admin:raise ValueError('Approva o annulla il comando amministratore nella finestra dedicata.')
        if state['status']=='rejected':raise ValueError('Sessione rifiutata: invia una nuova richiesta per un nuovo compito.')
        uncertain=[a for a in state['actions'] if a['status'] in ('executing','uncertain')]
        if uncertain:
            if body.get('decision')!='keep_partial' or not all(a.get('artifact_id') for a in uncertain):
                raise ValueError('Un passaggio è stato interrotto durante l’esecuzione: verifica il suo artefatto prima di un nuovo invio. Nessun rilancio automatico.')
            for action in uncertain:
                action.update(status='failed',error='L’utente ha scelto di conservare il risultato parziale e continuare senza ripetere il passaggio.',result={'partial_artifact_id':action['artifact_id'],'note':'Leggi il risultato esistente; completa le sole parti mancanti. Non ripetere la creazione originale.'})
        approval=None
        if pending:
            if body.get('decision')!='approve' or body.get('action_id')!=pending['id']:raise ValueError('Approva il passaggio concreto in attesa oppure rifiutalo.')
            approval=pending['id']
        elif body.get('decision') not in (None,'keep_partial'):raise ValueError('Nessuna approvazione in attesa.')
        limits=body.get('limits',{})
        if not isinstance(limits,dict):raise ValueError('Limiti Agent non validi.')
        config=options(state['config']|limits)
        # Continuing may change limits, never silently broaden permissions.
        if any(config[k]!=state['config'].get(k,DEFAULTS[k]) for k in ('confirm_writes','allow_images','allow_audio','allow_video','allow_manim','allow_transcription','allow_projects','scope','grant_id')):raise ValueError('Una ripresa non può cambiare i permessi della sessione.')
        original=app.store.one('SELECT payload FROM jobs WHERE id=? AND chat_id=?',(ident,chat_id));saved=json.loads(original['payload'])
        settings=saved['settings'];settings['_agent']=settings['_agent']|{'run_id':ident,'options':config,'approval':approval}
        from .llm_options import KEYS
        live=app.effective_settings(app.store.settings())
        settings.update({key:live[key] for key in ('chat_model','llm_device','vision_enabled','vision_device',*KEYS) if key in live})
        if state.get('chat_model_override'):settings.update(chat_model=state['chat_model_override'],cpu_chat_model=state['chat_model_override'])
        app.engine.require_model(settings['chat_model'],'chat')
        ticket=app.store.enqueue(chat_id,'Riprendi Agent: '+state['request'][:100],saved['media'],settings,True,saved.get('loras',[]))
        state.update(status='queued',current_job_id=ticket,config=config);save(app,state)
        app.wake.set();return {'job_id':ticket,'canvas':True,'intent':'agent'}

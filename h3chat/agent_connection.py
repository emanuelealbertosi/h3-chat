"""Human-only credential dialog. Secret bytes never enter Agent state or jobs."""
import json
from . import agent_state
from .providers import validate

class AwaitConnection(Exception):pass

FIELDS={'name','base_url','model','vision','max_refs','thinking','format','preset'}

def prepare(ctx,args):
    if getattr(ctx.app,'execution_owner',ctx.app) is not ctx.app:raise PermissionError('La configurazione dei collegamenti API è riservata al proprietario dell’app.')
    config,_=validate(args)
    ctx.action.update(connection=config,status='awaiting_connection')
    ctx.state.update(status='awaiting_connection',message='Inserisci la chiave nella finestra della connessione API. Agent riprenderà dopo il salvataggio; nessuna chiave viene passata al modello.')
    raise AwaitConnection()

def submit(app,chat_id,run_id,body):
    if getattr(app,'execution_owner',app) is not app:raise PermissionError('La configurazione dei collegamenti API è riservata al proprietario dell’app.')
    if not isinstance(body,dict) or set(body)-{'action_id','config','api_key','use_for_run','operation'}:raise ValueError('Dati connessione non validi.')
    with app.lock:
        state=agent_state.load(app,chat_id,run_id)
        action=next((a for a in state['actions'] if a['id']==body.get('action_id') and a['tool']=='configure_api'),None)
        if not action:raise ValueError('Richiesta di connessione non trovata in questa sessione.')
        if action['status']=='done':return {'provider_id':action['result']['provider_id'],'job_id':state['current_job_id'],'reused':True}
        if state['status']!='awaiting_connection' or action['status']!='awaiting_connection':raise ValueError('Questa richiesta non attende una connessione API.')
        config=body.get('config',{})
        if not isinstance(config,dict) or set(config)-FIELDS:raise ValueError('Campi connessione non validi.')
        use=body.get('use_for_run',False)
        if type(use) is not bool:raise ValueError('Scegli se usare il collegamento in questa sessione.')
        operation=body.get('operation','save')
        if operation not in ('save','test'):raise ValueError('Operazione connessione non valida.')
        # Password is validated only by the existing credential store. It never
        # becomes an action argument, an observation, a prompt or a checkpoint.
        request={k:v for k,v in action['connection'].items() if k in FIELDS}|config|{'api_key':body.get('api_key','')}
        validate(request,action['connection']['id'])
        if operation=='test':return app.provider_request(request,'test')
        if app.current_id or app.store.one("SELECT id FROM jobs WHERE status IN ('queued','running')"):raise ValueError('Attendi la fine del lavoro in corso prima di salvare il collegamento; la finestra resta disponibile.')
        if len(app.providers.list())>=100 and not app.store.one('SELECT id FROM api_providers WHERE id=?',(action['connection']['id'],)):raise ValueError('Massimo cento collegamenti API.')
        result=app.providers.save(request,prepared_id=action['connection']['id'])
        app.refresh_models();app.engine.configure(app.store.settings())
        action.update(status='done',connection={k:v for k,v in result.items() if k in FIELDS or k=='id'},
                      result={'provider_id':result['id'],'name':result['name'],'model':result['model'],'has_key':result['has_key'],'saved':True,'tested':False,'used_for_run':use})
        if use:state['chat_model_override']=result['id']
        state.update(status='paused',message='Collegamento API salvato dalla finestra protetta. Agent può proseguire.');agent_state.save(app,state)
        # The next job contains only the provider ID. The encrypted key remains
        # in api_providers and is resolved by the engine when actually needed.
        resumed=agent_state.resume(app,chat_id,run_id,{})
        return resumed|{'provider_id':result['id'],'saved':True}

"""Typed video jobs, delegated to H3's durable queue instead of blocking Agent."""
import copy
import json
import logging
import re

WRITES={'create_video','edit_video','resume_video','assemble_video'}
class AwaitVideo(RuntimeError):pass


def definitions():
    from .agent_tools import obj,string,ID
    versions={'type':'array','maxItems':100,'items':obj({'clip':{'type':'integer','minimum':1,'maximum':100},'version':ID},['clip','version'])}
    segment={'type':'integer','enum':[5,10,15]}
    common={'source':ID,'segment_seconds':segment}
    patch=obj({'clip':{'type':'integer','minimum':1,'maximum':100},'prompt':string(6000),
        'mode':{'type':'string','enum':['reference','i2v','video']},'images':{'type':'array','maxItems':9,'items':{'type':'integer','minimum':1,'maximum':128}},
        'lip_sync':{'type':'boolean'},'audio_guide':{'type':'boolean'},'recover_memory':{'type':'boolean'},
        'start_image':{'type':'integer','minimum':1,'maximum':128},'end_frame':{'type':'string','enum':['none','original','next']},
        'end_image':{'type':'integer','minimum':1,'maximum':128}},['clip','prompt'])
    parameters=obj({'duration':{'type':'number','minimum':1,'maximum':600},'megapixels':{'type':'number','minimum':0.1,'maximum':4},
        'aspect':{'type':'string','enum':['16:9','9:16','1:1','4:3','3:4']},'seed':{'type':'integer','minimum':-1,'maximum':2147483647},
        'variants':{'type':'integer','minimum':1,'maximum':8},'variants_mode':{'type':'string','enum':['clip','video']}})
    return {
      'list_video_timelines':('Elenca i lavori video e le timeline salvati di questa chat; nessuna generazione o valutazione visiva.',obj({})),
      'inspect_video_timeline':('Legge clip, prompt, seed, versioni e memoria di una timeline scelta di questa chat. Non guarda o ascolta il filmato.',obj(common,['source'])),
      'create_video':('Genera un video corto, lungo, musicale o con riferimenti usando il motore H3 e le impostazioni salvate. reference_numbers sceglie esplicitamente gli allegati numerati (anche da source_artifact_ids). Assistant è spento di default. La coda esegue il video, poi Agent riprende con lo stesso budget; nessun rilancio automatico in caso di errore o Stop.',obj({
        'prompt':string(24000),'model_id':string(150),'reference_numbers':{'type':'array','items':{'type':'integer','minimum':1,'maximum':128},'maxItems':13},
        'parameters':parameters,'segment_seconds':segment,'assistant':{'type':'boolean'},
        'editing':{'type':'string','enum':['continuous','storyboard']},
        'input_mode':{'type':'string','enum':['auto','i2v'],'description':'Per animare una foto usa i2v: la prima immagine scelta è il fotogramma iniziale vincolante anche con Assistant On. auto conserva le istruzioni del prompt, inclusi i normali riferimenti di identità/stile.'}},['prompt'])),
      'edit_video':('Rigenera clip intere con il normale editor H3, salvando versioni e memoria. source deve essere un lavoro o un video allegato della stessa chat. Gli indici immagini seguono inspect_video_timeline; end_frame usa il raccordo finale esistente. Non inventare l’identità o la voce osservata.',obj(common|{'patches':{'type':'array','items':patch,'minItems':1,'maxItems':100},'model_id':string(150),'assistant':{'type':'boolean'},'remount':{'type':'boolean'}},['source','patches'])),
      'resume_video':('Riprende solo clip mancanti di un lavoro preciso, già interrotto, di questa chat. Usalo solo se l’utente chiede di riprendere: non aggirare Stop o errori con rilanci automatici.',obj({'source':ID},['source'])),
      'assemble_video':('Monta su CPU una timeline della chat e le versioni scelte, senza nuove generazioni. Le versioni originali restano salvate.',obj(common|{'versions':versions},['source']))}


def source_owned(ctx,ident):
    if ctx.app.store.one('SELECT id FROM jobs WHERE id=? AND chat_id=?',(ident,ctx.job['chat_id'])):return
    if any(m['id']==ident and m.get('mime','').startswith('video/') for m in ctx.tool_payload['media']):return
    raise ValueError('Scegli un lavoro video di questa chat oppure collega esplicitamente il suo artefatto/allegato.')


def execute(ctx,name,args):
    app=ctx.app;chat=ctx.job['chat_id']
    if name=='list_video_timelines':
        rows=app.store.all("SELECT j.id,j.status,j.stage,j.payload,m.meta FROM jobs j JOIN messages m ON m.id=j.message_id WHERE j.chat_id=? ORDER BY j.created DESC LIMIT 150",(chat,))
        result=[]
        for row in rows:
            payload=json.loads(row['payload']);settings=payload['settings'];meta=json.loads(row['meta'])
            if not (settings.get('_video') or any(settings.get(k) for k in ('_video_edit','_video_assemble','_video_resume_origin'))):continue
            result.append({'source':row['id'],'status':row['status'],'stage':row['stage'],'prompt':payload['prompt'][:1000],
                'parameters':meta.get('video_parameters',{}),'has_timeline':(app.data/'outputs'/row['id']/'scenes.json').is_file()})
        return {'videos':result,'visual_inspection':False}
    if args.get('source'):source_owned(ctx,args['source'])
    if name=='inspect_video_timeline':
        from .video_edit import describe
        value=describe(app,chat,args['source'],args.get('segment_seconds'))
        # Browser URLs add no information for the LLM and can be large.
        for clip in value.get('clips',[]):clip.pop('url',None)
        return value|{'visual_inspection':False,'audio_listened':False}
    if ctx.state['usage'].get('video_jobs_started',0)>=8:raise ValueError('Raggiunto il limite di 8 lavori video per questa sessione Agent.')
    # Save intent BEFORE queue submission; the Agent ticket must finish first,
    # since Store rejects all sends while a workspace ticket is still active.
    body={k:copy.deepcopy(v) for k,v in args.items() if k!='source_artifact_ids'}
    if name=='create_video':
        if re.match(r'^\s*(agent|agente)\s*:',args['prompt'],re.I):raise ValueError('Il prompt del motore video non deve richiamare Agent.')
        numbers=args.get('reference_numbers',[]);media=ctx.tool_payload['media']
        if len(numbers)!=len(set(numbers)) or any(n>len(media) for n in numbers):raise ValueError('Riferimenti video numerati non validi.')
        selected=[media[n-1] for n in numbers]
        if any(not m['mime'].startswith(('image/','audio/','video/')) for m in selected):raise ValueError('Per Video scegli immagini, audio o video espliciti.')
        prompt=args['prompt']
        if args.get('input_mode')=='i2v':
            if not any(m['mime'].startswith('image/') for m in selected):raise ValueError('I2V: scegli l’immagine iniziale con reference_numbers.')
            prompt='I2V. Use <Picture 1> as the first frame at 0 seconds. Preserve the initial composition, then animate the requested motion.\n'+prompt
        # The actual H3 validators enforce media counts and model compatibility.
        body={'prompt':prompt,'video':True,'canvas':True,'assistant':args.get('assistant',False),'rag':False,'web':False,
            'media':[{'id':m['id']} for m in selected],'video_editing':args.get('editing','continuous')}
        body['loras']=[{k:l[k] for k in ('id','weight','model_id')} for l in ctx.payload.get('loras',[]) if 'video' in ctx.app.catalog.get(l['model_id'],{}).get('capabilities',[])]
        if args.get('model_id'):body['video_model']=args['model_id']
        if args.get('parameters'):body['video_parameters']=args['parameters']
        if args.get('segment_seconds'):body['video_segment_seconds']=args['segment_seconds']
    elif name=='edit_video':
        body={'source':args['source'],'patches':copy.deepcopy(args['patches']),'canvas':True,'assistant':args.get('assistant',False),'remount':args.get('remount',True)}
        for item in body['patches']:
            if 'end_image' in item:
                if item.get('end_frame','none')!='none':raise ValueError('Scegli una sola guida per il fotogramma finale.')
                item['end_frame']=item.pop('end_image')
        if args.get('segment_seconds'):body['segment_seconds']=args['segment_seconds']
        if args.get('model_id'):body['model']=args['model_id']
    elif name=='resume_video':body={'job_id':args['source']}
    elif name=='assemble_video':
        body={'source':args['source'],'canvas':True,'versions':{str(v['clip']):v['version'] for v in args.get('versions',[])}}
        if args.get('segment_seconds'):body['segment_seconds']=args['segment_seconds']
    settings=copy.deepcopy(ctx.settings)
    for key in list(settings):
        if key.startswith('_'):settings.pop(key)
    ctx.action.update(status='awaiting_video',video={'tool':name,'body':body,'settings':settings,'phase':'prepared'})
    ctx.state.update(status='awaiting_video',agent_ticket_id=ctx.job['id'],message='Video preparato: Agent attende la coda H3 e riprenderà dopo il risultato.')
    ctx.persist();raise AwaitVideo()


class QueueStore:
    def __init__(self,app,state,action):self.app=app;self.state=state;self.action=action
    def __getattr__(self,key):return getattr(self.app.store,key)
    def settings(self):return copy.deepcopy(self.action['video']['settings'])
    def enqueue(self,chat_id,prompt,media,settings,*args,**kwargs):
        settings=dict(settings);settings.pop('_agent',None)
        settings['_agent_video_origin']={'run_id':self.state['id'],'action_id':self.action['id']}
        return self.app.store.enqueue(chat_id,prompt,media,settings,*args,**kwargs)
    def resume_video(self,chat_id,ident):
        # resume_video internally calls Store.enqueue; delegate through a proxy
        # so the origin marker is inside the same queue transaction.
        from .store import Store
        return Store.resume_video(self,chat_id,ident)


class QueueApp:
    def __init__(self,app,state,action):self.app=app;self.store=QueueStore(app,state,action)
    def __getattr__(self,key):return getattr(self.app,key)
    def validate_settings(self,changes):
        # Stored settings were validated at the original Agent submission.
        return self.store.settings()|changes


def publish_wait(app,state):
    from . import agent_state as ledger
    row=app.store.one('SELECT * FROM jobs WHERE id=? AND chat_id=?',(state.get('agent_ticket_id',state['id']),state['chat_id']))
    if not row:return
    answer=app.store.one('SELECT meta FROM messages WHERE id=?',(row['message_id'],))
    app.store.update_answer(row,state['message'],'done',meta=json.loads(answer['meta'])|{'agent':ledger.public(state)})


def reconcile(app,run_id,chat_id):
    from . import agent_state as ledger
    with app.lock:
        state=ledger.load(app,chat_id,run_id)
        if state['status']!='awaiting_video':return
        action=next((a for a in reversed(state['actions']) if a['status']=='awaiting_video'),None)
        if not action:return
        draft=action['video'];origin=(run_id,action['id'])
        child=app.store.one("SELECT * FROM jobs WHERE chat_id=? AND json_extract(payload,'$.settings._agent_video_origin.run_id')=? AND json_extract(payload,'$.settings._agent_video_origin.action_id')=? ORDER BY created DESC LIMIT 1",(chat_id,*origin))
        if not child and draft.get('job_id'):
            child=app.store.one('SELECT * FROM jobs WHERE id=? AND chat_id=?',(draft['job_id'],chat_id))
        if not child and draft['phase']=='prepared':
            if app.store.one("SELECT id FROM jobs WHERE status IN ('queued','running')"):return
            # Durable uncertain state: a crash here is reconciled by exact origin,
            # never by guessing from an empty queue or repeating the submission.
            draft['phase']='uncertain_submission';ledger.save(app,state)
            proxy=QueueApp(app,state,action)
            try:
                tool=draft['tool'];body=draft['body']
                if tool=='create_video':
                    from .service import Service
                    result=Service.send(proxy,chat_id,body)
                elif tool=='edit_video':
                    from .video_edit import request
                    result=request(proxy,chat_id,body)
                elif tool=='assemble_video':
                    from .video_assemble import request
                    result=request(proxy,chat_id,body)
                else:
                    from .video_job_resume import request
                    result=request(proxy,chat_id,body)
                draft.update(phase='submitted',job_id=result['job_id']);state['current_job_id']=result['job_id']
                state['usage']['video_jobs_started']=state['usage'].get('video_jobs_started',0)+1
                ledger.save(app,state);publish_wait(app,state);return
            except (ValueError,PermissionError) as error:
                action.update(status='failed',error=str(error)[:800],result={'error':str(error)[:800]})
                state.update(status='failed',message='Il video non è stato avviato: '+str(error)[:800]);ledger.save(app,state);publish_wait(app,state);return
        if not child:
            state.update(status='uncertain',message='Invio video incerto: verifica la coda e i risultati. Nessun secondo invio automatico.')
            action.update(status='uncertain');ledger.save(app,state);publish_wait(app,state);return
        draft.update(phase='submitted',job_id=child['id']);state['current_job_id']=child['id']
        if child['status'] in ('queued','running'):
            ledger.save(app,state);return
        if child['status']!='done':
            action.update(status='failed',error=child.get('error') or child['stage'],result={'job_id':child['id'],'status':child['status']})
            state.update(status='stopped' if child['status']=='cancelled' else 'failed',message='Video '+child['status']+'. Le clip già salvate restano disponibili; nessun rilancio automatico.')
            ledger.save(app,state);publish_wait(app,state);return
        answer=app.store.one('SELECT meta,media,content FROM messages WHERE id=?',(child['message_id'],))
        meta=json.loads(answer['meta']);value=meta.get('artifact') or {'title':'Video','content':'','media':json.loads(answer['media'])}
        saved=app.store.canvas_history.save(chat_id,value,key='job:'+child['id'],message_id=child['message_id'])
        artifact={'id':saved['id'],'title':value['title'],'tool':action['tool']}
        if not any(v['id']==artifact['id'] for v in state['artifacts']):state['artifacts'].append(artifact)
        action.update(status='done',artifact_id=saved['id'],result={'job_id':child['id'],'status':'done','artifact_id':saved['id'],'visual_inspection':False})
        state.update(status='paused',last_artifact=saved['id'],message='Video pronto. Agent riprende dai risultati salvati.');ledger.save(app,state);publish_wait(app,state)
        try:ledger.resume(app,chat_id,run_id,{})
        except (ValueError,PermissionError) as error:
            state.update(message='Video pronto; ripresa Agent in pausa: '+str(error)[:500]);ledger.save(app,state);publish_wait(app,state)


def stop_waiting(app,job):
    """Honor Stop even if the browser still holds the completed Agent ticket."""
    from . import agent_state as ledger
    answer=app.store.one('SELECT meta FROM messages WHERE id=?',(job['message_id'],))
    public=json.loads(answer['meta']).get('agent',{}) if answer else {}
    if public.get('status')!='awaiting_video':return False
    with app.lock:
        state=ledger.load(app,job['chat_id'],public['id'])
        if state['status']!='awaiting_video':return False
        target=state.get('current_job_id');state.update(status='stopped',message='Agent e video fermati su richiesta. Nessun rilancio automatico.')
        for action in state['actions']:
            if action['status']=='awaiting_video':action.update(status='failed',error='Fermato dall’utente.',result={'status':'cancelled','job_id':target})
        ledger.save(app,state);publish_wait(app,state)
        if target!=job['id']:
            child=app.store.one('SELECT status FROM jobs WHERE id=? AND chat_id=?',(target,job['chat_id']))
            if child and child['status'] in ('queued','running'):app.cancel(target)
        return True


def reconcile_pending(app,cancelled_job=None):
    if cancelled_job:
        row=app.store.one('SELECT * FROM jobs WHERE id=?',(cancelled_job,))
        if row:stop_waiting(app,row)
    rows=app.store.all("SELECT j.chat_id,m.meta FROM jobs j JOIN messages m ON m.id=j.message_id WHERE json_extract(m.meta,'$.agent.status')='awaiting_video' ORDER BY j.created DESC LIMIT 100")
    seen=set()
    for row in rows:
        ident=json.loads(row['meta'])['agent']['id']
        if ident in seen:continue
        seen.add(ident)
        try:reconcile(app,ident,row['chat_id'])
        except Exception as error:
            logging.exception('Agent video reconciliation failed for %s',ident)
            try:
                from . import agent_state as ledger
                state=ledger.load(app,row['chat_id'],ident)
                if state['status']=='awaiting_video':
                    from .agent_state import save
                    for action in state['actions']:
                        if action['status']=='awaiting_video':action.update(status='uncertain',error=str(error)[:500])
                    state.update(status='uncertain',message='Collegamento al video da verificare. Nessun nuovo invio automatico.');save(app,state);publish_wait(app,state)
            except Exception:logging.exception('Cannot publish Agent video reconciliation error')

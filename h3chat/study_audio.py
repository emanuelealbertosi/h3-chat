"""Optional two-host speech from an already grounded, user-visible script."""
from .study import loaded
from .downloads import Cancelled

def voices(app,settings):
    from .voice import configuration
    result=[]
    for gender in ('male','female'):
        cfg,_,acting,voice=configuration(app.root,settings|{'_voice_fields':{'gender':gender,'mode':'read','delivery':'warm'}},'Lettura dello script Studio')
        result.append((cfg,acting,voice))
    if result[0][2]['id']==result[1][2]['id']:raise ValueError('Configura due voci distinte nelle impostazioni Voice prima dell’audio Studio.')
    return result

def enqueue(app,chat_id,artifact_id):
    value,deck=loaded(app,chat_id,artifact_id)
    if deck['kind']!='dialogue' or deck['status']!='ready' or not deck['items']:raise ValueError('Crea e completa prima un dialogo a due voci nello Studio.')
    settings=app.effective_settings(app.store.settings())
    from .execution_mode import guard_intent
    guard_intent(settings,'voice');voices(app,settings)
    settings=settings|{'_study_audio':value['id'],'_rag':False,'_assistant':False,'_voice':True}
    job=app.store.enqueue(chat_id,'Studio · crea audio dello script approvato',[],settings,True,[]);app.wake.set()
    return {'job_id':job,'intent':'study_audio','canvas':True}

def run(app,job,payload,settings,cancel,stage,log_path):
    from .voice_controls import split_text,apply_direction
    from .study import encode
    from .store import uid
    value,deck=loaded(app,job['chat_id'],settings['_study_audio']);profiles=voices(app,settings)
    segments=[];script=[]
    for index,item in enumerate(deck['items']):
        if cancel.is_set():raise Cancelled()
        import re
        speaker=re.fullmatch(r'\s*(?:Conduttore|Host)\s+([AB])\s*:?[ \t]*',item['question'],re.I)
        voice_index=(0 if speaker[1].upper()=='A' else 1) if speaker else index%2
        cfg,acting,voice=profiles[voice_index];script.append(('A' if voice_index==0 else 'B')+': '+item['answer'])
        for chunk in split_text(item['answer'],cfg.get('chunk_chars',settings['voice_chunk_chars'])):
            segments.append({'text':chunk,'spoken':apply_direction(chunk,acting['prefix']) if cfg['engine']=='higgs' else chunk,'voice':voice,'scene_id':item['id']})
    folder=app.data/'outputs'/job['id'];folder.mkdir(parents=True,exist_ok=True);(folder/'testo-voce.txt').write_text('\n\n'.join(script),encoding='utf8')
    if settings.get('memory_policy')!='resident':app.engine.stop()
    stage('Studio · sintesi del dialogo con due voci')
    result=app.engine.tool_call('voice-worker.py',{'config':profiles[0][0],'segments':segments,'output':str(folder)},cancel,stage,log_path,timeout=14400)
    media=[{'id':uid(),'name':'dialogo-studio.wav','mime':'audio/wav','path':(folder/'voce.wav').relative_to(app.data).as_posix()}]
    artifact={'title':deck['title'],'content':encode(deck),'media':media};app.save_artifact(job['chat_id'],**artifact)
    app.store.update_answer(job,'Audio Studio pronto: script conservato e due voci alternate.','done',media,{'intent':'study_audio','artifact':artifact,'duration':result.get('duration'),'voices':[p[2]['id'] for p in profiles]})
    app.store.execute("UPDATE jobs SET status='done',stage='Audio Studio pronto' WHERE id=?",(job['id'],))

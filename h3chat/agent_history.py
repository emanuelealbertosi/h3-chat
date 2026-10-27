"""Bounded access to this run's saved observations; never another chat/run."""
import json


def search(state,query='',limit=10):
    query=query.strip().casefold();rows=[]
    for action in reversed(state.get('actions',[])):
        if action.get('status') not in ('done','failed','reused','rejected'):continue
        text=json.dumps({'arguments':action.get('arguments',{}),'result':action.get('result'),
                         'error':action.get('error','')},ensure_ascii=False)
        title=action.get('summary','')
        searchable=(action['tool']+' '+title+' '+text).casefold()
        if query and query not in searchable:continue
        where=text.casefold().find(query) if query else 0
        start=max(0,where-150)
        rows.append({'id':action['id'],'tool':action['tool'],'status':action['status'],
                     'summary':title,'excerpt':text[start:start+800],'data_only':True})
    return {'run_id':state['id'],'matches':rows[:limit],'matched':len(rows),'more':len(rows)>limit,
            'note':'Solo risultati già salvati in questo run. Leggi l’azione per recuperare i dettagli; non ripetere una scrittura già eseguita.'}


def read(state,ident,offset=0,limit=8000):
    action=next((a for a in state.get('actions',[]) if a['id']==ident),None)
    if action is None or action.get('status') not in ('done','failed','reused','rejected'):
        raise ValueError('Passaggio salvato non trovato in questa sessione Agent.')
    raw=json.dumps({'arguments':action.get('arguments',{}),'result':action.get('result'),
                    'error':action.get('error')},ensure_ascii=False)
    if offset>len(raw):raise ValueError('Posizione oltre la fine del risultato.')
    end=min(len(raw),offset+limit)
    return {'run_id':state['id'],'action_id':ident,'tool':action['tool'],'status':action['status'],
            'data':raw[offset:end],'offset':offset,'next_offset':end if end<len(raw) else None,
            'total_characters':len(raw),'data_only':True}

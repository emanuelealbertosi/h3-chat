"""Human confirmation of one concrete command, before the native UAC prompt."""
import os
from .agent_computer import grant,owner
from .agent_state import load,save,resume

def approve(app,chat_id,ident,body):
    owner(app)
    with app.lock:
        state=load(app,chat_id,ident);record=grant(app,state['config'])
        if record['scope']!='global':raise PermissionError('Amministratore richiede Globale.')
        if body.get('confirmed') is not True:raise ValueError('Conferma il comando concreto prima di chiedere i privilegi amministratore.')
        action=next((a for a in state['actions'] if a['id']==body.get('action_id')),None)
        if not action or action['tool']!='request_admin':raise ValueError('Richiesta amministratore inesistente.')
        if action.get('admin_approved'):
            return {'job_id':state['current_job_id'],'reused':True}
        if state['status']!='awaiting_admin' or action['status']!='awaiting_admin':raise ValueError('Conferma amministratore non più valida.')
        action.update(status='awaiting_approval',admin_approved=True)
        state['status']='awaiting_approval';save(app,state)
        return resume(app,chat_id,ident,{'action_id':action['id'],'decision':'approve'})

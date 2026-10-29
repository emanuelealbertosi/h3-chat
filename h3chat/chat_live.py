"""Small workspace-scoped snapshot of one normal streaming answer."""
import json,re

def read(app,chat_id,message_id):
    if not all(isinstance(v,str) and re.fullmatch('[a-f0-9]{32}',v) for v in (chat_id,message_id)):raise ValueError('Risposta chat non valida.')
    row=app.store.one("SELECT id,content,status,meta FROM messages WHERE id=? AND chat_id=? AND role='assistant'",(message_id,chat_id))
    if not row:raise ValueError('Risposta non trovata in questa chat.')
    meta=json.loads(row['meta'])
    if meta.get('intent')!='chat' or meta.get('canvas') or meta.get('agent'):raise ValueError('Questa risposta usa il percorso canvas o uno strumento.')
    return {'id':row['id'],'content':row['content'],'status':row['status']}

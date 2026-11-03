"""Read-only listing of recent study sets in the current chat's project."""
from .study import PREFIX,decode


def listing(app,chat_id):
    chat=app.store.one('SELECT id,project_id FROM chats WHERE id=?',(chat_id,))
    if not chat:raise ValueError('Chat non trovata.')
    project=chat['project_id']
    where='c.project_id=?' if project else 'c.id=?'
    seen=set();items=[]
    with app.store.connect() as db:
        rows=db.execute('SELECT a.id,a.chat_id,a.content,a.updated,c.title AS chat_title FROM canvas_artifacts a JOIN chats c ON c.id=a.chat_id WHERE '+where+' AND a.content LIKE ? ORDER BY a.updated DESC,a.created DESC,a.id DESC LIMIT 500',(project or chat_id,PREFIX+'%'))
        for row in rows:
            try:deck=decode(row['content'])
            except (ValueError,TypeError,KeyError):continue
            key=(row['chat_id'],deck['id'])
            if key in seen:continue
            seen.add(key)
            items.append({'id':row['id'],'chat_id':row['chat_id'],'chat_title':row['chat_title'],'title':deck['title'],'kind':deck['kind'],'count':len(deck['items']),'requested':deck['requested'],'status':deck['status'],'updated':row['updated']})
            if len(items)>=50:break
    return {'items':items,'scope':'project' if project else 'chat','limit':50}

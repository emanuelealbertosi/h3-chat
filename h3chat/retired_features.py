"""Upgrade saved preferences without rewriting jobs or generated media."""
import json


def migrate(db):
    removed=set()
    for row in db.execute('SELECT id,config FROM external_models').fetchall():
        if json.loads(row['config']).get('profile') in ('fibo2','fibo2-int8'):
            removed.add(row['id'])
            db.execute('DELETE FROM external_models WHERE id=?',(row['id'],))
    for row in db.execute('SELECT key,value FROM settings').fetchall():
        key=row['key'];value=json.loads(row['value']);updated=value
        if key in ('chat_model','create_model','edit_model','diagram_model','music_model','video_model') and value in removed:
            updated=''
        elif key=='image_overrides':
            updated={ident:{k:v for k,v in preset.items() if k!='fibo_offload'} for ident,preset in value.items() if ident not in removed}
        elif key=='video_overrides':
            updated={ident:{k:v for k,v in preset.items() if k!='longtake_enabled'} for ident,preset in value.items()}
        if updated!=value:
            db.execute('UPDATE settings SET value=? WHERE key=?',(json.dumps(updated),key))

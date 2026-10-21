"""Read effective seeds from completed image results, never request defaults."""

def last_seed(app,model_id):
    model=app.catalog.get(model_id)
    if not model or not any(c in model.get('capabilities',[]) for c in ('create','edit')):
        raise ValueError('Scegli un modello immagini disponibile.')
    # Older answers stored only the model name. Accept it only if unambiguous.
    name=model['name'] if sum(m.get('name')==model['name'] for m in app.catalog.values())==1 else ''
    row=app.store.one("""
        SELECT json_extract(m.meta,'$.image_parameters.seed') AS seed,
               m.id AS message_id,m.chat_id,
               coalesce(json_extract(m.meta,'$.timing.finished_at'),m.created) AS completed_at
        FROM messages m JOIN jobs j ON j.message_id=m.id
        WHERE m.role='assistant' AND m.status='done' AND j.status='done'
          AND json_type(m.meta,'$.image_parameters.seed')='integer'
          AND json_extract(m.meta,'$.image_parameters.seed') BETWEEN 0 AND 2147483647
          AND (json_extract(m.meta,'$.image_model_id')=?
               OR (json_extract(m.meta,'$.image_model_id') IS NULL AND ?<>''
                   AND json_extract(m.meta,'$.model')=?))
        ORDER BY completed_at DESC,m.seq DESC LIMIT 1
    """,(model_id,name,name))
    batch=app.store.one("""
        SELECT json_extract(asset.value,'$.generation.seed') AS seed,
               m.id AS message_id,m.chat_id,
               coalesce(json_extract(asset.value,'$.generation.completed_at'),
                        json_extract(m.meta,'$.timing.finished_at'),m.created) AS completed_at
        FROM messages m JOIN jobs j ON j.message_id=m.id, json_each(m.media) asset
        WHERE m.role='assistant' AND json_extract(m.meta,'$.image_batch')=1
          AND json_extract(asset.value,'$.generation.image_model_id')=?
          AND json_type(asset.value,'$.generation.seed')='integer'
          AND json_extract(asset.value,'$.generation.seed') BETWEEN 0 AND 2147483647
        ORDER BY completed_at DESC,m.seq DESC LIMIT 1
    """,(model_id,))
    if batch and (not row or batch['completed_at']>row['completed_at']):row=batch
    return {'model_id':model_id,**(row or {'seed':None})}

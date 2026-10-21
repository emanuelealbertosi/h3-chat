"""Explicit, idempotent recovery of one saved video request in its own workspace.

No planner or model is loaded here. Store.resume_video delegates to enqueue(),
so the normal workspace queue can register the new ticket before waking workers.
"""
import copy
import json
import re
import time
from .downloads import safe_join
from .store import uid
from .video_resume import checkpoint

TERMINAL = ('failed', 'cancelled', 'interrupted')


def _ident(value, label):
    if not isinstance(value, str) or not re.fullmatch(r'[a-f0-9]{32}', value):
        raise ValueError(label + ' non valido.')
    return value


def _load(db, chat_id, job_id=None, message_id=None):
    _ident(chat_id, 'Conversazione')
    if (job_id is None) == (message_id is None):
        raise ValueError('Scegli una sola richiesta video da riprendere.')
    key, value = ('j.id', _ident(job_id, 'Lavoro video')) if job_id is not None else ('j.message_id', _ident(message_id, 'Messaggio'))
    row = db.execute(
        'SELECT j.*,m.meta AS message_meta FROM jobs j JOIN messages m ON m.id=j.message_id '
        f"WHERE j.chat_id=? AND m.chat_id=? AND m.role='assistant' AND {key}=? ORDER BY j.created DESC,j.rowid DESC LIMIT 1",
        (chat_id, chat_id, value)).fetchone()
    if not row:
        raise ValueError('La richiesta video non appartiene a questa chat o alla tua area.')
    return dict(row)


def _summary(store, original):
    if original['status'] not in TERMINAL:
        raise ValueError('Puoi riprendere soltanto una generazione interrotta, annullata o non riuscita.')
    try:
        payload = json.loads(original['payload'])
        settings = payload['settings']
        if not isinstance(settings, dict):raise ValueError()
    except (KeyError, TypeError, ValueError):
        raise ValueError('La richiesta originale non è più disponibile.')
    # These handlers do not have a model-generation resume loop. Never silently
    # repeat their finished work under a button promising only missing clips.
    if any(settings.get(k) for k in ('_video_extend', '_video_assemble', '_video_clip', '_video_remix', '_upscale', '_video_timeline_recover')):
        raise ValueError('Questa operazione non contiene una generazione a clip riprendibile. Ricarica la richiesta per ripeterla.')
    checkpoint_id = original['id']
    # A restarted retry can fail before copying its checkpoint (for example
    # during source validation). Follow only owned, same-message recovery links;
    # a malformed existing checkpoint is never replaced by older progress.
    parent_payload = payload
    visited = set()
    while not safe_join(store.root, 'outputs/'+checkpoint_id+'/scenes.json').is_file():
        visited.add(checkpoint_id)
        ancestor = parent_payload.get('settings', {}).get('_video_resume')
        if not isinstance(ancestor, str) or not re.fullmatch(r'[a-f0-9]{32}', ancestor) or ancestor in visited or len(visited) >= 20:
            raise ValueError('Nessuna scena video salvata da recuperare.')
        row = store.one('SELECT payload FROM jobs WHERE id=? AND chat_id=? AND message_id=?', (ancestor, original['chat_id'], original['message_id']))
        if not row:raise ValueError('Il checkpoint precedente non appartiene a questa richiesta.')
        checkpoint_id = ancestor
        parent_payload = json.loads(row['payload'])
    saved = checkpoint(store.root, checkpoint_id)
    if settings.get('_video_edit'):
        command = settings['_video_edit']
        patches = saved.get('revision_request')
        if not isinstance(patches, list) or not patches or patches != command.get('patches') or saved.get('revision_source') != command.get('source'):
            raise ValueError('Le modifiche salvate non corrispondono alla richiesta originale.')
        if saved.get('revision_remount', True) != command.get('remount', True):
            raise ValueError('Il montaggio salvato non corrisponde alla richiesta originale.')
        requested = [p.get('clip') for p in patches]
        ready = saved.get('revision_completed', [])
        if (any(type(n) is not int or not 1 <= n <= len(saved['timeline']) for n in requested)
                or len(set(requested)) != len(requested) or not isinstance(ready, list)
                or any(type(n) is not int or n not in requested for n in ready)
                or len(set(ready)) != len(ready)):
            raise ValueError('L’elenco delle modifiche completate non è valido.')
        for n in ready:
            if str(n) not in saved.get('revision_generated', {}) or str(n) not in saved.get('revision_plans', {}):
                raise ValueError('Manca il file o la regia di una clip già modificata.')
        kind = 'edit'
    elif settings.get('_video_recreate'):
        command = settings['_video_recreate']
        if saved.get('recreate_source') != command.get('source') or saved.get('recreate_parameters') != command.get('parameters'):
            raise ValueError('Il video salvato non corrisponde alla ricreazione originale.')
        requested = list(range(1, len(saved['timeline']) + 1))
        ready = requested[:saved['completed']]
        kind = 'recreate'
    else:
        # A long generation saves all directions before producing its first clip.
        # Its checkpoint is sufficient even if the initial request was auto-routed.
        if any(saved.get(k) for k in ('revision_source', 'recreate_source', 'extension_source')):
            raise ValueError('Il tipo del checkpoint non corrisponde alla richiesta video.')
        requested = list(range(1, len(saved['timeline']) + 1))
        ready = requested[:saved['completed']]
        kind = 'generation'
    for item in payload.get('media', []):
        if not isinstance(item, dict) or not isinstance(item.get('path'), str) or not safe_join(store.root, item['path']).is_file():
            raise ValueError('Un allegato originale non è più disponibile. Le clip salvate sono conservate.')
    model = saved.get('model')
    if model and settings.get('video_model') != model:
        raise ValueError('Il modello del checkpoint non corrisponde alla richiesta originale.')
    missing = [n for n in requested if n not in ready]
    return {'job_id': original['id'], 'checkpoint_job_id': checkpoint_id, 'message_id': original['message_id'], 'status': original['status'],
            'kind': kind, 'total': len(requested), 'completed': len(ready), 'remaining': len(missing),
            'ready_clips': sorted(ready), 'missing_clips': missing, 'assembly_only': not missing,
            'timeline_clips': len(saved['timeline']), 'timeline_available':kind=='edit' and bool(saved.get('working_timeline')),
            'canvas': bool(payload.get('canvas'))}, payload


def describe(app, chat_id, *, job_id=None, message_id=None):
    app.store.chat(chat_id)
    with app.store.connect() as db:
        original = _load(db, chat_id, job_id, message_id)
    result, _ = _summary(app.store, original)
    return result


def enqueue(store, chat_id, job_id):
    """Called by Store.resume_video; one transaction protects double clicks."""
    with store.connect() as db:
        db.execute('BEGIN IMMEDIATE')
        original = _load(db, chat_id, job_id)
        # Repeated submissions of this exact interrupted job return its existing
        # recovery, even if that recovery was subsequently cancelled or failed.
        # Another attempt must explicitly choose that newer interrupted request.
        existing = db.execute(
            "SELECT id FROM jobs WHERE chat_id=? AND json_extract(payload,'$.settings._video_resume_origin')=? ORDER BY created DESC,rowid DESC LIMIT 1",
            (chat_id, job_id)).fetchone()
        if existing:return existing['id']
        chat = db.execute('SELECT archived FROM chats WHERE id=?', (chat_id,)).fetchone()
        if not chat or chat['archived']:
            raise ValueError('Ripristina la chat dall’archivio per riprendere il video.')
        if db.execute("SELECT 1 FROM jobs WHERE status IN ('queued','running')").fetchone():
            raise ValueError('Attendi o interrompi la tua richiesta attiva o in coda prima di riprendere il video.')
        summary, payload = _summary(store, original)
        payload = copy.deepcopy(payload)
        payload['settings']['_video_resume'] = summary['checkpoint_job_id']
        payload['settings']['_video_resume_origin'] = job_id
        original_meta = json.loads(original['message_meta'])
        if original_meta.get('references'):
            payload['video_resume_context'] = {'references':original_meta['references']}
        # Keep the original model, LoRAs, references, plans, seeds and all per-run
        # settings. Current preferences must not change an interrupted film.
        ident, now = uid(), time.time()
        meta = {'intent': 'video', 'video_recovery': summary | {'source': job_id}}
        db.execute("UPDATE messages SET content='',media='[]',meta=?,status='queued',created=? WHERE id=?",
                   (json.dumps(meta), now, original['message_id']))
        db.execute("INSERT INTO jobs VALUES (?,?,?,?,'queued','Ripresa dalle clip mancanti','',?)",
                   (ident, chat_id, original['message_id'], json.dumps(payload), now))
        db.execute('UPDATE chats SET updated=? WHERE id=?', (now, chat_id))
    return ident


def request(app, chat_id, body):
    if not isinstance(body, dict) or set(body) != {'job_id'}:
        raise ValueError('Indica soltanto il lavoro video preciso da riprendere.')
    with app.lock:
        job_id = _ident(body['job_id'], 'Lavoro video')
        # Avoid adding a second shared-queue ticket for a retried HTTP response.
        # The transaction in enqueue repeats this check for separate callers.
        with app.store.connect() as db:
            _load(db, chat_id, job_id)
            existing = db.execute("SELECT id FROM jobs WHERE chat_id=? AND json_extract(payload,'$.settings._video_resume_origin')=? ORDER BY created DESC,rowid DESC LIMIT 1", (chat_id, job_id)).fetchone()
        ident = existing['id'] if existing else app.store.resume_video(chat_id, job_id)
        row = app.store.one('SELECT status FROM jobs WHERE id=?', (ident,))
        if row['status'] == 'queued':app.wake.set()
    return {'job_id': ident, 'status': row['status'], 'intent': 'video'}

"""Persist request timings without confusing queue time with model work."""
import json
import time


def start(store, job):
    clock = {'queued_at': job['created'], 'started_at': time.time(),
             'monotonic': time.monotonic(), 'job_id': job['id']}
    value = {k:v for k,v in clock.items() if k != 'monotonic'}
    store.execute("UPDATE messages SET meta=json_set(meta,'$.timing',json(?)) WHERE id=?",
                  (json.dumps(value), job['message_id']))
    return clock


def finish(store, job, clock=None):
    now = time.time()
    elapsed = max(0, time.monotonic() - clock['monotonic']) if clock else 0
    waiting = max(0, (clock['started_at'] if clock else now) - job['created'])
    value = {'job_id': job['id'], 'queued_at': job['created'],
             'started_at': clock['started_at'] if clock else None,
             'finished_at': now, 'elapsed_seconds': elapsed,
             'queue_seconds': waiting, 'total_seconds': waiting + elapsed}
    with store.connect() as db:
        db.execute('BEGIN IMMEDIATE')
        latest = db.execute('SELECT id FROM jobs WHERE message_id=? ORDER BY created DESC,rowid DESC LIMIT 1',
                            (job['message_id'],)).fetchone()
        if not latest or latest['id'] != job['id']:
            return  # Regenerate may already have replaced this answer.
        row = db.execute('SELECT meta FROM messages WHERE id=?', (job['message_id'],)).fetchone()
        if not row:
            return
        previous = json.loads(row['meta']).get('timing', {})
        if previous.get('job_id') == job['id'] and previous.get('finished_at') is not None:
            return  # A second cancellation/finalizer must not extend the time.
        db.execute("UPDATE messages SET meta=json_set(meta,'$.timing',json(?)) WHERE id=?",
                   (json.dumps(value), job['message_id']))

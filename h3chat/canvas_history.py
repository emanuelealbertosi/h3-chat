"""Chat-scoped artifacts; streaming updates one entry, browsing never replaces it."""
import json
import time
import uuid


class CanvasHistory:
    def __init__(self, store):
        self.store = store
        with store.connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS canvas_artifacts (
                    id TEXT PRIMARY KEY, chat_id TEXT NOT NULL REFERENCES chats(id) ON DELETE CASCADE,
                    source_key TEXT NOT NULL, message_id TEXT, title TEXT NOT NULL, content TEXT NOT NULL,
                    media TEXT NOT NULL, created REAL NOT NULL, updated REAL NOT NULL,
                    UNIQUE(chat_id,source_key));
                CREATE INDEX IF NOT EXISTS canvas_artifacts_chat ON canvas_artifacts(chat_id,created);
                CREATE INDEX IF NOT EXISTS canvas_artifacts_message ON canvas_artifacts(chat_id,message_id);
                CREATE TABLE IF NOT EXISTS canvas_heads (
                    chat_id TEXT PRIMARY KEY REFERENCES chats(id) ON DELETE CASCADE,
                    artifact_id TEXT REFERENCES canvas_artifacts(id) ON DELETE SET NULL);
            """)

    @staticmethod
    def value(row):
        return dict(row) | {'media': json.loads(row['media'])}

    @staticmethod
    def insert(db, chat_id, value, key, message_id=None, created=None):
        now = time.time()
        ident = uuid.uuid4().hex
        db.execute("""INSERT INTO canvas_artifacts VALUES (?,?,?,?,?,?,?,?,?)
            ON CONFLICT(chat_id,source_key) DO UPDATE SET
                title=excluded.title,content=excluded.content,media=excluded.media,updated=excluded.updated""",
            (ident, chat_id, key, message_id, value.get('title', 'Canvas')[:150],
             value.get('content', ''), json.dumps(value.get('media', [])), created or now, now))
        return db.execute('SELECT * FROM canvas_artifacts WHERE chat_id=? AND source_key=?', (chat_id, key)).fetchone()

    def backfill(self, db, chat_id, skip_message=None):
        """Import saved message artifacts and the pre-history canvas without altering them."""
        if not db.execute('SELECT 1 FROM chats WHERE id=?', (chat_id,)).fetchone():
            raise ValueError('Conversazione non trovata.')
        rows = db.execute("""SELECT m.* FROM messages m WHERE chat_id=? AND role='assistant'
            AND (json_extract(meta,'$.artifact') IS NOT NULL OR media!='[]')
            AND status NOT IN ('queued','running') AND NOT EXISTS
            (SELECT 1 FROM canvas_artifacts a WHERE a.chat_id=m.chat_id AND a.message_id=m.id)
            ORDER BY seq""", (chat_id,)).fetchall()
        for row in rows:
            if row['id'] == skip_message:
                continue
            meta = json.loads(row['meta'])
            value = meta.get('artifact') or self.message_value(row['content'], json.loads(row['media']), meta)
            if value:
                self.insert(db, chat_id, value, 'message:' + row['id'], row['id'], row['created'])
        current = db.execute('SELECT * FROM canvases WHERE chat_id=?', (chat_id,)).fetchone()
        if current and (current['content'] or current['media'] != '[]'):
            head = db.execute('SELECT artifact_id FROM canvas_heads WHERE chat_id=?', (chat_id,)).fetchone()
            if not head or not head['artifact_id']:
                match = db.execute('''SELECT * FROM canvas_artifacts WHERE chat_id=? AND title=? AND content=?
                    AND media=? ORDER BY created DESC LIMIT 1''',
                    (chat_id, current['title'], current['content'], current['media'])).fetchone()
                match = match or self.insert(db, chat_id, self.value(current), 'legacy-canvas', created=current['updated'])
                db.execute('INSERT OR REPLACE INTO canvas_heads VALUES (?,?)', (chat_id, match['id']))

    @staticmethod
    def message_value(content, media, meta):
        if not media:
            return None
        music = meta.get('music_composition')
        if music:
            title = music.get('title', 'Musica')
            return {'title': title, 'content': '## ' + title + '\n\n' + music.get('lyrics', '').replace('\n', '  \n'), 'media': media}
        title = {'create': 'Immagine', 'edit': 'Immagine modificata', 'video': 'Video',
                 'manim': 'Animazione Manim', 'transcribe': 'Trascrizione'}.get(meta.get('intent'), media[0].get('name', 'Artefatto'))
        return {'title': title, 'content': content, 'media': media}

    def listing(self, chat_id):
        with self.store.connect() as db:
            self.backfill(db, chat_id)
            head = db.execute('SELECT artifact_id FROM canvas_heads WHERE chat_id=?', (chat_id,)).fetchone()
            items = db.execute('''SELECT id,title,created,updated,message_id,source_key FROM canvas_artifacts
                WHERE chat_id=? ORDER BY created,id''', (chat_id,)).fetchall()
            return {'active_id': head['artifact_id'] if head else None, 'items': [dict(row) for row in items]}

    def get(self, chat_id, ident=None):
        with self.store.connect() as db:
            self.backfill(db, chat_id)
            if ident:
                row = db.execute('SELECT * FROM canvas_artifacts WHERE chat_id=? AND id=?', (chat_id, ident)).fetchone()
                if not row:
                    raise ValueError('Artefatto non trovato in questa chat.')
                return self.value(row)
            row = db.execute('SELECT * FROM canvases WHERE chat_id=?', (chat_id,)).fetchone()
            head = db.execute('SELECT artifact_id FROM canvas_heads WHERE chat_id=?', (chat_id,)).fetchone()
            return (self.value(row) if row else {'title': 'Canvas', 'content': '', 'media': []}) | {'id': head['artifact_id'] if head else None}

    def save(self, chat_id, value, *, key=None, message_id=None, edit_id=None, activate=True, editable=False):
        with self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            if editable:
                self.ensure_idle(db, chat_id)
            self.backfill(db, chat_id, message_id)
            if key is None:
                previous = db.execute('SELECT * FROM canvas_artifacts WHERE chat_id=? AND id=?', (chat_id, edit_id)).fetchone()
                if edit_id and not previous:
                    raise ValueError('Artefatto non trovato in questa chat.')
                # Edits make a working copy of generated/legacy artifacts. Later
                # keystrokes update that copy, preserving the original output.
                key = previous['source_key'] if previous and previous['source_key'].startswith('manual:') else 'manual:' + uuid.uuid4().hex
                if previous and all(self.value(previous)[k] == value.get(k, [] if k == 'media' else '') for k in ('title', 'content', 'media')):
                    entry = previous
                else:
                    entry = self.insert(db, chat_id, value, key, previous['message_id'] if previous else None)
            else:
                entry = self.insert(db, chat_id, value, key, message_id)
            if activate:
                self.activate(db, chat_id, entry)
            return self.value(entry)

    @staticmethod
    def activate(db, chat_id, entry):
        db.execute('INSERT OR REPLACE INTO canvases VALUES (?,?,?,?,?)',
                   (chat_id, entry['title'], entry['content'], entry['media'], time.time()))
        db.execute('INSERT OR REPLACE INTO canvas_heads VALUES (?,?)', (chat_id, entry['id']))

    @staticmethod
    def ensure_idle(db, chat_id):
        if db.execute("SELECT 1 FROM jobs WHERE chat_id=? AND status IN ('queued','running') AND json_extract(payload,'$.canvas')=1", (chat_id,)).fetchone():
            raise ValueError('Il motore sta scrivendo nel canvas. Attendi o interrompilo prima di modificare.')

    def restore(self, chat_id, ident):
        with self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            self.ensure_idle(db, chat_id)
            self.backfill(db, chat_id)
            entry = db.execute('SELECT * FROM canvas_artifacts WHERE chat_id=? AND id=?', (chat_id, ident)).fetchone()
            if not entry:
                raise ValueError('Artefatto non trovato in questa chat.')
            self.activate(db, chat_id, entry)
            return self.value(entry)

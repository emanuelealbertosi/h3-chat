from __future__ import annotations

import json
import sqlite3
import time
import uuid
from contextlib import contextmanager
from pathlib import Path
from .llm_options import KEYS as LLM_KEYS, merge as merge_llm_settings
from .voice import DEFAULTS as VOICE_DEFAULTS

PROFILES = {
    "cpu": {"context": 4096, "gpu_layers": 0, "width": 512, "height": 512},
    "low": {"context": 4096, "gpu_layers": 20, "width": 512, "height": 512},
    "balanced": {"context": 8192, "gpu_layers": 99, "width": 768, "height": 768},
}
DEFAULTS = {
    "llm_timeout": 1800,
    "lab_auto": True, "manim_device": "cpu", "manim_duration": 8, "manim_fps": 15, "manim_width": 854, "manim_height": 480, "manim_timeout": 600, "manim_memory_gb": 4,
    "llm_device": "inherit", "image_device": "inherit", "rag_device": "cpu", "asr_device": "cpu",
    "rag_enabled": True, "rag_embedding_model": "", "rag_embedding_profile": "embeddinggemma", "rag_top_k": 6,
    "web_auto": True, "web_provider": "duckduckgo", "web_searxng_url": "", "web_max_results": 3,
    "transcribe_auto": True, "asr_model": "whisper-small", "asr_language": "auto", "asr_threads": 4, "asr_beam": 3,
    "video_model": "", "video_auto": True, "video_advanced": False, "video_overrides": {}, "video_prompt_max_tokens": 3000,
    "llm_overrides": {},
    "profile": "low", "backend": "vulkan", "chat_model": "", "create_model": "",
    "music_model": "yue2-q8", "music_auto": True, "music_backend": "cuda", "music_threads": 8,
    "music_advanced": False, "music_overrides": {}, "music_prompt_max_tokens": 2200,
    "edit_model": "", "diagram_model": "", "diagram_auto": True, "vision_enabled": True, "prompt_max_tokens": 2200, "context": 4096, "gpu_layers": 20, "max_tokens": 1024,
    "image_advanced": False, "chat_advanced": False, "image_overrides": {}, "image_cfg": 7,
    "lora_dirs": [], "image_sampler": "auto", "image_scheduler": "auto", "seed": -1, "negative_prompt": "",
    "temperature": 0.7, "width": 512, "height": 512, "steps": 20,
    "strength": 0.65, "threads": 4, "system_prompt": "Rispondi in italiano, in modo chiaro e utile.",
    "setup_done": False, "think_level": "off", "mtp_enabled": False, "mtp_draft_tokens": 3, "memory_policy": "on_demand", "ram_cache_gb": 2,
}


DEFAULTS.update(VOICE_DEFAULTS)

def uid():
    return uuid.uuid4().hex


class Store:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.path = self.root / "chat.sqlite"
        with self.connect() as db:
            db.executescript("""
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS external_models (id TEXT PRIMARY KEY, config TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS api_providers (id TEXT PRIMARY KEY, config TEXT NOT NULL, secret TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS media_providers (id TEXT PRIMARY KEY, config TEXT NOT NULL, secret TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS collections (id TEXT PRIMARY KEY, name TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS chats (
                    id TEXT PRIMARY KEY, title TEXT NOT NULL, collection_id TEXT REFERENCES collections(id) ON DELETE SET NULL,
                    pinned INTEGER NOT NULL DEFAULT 0, archived INTEGER NOT NULL DEFAULT 0,
                    created REAL NOT NULL, updated REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS messages (
                    seq INTEGER PRIMARY KEY AUTOINCREMENT, id TEXT UNIQUE NOT NULL,
                    chat_id TEXT NOT NULL REFERENCES chats(id) ON DELETE CASCADE,
                    role TEXT NOT NULL, content TEXT NOT NULL DEFAULT '', media TEXT NOT NULL DEFAULT '[]',
                    status TEXT NOT NULL DEFAULT 'done', created REAL NOT NULL, meta TEXT NOT NULL DEFAULT '{}');
                CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY, chat_id TEXT REFERENCES chats(id) ON DELETE CASCADE,
                    message_id TEXT NOT NULL, payload TEXT NOT NULL, status TEXT NOT NULL,
                    stage TEXT NOT NULL DEFAULT '', error TEXT NOT NULL DEFAULT '', created REAL NOT NULL);
                CREATE INDEX IF NOT EXISTS messages_chat ON messages(chat_id,seq);
                CREATE INDEX IF NOT EXISTS jobs_state ON jobs(status,created);
                CREATE TABLE IF NOT EXISTS canvases (
                    chat_id TEXT PRIMARY KEY REFERENCES chats(id) ON DELETE CASCADE,
                    title TEXT NOT NULL DEFAULT 'Canvas', content TEXT NOT NULL DEFAULT '',
                    media TEXT NOT NULL DEFAULT '[]', updated REAL NOT NULL);
            """)
            db.executescript("""
                CREATE TABLE IF NOT EXISTS projects (id TEXT PRIMARY KEY, name TEXT NOT NULL, instructions TEXT NOT NULL DEFAULT '', sources_only INTEGER NOT NULL DEFAULT 0, created REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS project_roots (id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE, path TEXT NOT NULL, UNIQUE(project_id,path));
                CREATE TABLE IF NOT EXISTS project_exclusions (project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE, path TEXT NOT NULL, PRIMARY KEY(project_id,path));
                CREATE TABLE IF NOT EXISTS project_sources (id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE, path TEXT NOT NULL, name TEXT NOT NULL, fingerprint TEXT NOT NULL DEFAULT '', status TEXT NOT NULL DEFAULT 'pending', error TEXT NOT NULL DEFAULT '', updated REAL NOT NULL DEFAULT 0, UNIQUE(project_id,path));
                CREATE TABLE IF NOT EXISTS rag_chunks (id INTEGER PRIMARY KEY AUTOINCREMENT, source_id TEXT NOT NULL REFERENCES project_sources(id) ON DELETE CASCADE, location TEXT NOT NULL, page INTEGER, text TEXT NOT NULL, embedding TEXT, embedding_key TEXT NOT NULL DEFAULT '');
                CREATE INDEX IF NOT EXISTS rag_source ON rag_chunks(source_id);
                CREATE VIRTUAL TABLE IF NOT EXISTS rag_fts USING fts5(text, content='rag_chunks', content_rowid='id', tokenize='unicode61 remove_diacritics 2');
                CREATE TRIGGER IF NOT EXISTS rag_insert AFTER INSERT ON rag_chunks BEGIN INSERT INTO rag_fts(rowid,text) VALUES(new.id,new.text); END;
                CREATE TRIGGER IF NOT EXISTS rag_delete AFTER DELETE ON rag_chunks BEGIN INSERT INTO rag_fts(rag_fts,rowid,text) VALUES('delete',old.id,old.text); END;
                CREATE TRIGGER IF NOT EXISTS rag_update AFTER UPDATE OF text ON rag_chunks BEGIN INSERT INTO rag_fts(rag_fts,rowid,text) VALUES('delete',old.id,old.text); INSERT INTO rag_fts(rowid,text) VALUES(new.id,new.text); END;
            """)
            if 'project_id' not in {row['name'] for row in db.execute('PRAGMA table_info(chats)')}:
                db.execute('ALTER TABLE chats ADD COLUMN project_id TEXT REFERENCES projects(id) ON DELETE SET NULL')
            if 'source_url' not in {row['name'] for row in db.execute('PRAGMA table_info(project_sources)')}:
                db.execute("ALTER TABLE project_sources ADD COLUMN source_url TEXT NOT NULL DEFAULT ''")
            db.execute("UPDATE project_sources SET status='pending' WHERE status='indexing'")
            # One-time migration preserves the user's existing active model settings.
            if not db.execute("SELECT 1 FROM settings WHERE key='llm_overrides'").fetchone():
                existing=DEFAULTS|{r['key']:json.loads(r['value']) for r in db.execute('SELECT * FROM settings')}
                presets={existing['chat_model']:{k:existing[k] for k in LLM_KEYS}} if existing['chat_model'] else {}
                db.execute("INSERT INTO settings VALUES ('llm_overrides',?)",(json.dumps(presets),))
            db.execute("UPDATE messages SET status='interrupted' WHERE status IN ('queued','running')")
            db.execute("UPDATE jobs SET status='interrupted',error='Applicazione riavviata. Puoi riprovare.' WHERE status IN ('queued','running')")
        from .canvas_history import CanvasHistory
        self.canvas_history = CanvasHistory(self)

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=15)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        try:
            with db:
                yield db
        finally:
            db.close()

    def all(self, sql, args=()):
        with self.connect() as db:
            return [dict(row) for row in db.execute(sql, args)]

    def one(self, sql, args=()):
        rows = self.all(sql, args)
        return rows[0] if rows else None

    def execute(self, sql, args=()):
        with self.connect() as db:
            return db.execute(sql, args).rowcount

    def settings(self):
        return DEFAULTS | {r["key"]: json.loads(r["value"]) for r in self.all("SELECT * FROM settings")}

    def save_settings(self, patch):
        patch=merge_llm_settings(self.settings(),patch)
        with self.connect() as db:
            for key, value in patch.items():
                db.execute("INSERT OR REPLACE INTO settings VALUES (?,?)", (key, json.dumps(value)))

    def chat(self, chat_id):
        chat = self.one("SELECT * FROM chats WHERE id=?", (chat_id,))
        if not chat:
            raise ValueError("Conversazione non trovata.")
        chat["messages"] = self.messages(chat_id)
        return chat

    def messages(self, chat_id, until=None):
        rows = self.all("SELECT * FROM messages WHERE chat_id=? AND seq<=? ORDER BY seq", (chat_id, until or 2**62))
        for row in rows:
            row["media"] = json.loads(row["media"])
            row["meta"] = json.loads(row["meta"])
        return rows

    def create_chat(self, title="Nuova chat", collection_id=None, project_id=None):
        chat_id, now = uid(), time.time()
        self.execute("INSERT INTO chats(id,title,collection_id,pinned,archived,created,updated,project_id) VALUES (?,?,?,0,0,?,?,?)", (chat_id, title, collection_id, now, now, project_id))
        return self.chat(chat_id)

    def enqueue(self, chat_id, prompt, media, settings, canvas=False, loras=None):
        job_id, user_id, answer_id, now = uid(), uid(), uid(), time.time()
        loras=loras or []
        lora_meta={"voice":settings.get("_voice",False),"voice_fields":settings.get("_voice_fields",{}),"web":settings.get("_web",False),"transcribe":settings.get("_transcribe",False),"video":settings.get("_video",False),"music":settings.get("_music",False),"music_fields":settings.get("_music_fields",{}),"image_model":settings.get("_image_model",""),"assistant":settings.get("_assistant",True),"loras":[{k:l[k] for k in ("id","name","weight","model_id","model_name")} for l in loras]}
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            chat = db.execute("SELECT * FROM chats WHERE id=?", (chat_id,)).fetchone()
            if not chat:
                raise ValueError("Conversazione non trovata.")
            if chat["archived"]:
                raise ValueError("Ripristina la chat dall’archivio per continuare.")
            if db.execute("SELECT 1 FROM jobs WHERE chat_id=? AND status IN ('queued','running')", (chat_id,)).fetchone():
                raise ValueError("Attendi la risposta oppure interrompila.")
            cur = db.execute("INSERT INTO messages(id,chat_id,role,content,media,created,meta) VALUES (?,?,'user',?,?,?,?)",
                             (user_id, chat_id, prompt, json.dumps(media), now, json.dumps(lora_meta)))
            snapshot = db.execute("SELECT * FROM canvases WHERE chat_id=?", (chat_id,)).fetchone()
            payload = {"prompt": prompt, "media": media, "settings": settings, "loras": loras, "until": cur.lastrowid, "canvas": canvas,
                       "project_id": chat['project_id'],
                       "canvas_snapshot": dict(snapshot) if canvas and snapshot else None}
            db.execute("INSERT INTO messages(id,chat_id,role,status,created) VALUES (?,?,'assistant','queued',?)", (answer_id, chat_id, now))
            db.execute("INSERT INTO jobs VALUES (?,?,?,?, 'queued','In attesa','',?)", (job_id, chat_id, answer_id, json.dumps(payload), now))
            title = prompt[:65].strip() or "Conversazione con immagine"
            db.execute("UPDATE chats SET title=CASE WHEN title='Nuova chat' THEN ? ELSE title END,updated=? WHERE id=?", (title, now, chat_id))
        return job_id

    def regenerate(self, chat_id, llm_settings=None):
        """Replay the last saved request, replacing its answer atomically."""
        job_id, now = uid(), time.time()
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            chat = db.execute("SELECT * FROM chats WHERE id=?", (chat_id,)).fetchone()
            if not chat:
                raise ValueError("Conversazione non trovata.")
            if chat['archived']:
                raise ValueError("Ripristina la chat dall’archivio per continuare.")
            if db.execute("SELECT 1 FROM jobs WHERE chat_id=? AND status IN ('queued','running')", (chat_id,)).fetchone():
                raise ValueError("Attendi la risposta oppure interrompila.")
            user = db.execute("SELECT seq FROM messages WHERE chat_id=? AND role='user' ORDER BY seq DESC LIMIT 1", (chat_id,)).fetchone()
            original = db.execute("SELECT * FROM jobs WHERE chat_id=? AND json_extract(payload,'$.until')=? ORDER BY created DESC LIMIT 1", (chat_id, user['seq'] if user else -1)).fetchone()
            if not original:
                raise ValueError("Invia prima un messaggio da rigenerare.")
            # Keep attachments, controls, per-model settings and the original
            # history/canvas snapshot. A retry must not consume its own answer.
            payload = original['payload']
            value=json.loads(payload)
            value['settings'].pop('_video_resume',None)
            value['settings'].pop('_manim_voice_resume',None)
            if original['status'] in ('failed','cancelled'):
                try:
                    from .video_resume import checkpoint
                    saved=checkpoint(self.root,original['id'])
                except (OSError,ValueError,TypeError,KeyError):saved=None
                if saved:
                    value['settings']['_video_resume']=original['id']
                if value['settings'].get('_manim_voice'):
                    try:
                        from .narrated_manim import checkpoint as narration_checkpoint
                        narration_checkpoint(self.root,original['id'])
                    except (OSError,ValueError,TypeError,KeyError):pass
                    else:value['settings']['_manim_voice_resume']=original['id']
            if llm_settings is not None:
                from .llm_options import KEYS
                value['settings'].update({key:llm_settings[key] for key in ('chat_model','llm_device','vision_enabled',*KEYS)})
            payload=json.dumps(value)
            answer_id = original['message_id']
            self.canvas_history.backfill(db, chat_id)
            db.execute("UPDATE messages SET content='',media='[]',meta='{}',status='queued',created=? WHERE id=?", (now, answer_id))
            db.execute("INSERT INTO jobs VALUES (?,?,?,?, 'queued','In attesa','',?)", (job_id, chat_id, answer_id, payload, now))
            db.execute("UPDATE chats SET updated=? WHERE id=?", (now, chat_id))
        return job_id

    def update_answer(self, job, content, status="running", media=None, meta=None):
        if status not in ('queued', 'running'):
            value = (meta or {}).get('artifact') or self.canvas_history.message_value(content, media or [], meta or {})
            if value:
                self.canvas_history.save(job['chat_id'], value, key='job:' + job['id'],
                                         message_id=job['message_id'], activate=bool((meta or {}).get('canvas')))
        # Register before publishing the terminal answer, so concurrent history
        # polling cannot import the same output as an additional legacy entry.
        self.execute("UPDATE messages SET content=?,status=?,media=?,meta=? WHERE id=?",
                     (content, status, json.dumps(media or []), json.dumps(meta or {}), job["message_id"]))

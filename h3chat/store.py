from __future__ import annotations

import json
import sqlite3
import time
import uuid
from contextlib import contextmanager
from pathlib import Path
from .llm_options import KEYS as LLM_KEYS, merge as merge_llm_settings

PROFILES = {
    "cpu": {"context": 4096, "gpu_layers": 0, "width": 512, "height": 512},
    "low": {"context": 4096, "gpu_layers": 20, "width": 512, "height": 512},
    "balanced": {"context": 8192, "gpu_layers": 99, "width": 768, "height": 768},
}
DEFAULTS = {
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
            # One-time migration preserves the user's existing active model settings.
            if not db.execute("SELECT 1 FROM settings WHERE key='llm_overrides'").fetchone():
                existing=DEFAULTS|{r['key']:json.loads(r['value']) for r in db.execute('SELECT * FROM settings')}
                presets={existing['chat_model']:{k:existing[k] for k in LLM_KEYS}} if existing['chat_model'] else {}
                db.execute("INSERT INTO settings VALUES ('llm_overrides',?)",(json.dumps(presets),))
            db.execute("UPDATE messages SET status='interrupted' WHERE status IN ('queued','running')")
            db.execute("UPDATE jobs SET status='interrupted',error='Applicazione riavviata. Puoi riprovare.' WHERE status IN ('queued','running')")

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

    def create_chat(self, title="Nuova chat", collection_id=None):
        chat_id, now = uid(), time.time()
        self.execute("INSERT INTO chats VALUES (?,?,?,0,0,?,?)", (chat_id, title, collection_id, now, now))
        return self.chat(chat_id)

    def enqueue(self, chat_id, prompt, media, settings, canvas=False, loras=None):
        job_id, user_id, answer_id, now = uid(), uid(), uid(), time.time()
        loras=loras or []
        lora_meta={"music":settings.get("_music",False),"music_fields":settings.get("_music_fields",{}),"image_model":settings.get("_image_model",""),"assistant":settings.get("_assistant",True),"loras":[{k:l[k] for k in ("id","name","weight","model_id","model_name")} for l in loras]}
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
                       "canvas_snapshot": dict(snapshot) if canvas and snapshot else None}
            db.execute("INSERT INTO messages(id,chat_id,role,status,created) VALUES (?,?,'assistant','queued',?)", (answer_id, chat_id, now))
            db.execute("INSERT INTO jobs VALUES (?,?,?,?, 'queued','In attesa','',?)", (job_id, chat_id, answer_id, json.dumps(payload), now))
            title = prompt[:65].strip() or "Conversazione con immagine"
            db.execute("UPDATE chats SET title=CASE WHEN title='Nuova chat' THEN ? ELSE title END,updated=? WHERE id=?", (title, now, chat_id))
        return job_id

    def update_answer(self, job, content, status="running", media=None, meta=None):
        self.execute("UPDATE messages SET content=?,status=?,media=?,meta=? WHERE id=?",
                     (content, status, json.dumps(media or []), json.dumps(meta or {}), job["message_id"]))

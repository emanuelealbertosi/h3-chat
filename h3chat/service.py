from __future__ import annotations
import base64
import json
import os
import re
import secrets
import subprocess
import threading
import time
from pathlib import Path
from .downloads import Cancelled, Downloads, model_ready, safe_join
from .engine import CREATE_NO_WINDOW, Engine, runtime_executable
from .store import DEFAULTS, PROFILES, Store, uid
from .models import discover_local, inspect_model, THINK_LEVELS, thinking_parameters
from .hardware import detect_hardware, assess_model


class Service:
    def __init__(self, root, data=None, start_worker=True):
        self.root = Path(root).resolve()
        self.data = Path(data or self.root / "data").resolve()
        self.store = Store(self.data)
        self.catalog = {m["id"]: m for m in json.loads((self.root / "catalog.json").read_text(encoding="utf-8"))}
        self.runtimes = json.loads((self.root / "runtimes.json").read_text(encoding="utf-8"))
        self.downloads = Downloads(self.root, self.catalog, self.runtimes)
        self.engine = Engine(self.root, self.data, self.catalog)
        self.token = secrets.token_hex(32)
        self.wake, self.closed = threading.Event(), threading.Event()
        self.lock = threading.RLock()
        self.current_id, self.cancel_event = None, None
        self.worker = threading.Thread(target=self.run, daemon=True)
        if start_worker:
            self.worker.start()

    def refresh_models(self):
        with self.lock:
            for key in list(self.catalog):
                if self.catalog[key].get("local"):
                    del self.catalog[key]
            self.catalog.update({m["id"]:m for m in discover_local(self.root)})
            return [m | inspect_model(self.root, m) for m in list(self.catalog.values())]

    def state(self):
        models = self.refresh_models()
        return {"token": self.token, "version": "0.2.0", "settings": self.store.settings(), "profiles": PROFILES,
                "models": models,
                "runtimes": {key: {"ready": all(runtime_executable(self.root, key, e) for e in ("llama", "sd")),
                                    "size": sum(f["size"] for f in r["files"])} for key, r in self.runtimes.items()},
                "chats": self.store.all("SELECT * FROM chats ORDER BY pinned DESC,updated DESC"),
                "collections": self.store.all("SELECT * FROM collections ORDER BY name"),
                "jobs": self.store.all("SELECT id,chat_id,status,stage,error,created,json_extract(payload,'$.canvas') AS canvas FROM jobs ORDER BY created DESC LIMIT 100"),
                "downloads": self.downloads.snapshot()}

    def validate_settings(self, patch):
        self.refresh_models()
        if not isinstance(patch, dict) or set(patch) - set(DEFAULTS):
            raise ValueError("Impostazione sconosciuta.")
        s = self.store.settings() | patch
        if s["profile"] not in PROFILES or s["backend"] not in self.runtimes:
            raise ValueError("Profilo hardware non valido.")
        for key, lo, hi in (("context", 1024, 32768), ("gpu_layers", 0, 999), ("max_tokens", 64, 8192),
                            ("width", 256, 1536), ("height", 256, 1536), ("steps", 1, 100), ("threads", 1, 64)):
            if type(s[key]) is not int or not lo <= s[key] <= hi:
                raise ValueError(f"{key}: inserisci un intero tra {lo} e {hi}.")
        if s["max_tokens"] > s["context"] // 2:
            raise ValueError("I token di risposta non possono superare metà del contesto.")
        if s["width"] % 64 or s["height"] % 64:
            raise ValueError("Le dimensioni devono essere multipli di 64.")
        for key, lo, hi in (("temperature", 0, 2), ("strength", 0.05, 1)):
            if type(s[key]) not in (int, float) or not lo <= s[key] <= hi:
                raise ValueError(f"{key} fuori intervallo.")
        if not isinstance(s["system_prompt"], str) or len(s["system_prompt"]) > 8000:
            raise ValueError("Istruzioni di sistema troppo lunghe.")
        if type(s["setup_done"]) is not bool:
            raise ValueError("setup_done non valido.")
        for key, capability in (("chat_model", "chat"), ("create_model", "create"), ("edit_model", "edit")):
            if s[key] and (s[key] not in self.catalog or capability not in self.catalog[s[key]]["capabilities"]):
                raise ValueError(f"Modello incompatibile con {capability}.")
        if s.get("think_level") not in THINK_LEVELS:
            raise ValueError("Thinking: scegli off, low, med, high o xhigh.")
        return s

    def save_settings(self, patch):
        settings = self.validate_settings(patch)
        self.store.save_settings(settings)
        return settings

    def assess(self, body):
        settings = self.validate_settings(body.get("settings", {}))
        refs = body.get("references", 1)
        if type(refs) is not int or not 0 <= refs <= 4:
            raise ValueError("Numero di riferimenti non valido.")
        hardware = self.hardware()
        models = self.refresh_models()
        selected = []
        for key in ("chat_model", "create_model", "edit_model"):
            model = next((m for m in models if m["id"] == settings[key]), None)
            if model:
                selected.append(assess_model(model, settings, hardware, refs) | {"role":key})
        return {"hardware":hardware,"models":selected,"references":refs}

    def upload(self, body):
        try:
            raw = base64.b64decode(body["data"], validate=True)
        except Exception as exc:
            raise ValueError("Allegato non valido.") from exc
        if len(raw) > 12 * 1024 * 1024:
            raise ValueError("Ogni immagine può occupare al massimo 12 MB.")
        if raw.startswith(b"\x89PNG\r\n\x1a\n"):
            ext, mime = "png", "image/png"
            if len(raw) < 24 or max(int.from_bytes(raw[16:20], "big"), int.from_bytes(raw[20:24], "big")) > 8192:
                raise ValueError("PNG troppo grande o non valido (massimo 8192 px).")
        elif raw.startswith(b"\xff\xd8\xff"):
            ext, mime = "jpg", "image/jpeg"
        else:
            raise ValueError("Usa immagini PNG o JPEG.")
        image_id = uid()
        relative = f"uploads/{image_id}.{ext}"
        target = safe_join(self.data, relative)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)
        result = {"id": image_id, "name": str(body.get("name", "Immagine"))[:150], "path": relative, "mime": mime}
        target.with_suffix(".json").write_text(json.dumps(result), encoding="utf-8")
        return result

    def validate_media(self, media):
        if not isinstance(media, list) or len(media) > 4:
            raise ValueError("Allega fino a quattro immagini per messaggio.")
        resolved = []
        for item in media:
            image_id = item.get("id", "") if isinstance(item, dict) else ""
            if not re.fullmatch(r"[0-9a-f]{32}", image_id):
                raise ValueError("Riferimento immagine non valido.")
            meta_path = self.data / "uploads" / (image_id + ".json")
            if meta_path.exists():
                resolved.append(json.loads(meta_path.read_text(encoding="utf-8")))
            else:
                matches = self.store.all("SELECT media FROM messages WHERE role='assistant' AND status='done' UNION ALL SELECT media FROM canvases")
                found = next((m for row in matches for m in json.loads(row["media"]) if m["id"] == image_id), None)
                if not found:
                    raise ValueError("Immagine non trovata.")
                resolved.append(found)
        return resolved

    def send(self, chat_id, body):
        prompt = body.get("prompt", "")
        if not isinstance(prompt, str) or not prompt.strip() or len(prompt) > 24000:
            raise ValueError("Scrivi una richiesta tra 1 e 24.000 caratteri.")
        media = self.validate_media(body.get("media", []))
        settings = self.validate_settings({"think_level":body.get("think_level", self.store.settings()["think_level"])})
        self.engine.require_model(settings["chat_model"], "chat")
        canvas = body.get("canvas", False)
        if type(canvas) is not bool:
            raise ValueError("Destinazione canvas non valida.")
        job_id = self.store.enqueue(chat_id, prompt.strip(), media, settings, canvas)
        self.wake.set()
        return {"job_id": job_id}

    def cancel(self, job_id):
        with self.lock:
            job = self.store.one("SELECT * FROM jobs WHERE id=?", (job_id,))
            if not job:
                raise ValueError("Lavoro non trovato.")
            if self.current_id == job_id and self.cancel_event:
                self.cancel_event.set()
                self.engine.stop()
            elif job["status"] == "queued":
                self.store.execute("UPDATE jobs SET status='cancelled',stage='Interrotto' WHERE id=?", (job_id,))
                self.store.execute("UPDATE messages SET status='cancelled' WHERE id=?", (job["message_id"],))
        return {"ok": True}

    def delete_chat(self, chat_id):
        with self.lock:
            if self.store.one("SELECT id FROM jobs WHERE chat_id=? AND status IN ('running','queued')", (chat_id,)):
                raise ValueError("Interrompi prima il lavoro in questa chat.")
            self.store.execute("DELETE FROM chats WHERE id=?", (chat_id,))
        return {"ok": True}

    def run(self):
        while not self.closed.is_set():
            with self.lock:
                job = self.store.one("SELECT * FROM jobs WHERE status='queued' ORDER BY created LIMIT 1")
                if job:
                    self.store.execute("UPDATE jobs SET status='running' WHERE id=?", (job["id"],))
                    self.current_id, self.cancel_event = job["id"], threading.Event()
            if not job:
                self.wake.wait(0.5)
                self.wake.clear()
                continue
            self.execute_job(job, self.cancel_event)
            with self.lock:
                self.current_id, self.cancel_event = None, None

    def execute_job(self, job, cancel):
        text = ""
        meta = {}
        try:
            payload = json.loads(job["payload"])
            settings = payload["settings"]
            history = self.store.messages(job["chat_id"], payload["until"])
            for previous in history:
                artifact = previous.get("meta", {}).get("artifact")
                if artifact:
                    previous["content"] += "\nArtefatto nel canvas:\n" + artifact["content"]
                    previous["media"] = artifact["media"]
            snapshot = payload.get("canvas_snapshot")
            if snapshot:
                history.insert(-1, {"role":"user", "content":"Canvas attuale da modificare se richiesto:\n" + snapshot["content"],
                                   "media":json.loads(snapshot["media"]), "status":"done", "seq":-1})
            model = self.engine.require_model(settings["chat_model"], "chat")
            log_path = self.data / "logs" / (job["id"] + ".log")
            log_path.parent.mkdir(parents=True, exist_ok=True)
            def stage(label):
                self.store.execute("UPDATE jobs SET stage=? WHERE id=?", (label, job["id"]))
            stage("Caricamento del modello chat")
            self.engine.start_llama(model, settings, log_path, cancel)
            stage("Comprensione della richiesta")
            route = self.engine.route(history, settings, cancel)
            intent = route["intent"]
            meta = {"intent": intent, "model": model["name"], "settings": settings, "prompt": payload["prompt"], "canvas": payload.get("canvas", False)}
            meta.update(vision=model.get("vision",{}).get("enabled",False),
                        model_warning=model.get("vision",{}).get("warning",""),
                        think_level=settings.get("think_level","off") if model.get("thinking",{}).get("supported") else "off",
                        think_budget=thinking_parameters(model, settings)["reasoning_budget_tokens"])
            if intent == "chat":
                stage("Scrittura della risposta")
                last_update = 0
                def update(content):
                    nonlocal text, last_update, reason_started
                    if not content:
                        return
                    text = "Sto scrivendo nel canvas." if payload.get("canvas") else content
                    if content and reason_started:
                        stage("Scrittura della risposta")
                        reason_started = False
                    if time.monotonic() - last_update > 0.18:
                        self.store.update_answer(job, text, meta=meta)
                        if payload.get("canvas"):
                            self.save_artifact(job["chat_id"], partial_string(content, "title") or "Canvas", partial_string(content, "content"), [])
                        last_update = time.monotonic()
                reason_started = False
                def reasoning():
                    nonlocal reason_started
                    if not reason_started:
                        stage("Thinking · " + meta["think_level"])
                        reason_started = True
                messages = self.engine.chat_messages(history, model, settings)
                schema = None
                if payload.get("canvas"):
                    messages[0]["content"] += CANVAS_INSTRUCTIONS
                    schema = CANVAS_SCHEMA
                raw, finish = self.engine.completion(messages, settings, cancel, on_text=update, schema=schema, on_reasoning=reasoning)
                if payload.get("canvas"):
                    if finish == "length":
                        text = "Ho iniziato a scrivere nel canvas. Chiedimi di continuare."
                        self.save_artifact(job["chat_id"], partial_string(raw,"title") or "Canvas", partial_string(raw,"content"), [])
                    else:
                        artifact = json.loads(raw)
                        text = "Ho scritto l’artefatto nel canvas."
                        self.save_artifact(job["chat_id"], artifact["title"], artifact["content"], [])
                else:
                    text = raw
                meta["finish_reason"] = finish
                if payload.get("canvas"):
                    saved = self.store.one("SELECT * FROM canvases WHERE chat_id=?", (job["chat_id"],))
                    meta["artifact"] = {"title":saved["title"],"content":saved["content"],"media":json.loads(saved["media"])}
                self.store.update_answer(job, text, "done", meta=meta)
                stage("Risposta completata" if finish != "length" else "Limite di risposta raggiunto: puoi chiedere di continuare")
            else:
                image_model = self.engine.require_model(settings[intent + "_model"], intent)
                refs = payload["media"]
                if intent == "edit" and not refs:
                    refs = next((m["media"] for m in reversed(history) if m["media"]), [])
                if intent == "edit" and not refs:
                    raise ValueError("Per modificare un'immagine, allegala o generala prima in questa chat.")
                if intent == "create" and refs:
                    image_model = self.engine.require_model(settings["edit_model"], "edit")
                    intent = "edit"
                if len(refs) > image_model.get("max_refs", 1):
                    raise ValueError(f"Il modello accetta fino a {image_model.get('max_refs', 1)} riferimenti. Seleziona un modello compatibile nelle impostazioni.")
                meta.update(intent=intent, model=image_model["name"], image_prompt=route["prompt"] or payload["prompt"], references=refs)
                stage("Rilascio della memoria del modello chat")
                self.engine.stop()
                stage("Modifica immagine" if intent == "edit" else "Creazione immagine")
                media = self.engine.generate(image_model, settings, meta["image_prompt"], refs, job["id"], cancel, stage)
                text = "Ecco l'immagine modificata." if intent == "edit" else "Ecco l'immagine."
                if payload.get("canvas"):
                    self.save_artifact(job["chat_id"], "Immagine", "", [media])
                    text = "Ho creato l'immagine nel canvas."
                    meta["artifact"] = {"title":"Immagine","content":"","media":[media]}
                    self.store.update_answer(job, text, "done", [], meta)
                else:
                    self.store.update_answer(job, text, "done", [media], meta)
                stage("Immagine pronta")
            self.store.execute("UPDATE jobs SET status='done' WHERE id=?", (job["id"],))
        except Exception as exc:
            status = "cancelled" if isinstance(exc, Cancelled) or cancel.is_set() else "failed"
            error = "Generazione interrotta." if status == "cancelled" else str(exc)
            self.store.update_answer(job, text, status, meta=meta | {"error": error})
            self.store.execute("UPDATE jobs SET status=?,error=?,stage=? WHERE id=?", (status, error, error, job["id"]))
        finally:
            self.engine.stop()
            self.store.execute("UPDATE chats SET updated=? WHERE id=?", (time.time(), job["chat_id"]))

    def save_artifact(self, chat_id, title, content, media):
        self.store.execute("INSERT OR REPLACE INTO canvases VALUES (?,?,?,?,?)", (chat_id, title[:150], content, json.dumps(media), time.time()))

    def close(self):
        self.closed.set()
        self.wake.set()
        if self.cancel_event:
            self.cancel_event.set()
        for task in self.downloads.snapshot():
            self.downloads.cancel(task["id"])
        self.engine.stop()
        if self.worker.is_alive():
            self.worker.join(timeout=8)

    def hardware(self):
        return detect_hardware()


CANVAS_INSTRUCTIONS = """
Il canvas è ATTIVO. Rispondi esclusivamente con JSON conforme allo schema.
L’app aggiunge autonomamente un breve messaggio di accompagnamento nella chat.
title: titolo breve del documento o del grafico.
content: artefatto completo in Markdown, comprensivo di codice, LaTeX, mermaid e chart
secondo le regole precedenti. Questo campo appare soltanto nel canvas laterale.
Se l'utente chiede una modifica, riscrivi il documento completo aggiornato, mantenendo
le parti non coinvolte. Non rispondere con un diff o con "resto invariato".
"""
CANVAS_SCHEMA = {"type":"object", "properties":{k:{"type":"string"} for k in ("title","content")},
                 "required":["title","content"], "additionalProperties":False}


def partial_string(source, key):
    """Read one incomplete JSON string without eval and without exposing raw JSON."""
    match = re.search(r'"' + re.escape(key) + r'"\s*:\s*"', source)
    if not match:
        return ""
    pos, out = match.end(), []
    escapes = {'n':'\n','r':'\r','t':'\t','b':'\b','f':'\f','"':'"','/':'/','\\':'\\'}
    while pos < len(source):
        char = source[pos]
        if char == '"':
            break
        if char == '\\':
            pos += 1
            if pos >= len(source):
                break
            char = source[pos]
            if char == 'u':
                if pos + 4 >= len(source):
                    break
                try:
                    out.append(chr(int(source[pos+1:pos+5],16)))
                except ValueError:
                    break
                pos += 5
                continue
            out.append(escapes.get(char,char))
        else:
            out.append(char)
        pos += 1
    return ''.join(out).encode('utf-16', 'surrogatepass').decode('utf-16', 'ignore')

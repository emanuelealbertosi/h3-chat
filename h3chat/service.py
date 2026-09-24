from __future__ import annotations
from . import __version__
import base64
import json
import logging
import os
import re
import secrets
import subprocess
import threading
import time
from pathlib import Path
from .downloads import Cancelled, Downloads, model_ready, safe_join
from .engine import CREATE_NO_WINDOW, Engine, runtime_executable, explicit_route
from .visual_routing import visual_route
from .music_routing import route as music_route
from .music_options import validate as validate_music_options, validate_fields as validate_music_fields, NUMBERS as MUSIC_NUMBERS, DEFAULTS as MUSIC_DEFAULTS, INTEGER as MUSIC_INTEGER
from .music_runtime import status as music_status
from .vision_runtime import status as vision_status, SAMPLERS as VISION_SAMPLERS, SCHEDULERS as VISION_SCHEDULERS
from .llm_options import KEYS as LLM_KEYS, defaults as llm_defaults, merge as merge_llm_settings, validate_presets as validate_llm_presets
from .store import DEFAULTS, PROFILES, Store, uid
from .models import MAX_CONTEXT, discover_local, inspect_model, THINK_LEVELS, thinking_parameters, mtp_tokens
from .external_models import PROFILES as EXTERNAL_PROFILES, ROLE_LABELS, build_model, validate_config
from .hardware import detect_hardware, assess_model, assess_selection
from .loras import LoraLibrary, validate_directories, for_model as loras_for_model, public as public_loras
from .image_options import SAMPLERS, SCHEDULERS, NATIVE_SAMPLERS, NATIVE_SCHEDULERS, IMAGE_DEFAULT_KEYS, validate_overrides, options as image_options


LOG = logging.getLogger("h3chat.jobs")


class Service:
    def __init__(self, root, data=None, start_worker=True):
        self.root = Path(root).resolve()
        self.data = Path(data or self.root / "data").resolve()
        self.store = Store(self.data)
        self.catalog = {m["id"]: m for m in json.loads((self.root / "catalog.json").read_text(encoding="utf-8"))}
        self.runtimes = json.loads((self.root / "runtimes.json").read_text(encoding="utf-8"))
        self.downloads = Downloads(self.root, self.catalog, self.runtimes)
        self.engine = Engine(self.root, self.data, self.catalog)
        self.loras = LoraLibrary()
        self.token = secrets.token_hex(32)
        self.wake, self.closed = threading.Event(), threading.Event()
        self.lock = threading.RLock()
        self.current_id, self.cancel_event = None, None
        self.worker = threading.Thread(target=self.run, daemon=True)
        if start_worker:
            self.worker.start()

    def refresh_models(self):
        with self.lock:
            # Build the replacement before publishing: file/SQLite I/O must never
            # leave an externally linked model absent while the worker reads it.
            fresh={key:model for key,model in self.catalog.items() if not model.get("local")}
            fresh.update({m["id"]:m for m in discover_local(self.root)})
            for row in self.store.all("SELECT config FROM external_models"):
                model=build_model(json.loads(row["config"]))
                fresh[model["id"]]=model
            fresh={key:model|inspect_model(self.root,model) for key,model in fresh.items()}
            with self.engine.process_lock:
                # Preserve the shared dictionary used by Engine and Downloads.
                self.catalog.update(fresh)
                for key in list(self.catalog):
                    if key not in fresh: del self.catalog[key]
            return list(fresh.values())

    def state(self):
        models = self.refresh_models()
        return {"token": self.token, "version": __version__, "settings": self.store.settings(), "profiles": PROFILES,
                "llm_options":{"keys":LLM_KEYS,"defaults":{profile:llm_defaults(profile) for profile in PROFILES},"max_context":MAX_CONTEXT},
                "music_runtime":music_status(self.root), "music_options":{"defaults":MUSIC_DEFAULTS,"numbers":MUSIC_NUMBERS,"integers":sorted(MUSIC_INTEGER)},
                "vision_runtime":vision_status(self.root), "models": models,"image_options":{"samplers":NATIVE_SAMPLERS,"schedulers":NATIVE_SCHEDULERS,"vision_samplers":VISION_SAMPLERS,"vision_schedulers":VISION_SCHEDULERS,"defaults":{k:DEFAULTS[k] for k in IMAGE_DEFAULT_KEYS}},"external_profiles":EXTERNAL_PROFILES,"model_role_labels":ROLE_LABELS,
                "runtimes": {key: {"ready": vision_status(self.root)["ready"] if key=="vision" else music_status(self.root).get(key.removeprefix("music_"),{}).get("ready",False) if key.startswith("music_") else all(runtime_executable(self.root, key, e) for e in ("llama", "sd")),
                                    "size": sum(f["size"] for f in r["files"])} for key, r in self.runtimes.items()},
                "chats": self.store.all("SELECT * FROM chats ORDER BY pinned DESC,updated DESC"),
                "collections": self.store.all("SELECT * FROM collections ORDER BY name"),
                "jobs": self.store.all("SELECT id,chat_id,message_id,status,stage,error,created,json_extract(payload,'$.canvas') AS canvas FROM jobs ORDER BY created DESC LIMIT 100"),
                "downloads": self.downloads.snapshot(), "memory": self.engine.snapshot()}

    def external_model(self, body):
        with self.lock:
            model_id=body.get('id')
            if model_id and not self.store.one('SELECT id FROM external_models WHERE id=?',(model_id,)):
                raise ValueError('Collegamento non trovato.')
            config=validate_config(body,model_id)
            if self.current_id or self.store.one("SELECT id FROM jobs WHERE status IN ('queued','running')"):
                raise ValueError('Attendi o interrompi i lavori prima di cambiare i collegamenti ai modelli.')
            self.store.execute('INSERT OR REPLACE INTO external_models VALUES (?,?)',(config['id'],json.dumps(config)))
            self.refresh_models()
            model=self.catalog[config['id']]
            settings=self.store.settings()
            self.store.save_settings({key:'' for key,cap in (('chat_model','chat'),('create_model','create'),('edit_model','edit'),('diagram_model','create'),('music_model','music')) if settings[key]==config['id'] and (cap not in model['capabilities'] or (key=='diagram_model' and model.get('architecture')!='ming'))})
            self.engine.configure(self.store.settings())
            self.engine.cache.clear()
            return model | inspect_model(self.root,model)

    def remove_external_model(self, model_id):
        with self.lock:
            row=self.store.one('SELECT config FROM external_models WHERE id=?',(model_id,))
            if not row:raise ValueError('Collegamento non trovato.')
            if self.current_id or self.store.one("SELECT id FROM jobs WHERE status IN ('queued','running')"):
                raise ValueError('Attendi o interrompi i lavori prima di scollegare il modello.')
            self.store.execute('DELETE FROM external_models WHERE id=?',(model_id,))
            settings=self.store.settings()
            self.store.save_settings({key:'' for key in ('chat_model','create_model','edit_model','diagram_model','music_model') if settings[key]==model_id})
            self.refresh_models()
            self.engine.configure(self.store.settings())
            self.engine.cache.clear()
            return {'ok':True}

    def validate_settings(self, patch):
        self.refresh_models()
        if not isinstance(patch, dict) or set(patch) - set(DEFAULTS):
            raise ValueError("Impostazione sconosciuta.")
        current=self.store.settings()
        if 'llm_overrides' in patch:validate_llm_presets(patch['llm_overrides'],patch.get('profile',current['profile']))
        s = merge_llm_settings(current,patch)
        validate_llm_presets(s['llm_overrides'],s['profile'])
        if s["profile"] not in PROFILES or s["backend"] not in ("cpu","cuda","vulkan"):
            raise ValueError("Profilo hardware non valido.")
        for key, lo, hi in (("context", 1024, MAX_CONTEXT), ("gpu_layers", 0, 999), ("max_tokens", 64, 8192),
                            ("width", 256, 1536), ("height", 256, 1536), ("steps", 1, 100), ("threads", 1, 64), ("ram_cache_gb", 0, 32), ("mtp_draft_tokens", 1, 8)):
            if type(s[key]) is not int or not lo <= s[key] <= hi:
                raise ValueError(f"{key}: inserisci un intero tra {lo} e {hi}.")
        s['lora_dirs']=validate_directories(s['lora_dirs'])
        validate_overrides(s['image_overrides'])
        if type(s['image_advanced']) is not bool or type(s['chat_advanced']) is not bool:raise ValueError('Avanzate: usa un valore booleano.')
        if type(s['image_cfg']) not in (int,float) or not 0<=s['image_cfg']<=30:raise ValueError('CFG fuori intervallo.')
        if s['image_sampler'] not in NATIVE_SAMPLERS or s['image_scheduler'] not in NATIVE_SCHEDULERS:
            raise ValueError('Sampler o scheduler non supportato dal motore integrato.')
        if type(s['seed']) is not int or not -1<=s['seed']<=2147483647:raise ValueError('Seed: usa -1 per casuale oppure un intero da 0 a 2147483647.')
        if not isinstance(s['negative_prompt'],str) or len(s['negative_prompt'])>8000:raise ValueError('Negative prompt: massimo 8000 caratteri.')
        if s["max_tokens"] > s["context"] // 2:
            raise ValueError("I token di risposta non possono superare metà del contesto.")
        if s["width"] % 64 or s["height"] % 64:
            raise ValueError("Le dimensioni devono essere multipli di 64.")
        for key, lo, hi in (("temperature", 0, 2), ("strength", 0.05, 1)):
            if type(s[key]) not in (int, float) or not lo <= s[key] <= hi:
                raise ValueError(f"{key} fuori intervallo.")
        if not isinstance(s["system_prompt"], str) or len(s["system_prompt"]) > 8000:
            raise ValueError("Istruzioni di sistema troppo lunghe.")
        if type(s["mtp_enabled"]) is not bool:
            raise ValueError("MTP: scegli attivato o disattivato.")
        if type(s["setup_done"]) is not bool:
            raise ValueError("setup_done non valido.")
        for key, capability in (("chat_model", "chat"), ("create_model", "create"), ("edit_model", "edit"), ("diagram_model", "create"), ("music_model", "music")):
            if s[key] and (s[key] not in self.catalog or capability not in self.catalog[s[key]]["capabilities"]):
                raise ValueError(f"Modello incompatibile con {capability}.")
        if s['diagram_model'] and self.catalog[s['diagram_model']].get('architecture') != 'ming':
            raise ValueError('Per il routing dei grafici scegli un modello Ming.')
        if type(s['music_auto']) is not bool or type(s['music_advanced']) is not bool:raise ValueError('Musica: opzione non valida.')
        if s['music_backend'] not in ('auto','cpu','cuda'):raise ValueError('Musica: scegli CPU o CUDA.')
        if type(s['music_threads']) is not int or not 1<=s['music_threads']<=64:raise ValueError('Thread musica: scegli da 1 a 64.')
        if type(s['music_prompt_max_tokens']) is not int or not 256<=s['music_prompt_max_tokens']<=8192:raise ValueError('Token Assistant musica: scegli da 256 a 8192.')
        if not isinstance(s['music_overrides'],dict) or len(s['music_overrides'])>100:raise ValueError('Preset musica non validi.')
        for key,value in s['music_overrides'].items():
            if not isinstance(key,str) or len(key)>150:raise ValueError('Identificativo preset musicale non valido.')
            validate_music_options(value)
        if type(s['vision_enabled']) is not bool:raise ValueError('Vision: scegli On oppure Off.')
        if type(s['diagram_auto']) is not bool:raise ValueError('Routing grafici non valido.')
        if type(s['prompt_max_tokens']) is not int or not 256 <= s['prompt_max_tokens'] <= 8192:
            raise ValueError('Token Assistant: scegli tra 256 e 8192.')
        for model in self.catalog.values():
            if model.get('id') in s['image_overrides']:
                image_options(model,s)
        if s["memory_policy"] not in ("on_demand", "resident"):
            raise ValueError("Memoria: scegli A richiesta o Residenti.")
        if s.get("think_level") not in THINK_LEVELS:
            raise ValueError("Thinking: scegli off, low, med, high o xhigh.")
        return s

    def save_settings(self, patch):
        settings = self.validate_settings(patch)
        with self.lock:
            self.store.save_settings(settings)
            if not self.current_id:
                self.engine.configure(settings)
        return settings

    def release_memory(self):
        with self.lock:
            if self.current_id or self.store.one("SELECT id FROM jobs WHERE status IN ('queued','running')"):
                raise ValueError("Attendi o interrompi il lavoro prima di liberare la memoria.")
            self.engine.stop()
        return self.engine.snapshot()

    def assess(self, body):
        settings = self.validate_settings(body.get("settings", {}))
        refs = body.get("references", 1)
        if type(refs) is not int or not 0 <= refs <= 4:
            raise ValueError("Numero di riferimenti non valido.")
        hardware = self.hardware()
        models = self.refresh_models()
        chosen_loras=self.loras.capture(body.get("loras",[]),settings["lora_dirs"],self.catalog)
        selected = []
        selected_models = []
        for key in ("chat_model", "create_model", "edit_model", "diagram_model", "music_model"):
            model = next((m for m in models if m["id"] == settings[key]), None)
            if model:
                model=model|{"active_lora_bytes":sum(l["size"] for l in chosen_loras if l["model_id"]==model["id"] and l["weight"]!=0)}
                selected_models.append(model)
                selected.append(assess_model(model, settings, hardware, refs) | {"role":key})
        return {"hardware":hardware,"models":selected,"references":refs,
                "overall":assess_selection(selected_models,settings,hardware,refs),"memory":self.engine.snapshot()}

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

    def validate_media(self, media, *, canvas=False):
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
                if not canvas and not str(found.get("mime","")).startswith("image/"):raise ValueError("Il motore immagini richiede un riferimento PNG o JPEG, non un brano audio.")
                resolved.append(found)
        return resolved

    def send(self, chat_id, body):
        prompt = body.get("prompt", "")
        if not isinstance(prompt, str) or not prompt.strip() or len(prompt) > 24000:
            raise ValueError("Scrivi una richiesta tra 1 e 24.000 caratteri.")
        media = self.validate_media(body.get("media", []))
        settings = self.validate_settings({"think_level":body.get("think_level", self.store.settings()["think_level"])})
        selection = body.get('image_model','')
        if not isinstance(selection,str):raise ValueError('Selezione modello immagini non valida.')
        if selection:
            self.engine.require_model(selection,'edit' if media else 'create')
        assistant = body.get('assistant',True)
        if type(assistant) is not bool:raise ValueError('Assistant: scegli On oppure Off.')
        music=body.get('music',False)
        if type(music) is not bool:raise ValueError('Music: scegli attivo o disattivo.')
        if music and selection:raise ValueError('Scegli Music oppure un modello immagini esplicito.')
        fields=validate_music_fields(body.get('music_fields',{}))
        settings = settings | {'_image_model':selection,'_assistant':assistant,'_music':music,'_music_fields':fields}
        request_history=[{'content':prompt,'media':media}]
        direct_media=music_route(request_history,settings) or visual_route(request_history,settings) or explicit_route(request_history) in ('create','edit')
        if assistant or not direct_media:
            self.engine.require_model(settings["chat_model"], "chat")
        canvas = body.get("canvas", False)
        if type(canvas) is not bool:
            raise ValueError("Destinazione canvas non valida.")
        loras=self.loras.capture(body.get('loras',[]),settings['lora_dirs'],self.catalog)
        job_id = self.store.enqueue(chat_id, prompt.strip(), media, settings, canvas, loras)
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
                self.engine.configure(self.store.settings())

    def execute_job(self, job, cancel):
        text = ""
        meta = {}
        try:
            payload = json.loads(job["payload"])
            settings = DEFAULTS | payload["settings"]
            history = self.store.messages(job["chat_id"], payload["until"])
            for previous in history:
                composition=previous.get("meta",{}).get("music_composition")
                if composition:previous["content"] += "\nComposizione del brano (non ascolto audio):\n"+json.dumps(composition,ensure_ascii=False)
                artifact = previous.get("meta", {}).get("artifact")
                if artifact:
                    previous["content"] += "\nArtefatto nel canvas:\n" + artifact["content"]
                    previous["media"] = artifact["media"]
            snapshot = payload.get("canvas_snapshot")
            if snapshot:
                history.insert(-1, {"role":"user", "content":"Canvas attuale da modificare se richiesto:\n" + snapshot["content"],
                                   "media":json.loads(snapshot["media"]), "status":"done", "seq":-1})
            log_path = self.data / "logs" / (job["id"] + ".log")
            log_path.parent.mkdir(parents=True, exist_ok=True)
            def stage(label):
                LOG.info("Lavoro %s · %s", job["id"][:8], label)
                self.store.execute("UPDATE jobs SET stage=? WHERE id=?", (label, job["id"]))
            self.engine.prepare(settings, cancel, stage)
            visual_history=[m|{"media":[x for x in m["media"] if x.get("mime", "").startswith("image/")]} for m in history]
            selected_route = music_route(history,settings) or visual_route(visual_history,settings)
            direct = explicit_route(visual_history)
            direct_media=(selected_route or direct in ('create','edit')) and not settings.get('_assistant',True)
            model={} if direct_media else self.engine.require_model(settings["chat_model"], "chat")
            if selected_route:
                route = selected_route
            elif direct in ('create', 'edit'):
                route = {'intent':direct,'prompt':history[-1]['content']}
            else:
                stage("Caricamento / riuso del modello chat")
                self.engine.start_llama(model, settings, log_path, cancel, stage=stage)
                stage("Comprensione della richiesta")
                route = self.engine.route(history, settings, cancel)
            intent = route["intent"]
            meta = {"intent": intent, "model": model.get("name", ""), "settings": settings, "prompt": payload["prompt"], "canvas": payload.get("canvas", False)}
            if model:meta.update(vision=settings.get("vision_enabled",True) and model.get("vision",{}).get("enabled",False),
                        model_warning=model.get("vision",{}).get("warning","") if settings.get("vision_enabled",True) else "Vision Off · il proiettore non è caricato.",
                        think_level=settings.get("think_level","off") if model.get("thinking",{}).get("supported") else "off",
                        think_budget=thinking_parameters(model, settings)["reasoning_budget_tokens"],
                        mtp_tokens=mtp_tokens(model,settings) if intent=="chat" else 0, max_tokens=settings["max_tokens"])
            if intent!='chat':
                for key in ('think_level','think_budget','model_warning'):meta.pop(key,None)
            self.store.update_answer(job,text,meta=meta)
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
                messages = self.engine.chat_messages(visual_history, model, settings)
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
            elif intent == "music":
                music_model=self.engine.require_model(settings['music_model'],'music')
                meta['model']=music_model['name'];self.store.update_answer(job,text,meta=meta)
                composition,assistant_info=self.engine.refine_music(history,payload['prompt'],settings.get('_music_fields',{}),settings,cancel,log_path,stage)
                media=self.engine.generate_music(music_model,settings,composition,job['id'],cancel,stage)
                meta.update(model=music_model['name'],assistant_on=settings.get('_assistant',True),assistant=assistant_info,
                            music_composition=composition,music_parameters=media['generation'],music_selection=route.get('selection','auto'))
                meta.pop('model_warning',None);meta.pop('think_level',None)
                warning=' Il brano ha raggiunto il limite di token: la fine può essere troncata.' if media['generation'].get('audio_truncated') or media['generation'].get('abc_truncated') else ''
                if payload.get('canvas'):
                    content='## '+composition['title']+'\n\n'+composition['lyrics'].replace('\n','  \n')
                    self.save_artifact(job['chat_id'],composition['title'],content,[media])
                    meta['artifact']={'title':composition['title'],'content':content,'media':[media]}
                    self.store.update_answer(job,'Ho creato il brano nel canvas.'+warning,'done',[],meta)
                else:
                    self.store.update_answer(job,'Ecco il brano «'+composition['title']+'».'+warning,'done',[media],meta)
                stage('Brano pronto')
            else:
                image_model = self.engine.require_model(route.get("image_model") or settings[intent + "_model"], intent)
                refs = [m for m in payload["media"] if m.get("mime", "").startswith("image/")]
                if intent == "edit" and not refs:
                    refs = next(([x for x in m["media"] if x.get("mime", "").startswith("image/")] for m in reversed(history) if any(x.get("mime", "").startswith("image/") for x in m["media"])), [])
                if intent == "edit" and not refs:
                    raise ValueError("Per modificare un'immagine, allegala o generala prima in questa chat.")
                if intent == "create" and refs:
                    image_model = self.engine.require_model(route.get("image_model") or settings["edit_model"], "edit")
                    intent = "edit"
                if len(refs) > image_model.get("max_refs", 1):
                    raise ValueError(f"Il modello accetta fino a {image_model.get('max_refs', 1)} riferimenti. Seleziona un modello compatibile nelle impostazioni.")
                meta.update(intent=intent, model=image_model["name"], image_prompt=payload["prompt"], references=refs)
                meta['model']=image_model['name'];self.store.update_answer(job,text,meta=meta)
                meta['image_selection'] = route.get('selection','auto')
                meta['assistant_on'] = bool(settings.get('_assistant',True))
                if meta['assistant_on']:
                    meta['original_image_prompt'] = meta['image_prompt']
                    meta['image_prompt'],meta['assistant'] = self.engine.refine_image_prompt(
                        history,meta['image_prompt'],refs,settings,cancel,log_path,stage,image_model=image_model)
                selected_loras=loras_for_model(payload.get('loras',[]),image_model)
                generation_settings=settings|{'_image_model':image_model['id'],'_loras':selected_loras,'_image_options':image_options(image_model,settings)}
                meta['loras']=public_loras(selected_loras)
                meta['image_parameters']=generation_settings['_image_options']
                meta['loras_skipped']=public_loras([l for l in payload.get('loras',[]) if l not in selected_loras])
                stage("Modifica immagine" if intent == "edit" else "Creazione immagine")
                media = self.engine.generate(image_model, generation_settings, meta["image_prompt"], refs, job["id"], cancel, stage)
                if media.get('generation'):meta['image_parameters'].update(media['generation'])
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
            self.engine.abort_active()
            status = "cancelled" if isinstance(exc, Cancelled) or cancel.is_set() else "failed"
            error = "Generazione interrotta." if status == "cancelled" else str(exc)
            LOG.log(logging.INFO if status == "cancelled" else logging.ERROR, "Lavoro %s · %s", job["id"][:8], error)
            self.store.update_answer(job, text, status, meta=meta | {"error": error})
            self.store.execute("UPDATE jobs SET status=?,error=?,stage=? WHERE id=?", (status, error, error, job["id"]))
        finally:
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

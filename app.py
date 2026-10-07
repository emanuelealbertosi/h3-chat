"""Loopback HTTP host with optional private Tailscale HTTPS access."""
from __future__ import annotations
import argparse
import hashlib
import json
import logging
import mimetypes
import secrets
import sqlite3
import threading
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from h3chat.downloads import safe_join
from h3chat.service import Service
from h3chat import __version__
from h3chat.media_http import send_audio
from h3chat.external_models import browse, suggest
from h3chat.pdf_export import export_pdf
from h3chat.store import uid
from h3chat.tailscale_access import TailscaleAccess
from h3chat.document_limits import IMPORT_CHUNK_BYTES
from h3chat.access import Access,LoginRequired,LoginLimited,local_request,password_matches
from h3chat.workspaces import Workspaces,guest_allowed,guest_state

ROOT = Path(__file__).resolve().parent
LOG = logging.getLogger("h3chat.http")


class Handler(BaseHTTPRequestHandler):
    server_version = "H3Chat/0.1"

    @property
    def app(self):
        identity=getattr(self,'identity',None)
        spaces=getattr(self.server,'workspaces',None)
        return spaces.get(identity) if spaces and identity else self.server.app

    def log_message(self, format, *args):
        pass

    def json(self, value, status=200, headers=None):
        path = urllib.parse.urlsplit(self.path).path
        if status >= 400:
            LOG.warning("%s %s — %s: %s", self.command, path, status, value.get("error", "Errore"))
        elif self.command != "GET" and path != "/api/assess":
            LOG.info("%s %s — %s", self.command, path, status)
        body = json.dumps(value, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        for name,value in (headers or {}).items():self.send_header(name,value)
        self.end_headers()
        self.wfile.write(body)

    def guard(self):
        allowed = {f"127.0.0.1:{self.server.server_port}", f"localhost:{self.server.server_port}"}
        origins = {"http://" + host for host in allowed}
        network = getattr(self.server, 'network', None)
        if network:
            origins.update(network.origins)
            allowed.update(urllib.parse.urlsplit(url).netloc for url in network.origins)
        if self.headers.get("Host") not in allowed:
            raise PermissionError("Host non consentito.")
        origin = self.headers.get("Origin")
        if origin and origin not in origins:
            raise PermissionError("Origine non consentita.")
        if self.headers.get("Sec-Fetch-Site") == "cross-site":
            raise PermissionError("Richiesta da un altro sito non consentita.")
        access=getattr(self.server,'access',None)
        path=urllib.parse.unquote(urllib.parse.urlsplit(self.path).path)
        if access:
            maintenance=(path in ('/api/maintenance/state','/api/shutdown','/api/network/refresh') and local_request(self)
                and secrets.compare_digest(self.headers.get('X-H3-Token',''),access.maintenance))
            self.identity={'id':'maintenance','role':'owner','name':'Avvio locale','csrf':access.maintenance} if maintenance else access.identity(self)
            public=(self.command=='GET' and (path in ('/','/login','/api/health','/api/auth/me') or path.startswith('/static/'))) or path=='/api/auth/login'
            if public:return
            if not self.identity:raise LoginRequired('Accedi con il tuo account o una chiave.')
            if path=='/api/maintenance/state' and not maintenance:raise PermissionError('Operazione riservata all’avvio locale.')
            if self.identity['role']=='guest' and not path.startswith('/api/auth/') and not guest_allowed(path,self.command):
                raise PermissionError('Operazione riservata all’amministratore.')
            if self.command in ('POST','PATCH','DELETE','PUT') and not self.identity.get('bearer'):
                if not secrets.compare_digest(self.headers.get('X-H3-Token',''),self.identity['csrf']):raise PermissionError('Sessione scaduta. Ricarica la pagina.')
            return
        if self.command in ("POST", "PATCH", "DELETE", "PUT"):
            if not secrets.compare_digest(self.headers.get("X-H3-Token", ""), self.app.token):
                raise PermissionError("Sessione scaduta. Ricarica la pagina.")

    def read_body(self):
        if "application/json" not in self.headers.get("Content-Type", ""):
            raise ValueError("È richiesto un corpo JSON.")
        length = int(self.headers.get("Content-Length", "0"))
        limit=4096 if urllib.parse.urlsplit(self.path).path.startswith('/api/auth/') else 90*1024*1024
        if length < 0 or length > limit:
            raise ValueError("Richiesta troppo grande.")
        body = json.loads(self.rfile.read(length) or b"{}")
        if not isinstance(body, dict):
            raise ValueError("Il corpo deve essere un oggetto.")
        return body

    def file(self, path):
        if not path.is_file():
            self.json({"error": "File non trovato."}, 404)
            return
        if path.suffix.lower() in ('.wav','.mp3','.ogg','.flac','.mp4'):return send_audio(self,path)
        body = path.read_bytes()
        self.send_response(200)
        mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        if path.suffix.lower() in ('.html','.js','.css'):
            self.send_header("Cache-Control", "no-store")
        if path.suffix.lower() in ('.html','.svg') and not path.resolve().is_relative_to((ROOT/'static').resolve()):
            self.send_header('Content-Security-Policy',"default-src 'none'; script-src 'none'; style-src 'unsafe-inline'; img-src data:; font-src data:; form-action 'none'; base-uri 'none'")
        else:self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; font-src 'self' data:; media-src 'self' blob:; connect-src 'self'; object-src 'none'; frame-src 'self'; base-uri 'self'; form-action 'self'")
        self.end_headers()
        self.wfile.write(body)

    def handle_request(self):
        try:
            self.guard()
            path = urllib.parse.unquote(urllib.parse.urlsplit(self.path).path)
            parts = [p for p in path.split("/") if p]
            method = self.command
            access=getattr(self.server,'access',None)
            if access and path.startswith('/api/auth/'):
                return self.auth_request(path,method)
            if method == "GET":
                if path=='/api/gallery':
                    query=urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query)
                    return self.json(self.app.store.gallery.listing(query.get('q',[''])[0],query.get('kind',['all'])[0],query.get('origin',['all'])[0],int(query.get('offset',['0'])[0])))
                if len(parts)==2 and parts[0]=='gallery-file':
                    item=self.app.store.gallery.get(parts[1])
                    return self.file(safe_join(self.app.data,item['path']))
                if path=='/api/maintenance/state':
                    return self.json(self.server.workspaces.maintenance_state()|{'token':access.maintenance})
                if len(parts)==3 and parts[:2]==['api','projects']:
                    return self.json(self.app.knowledge.project(parts[2]))
                if path == "/api/health":
                    return self.json({"app": "h3-chat", "version": __version__, "worker_alive": self.app.worker.is_alive(), "instance": hashlib.sha256(str(ROOT).encode()).hexdigest()[:16], 'network': getattr(self.server, 'network', None).status if getattr(self.server, 'network', None) else {}})
                if path == "/api/state":
                    value=self.app.state() | {'network': getattr(self.server, 'network', None).status if getattr(self.server, 'network', None) else {}}
                    if access:
                        value['token']=self.identity['csrf'];value['access']={k:self.identity[k] for k in ('id','name','role')}
                        if self.identity['role']=='guest':value=guest_state(value)
                    return self.json(value)
                if path == "/api/hardware":
                    return self.json(self.app.hardware())
                if len(parts) == 3 and parts[:2] == ["api", "chats"]:
                    return self.json(self.app.store.chat(parts[2]))
                if len(parts) == 3 and parts[:2] == ["api", "canvas"]:
                    return self.json(self.app.store.canvas_history.get(parts[2]))
                if len(parts) == 4 and parts[:2] == ['api', 'canvas'] and parts[3] == 'history':
                    return self.json(self.app.store.canvas_history.listing(parts[2]))
                if len(parts) == 5 and parts[:2] == ['api', 'canvas'] and parts[3] == 'history':
                    return self.json(self.app.store.canvas_history.get(parts[2], parts[4]))
                if path == "/":
                    if access and not self.identity:return self.file(ROOT/'static/login.html')
                    return self.file(ROOT / "static/index.html")
                if path=='/login':return self.file(ROOT/'static/login.html')
                if path=='/access':return self.file(ROOT/'static/access.html')
                if path.startswith("/static/"):
                    return self.file(safe_join(ROOT / "static", path[len("/static/"):]))
                if path.startswith("/exports/"):
                    relative = path[len("/exports/"):]
                    if len(parts) != 3 or parts[-1] not in ("document.pdf","document.html","audio.wav","audio.mp3"):
                        raise PermissionError("File non disponibile.")
                    return self.file(safe_join(self.app.data / "exports", relative))
                if path.startswith("/media/"):
                    relative = path[len("/media/"):]
                    if not relative.startswith(("uploads/", "outputs/", "project-imports/", "exports/")) or Path(relative).suffix not in (".png", ".jpg", ".wav", ".mp3", ".flac", ".ogg", ".mp4", ".pdf", ".docx", ".pptx", ".txt", ".md", ".srt", ".py", ".json", ".tex", ".log", ".html", ".svg"):
                        raise PermissionError("File non disponibile.")
                    if relative.startswith(('project-imports/','exports/')) and not self.app.store.one('SELECT 1 FROM gallery WHERE path=?',(relative,)):raise PermissionError('File non disponibile.')
                    return self.file(safe_join(self.app.data, relative))
                return self.json({"error": "Risorsa non trovata."}, 404)
            # Binary project blocks have their own small bound; other requests
            # retain the existing JSON/body limits and CSRF guard above.
            if len(parts)==5 and parts[:2]==['api','projects'] and parts[3]=='import' and method=='PATCH':
                if self.headers.get('Content-Type','').split(';')[0]!='application/octet-stream':raise ValueError('Blocco documento non valido.')
                length=int(self.headers.get('Content-Length','0'))
                if not 0<length<=IMPORT_CHUNK_BYTES:raise ValueError('Blocco documento troppo grande.')
                offset=int(self.headers.get('X-H3-Offset','-1'));raw=self.rfile.read(length)
                if len(raw)!=length:raise ValueError('Blocco documento incompleto.')
                return self.json(self.app.knowledge.uploads.append(parts[2],parts[4],offset,raw))
            body = self.read_body()
            if len(parts)==5 and parts[:2]==['api','canvas'] and parts[3:]==['infographic','render'] and method=='POST':
                from h3chat.infographics import enqueue_render
                return self.json(enqueue_render(self.app,parts[2],body),202)
            if path=='/api/gallery/select' and method=='POST':
                return self.json(self.app.validate_media([{'id':ident} for ident in body.get('ids',[])],canvas=True))
            if path=='/api/gallery/import' and method=='POST':
                import base64
                try:digest=hashlib.sha256(base64.b64decode(body.get('data',''),validate=True)).hexdigest()
                except (ValueError,TypeError):raise ValueError('File esportato non valido.')
                existing=self.app.store.one('SELECT id FROM gallery_exports WHERE hash=?',(digest,))
                if existing:
                    try:return self.json(self.app.store.gallery.get(existing['id']))
                    except ValueError:pass
                item=self.app.upload(body|{'_gallery_export':True});self.app.store.execute('INSERT OR REPLACE INTO gallery_exports VALUES (?,?)',(digest,item['id']));return self.json(item,201)
            if len(parts)==5 and parts[:2]==['api','canvas'] and parts[3:]==['slides','regenerate'] and method=='POST':
                from h3chat.slide_revision import enqueue
                return self.json(enqueue(self.app,parts[2],body),202)
            if access and self.identity['role']=='guest':
                if path=='/api/settings':return self.json(self.server.workspaces.preferences(self.identity,body))
                if path=='/api/knowledge/options':return self.json(self.server.workspaces.preferences(self.identity,body,rag=True))
            if path == '/api/network/refresh' and method == 'POST':
                return self.json(self.server.network.refresh())
            if path=='/api/server/start' and method=='POST':return self.json(self.app.media_server.start(body))
            if path=='/api/server/stop' and method=='POST':
                self.app.media_server.close();return self.json({'ok':True})
            if path=='/api/media-providers' and method=='POST':return self.json(self.app.media_provider_request(body),201)
            if path=='/api/media-providers/test' and method=='POST':return self.json(self.app.media_provider_request(body,'test'))
            if len(parts)==3 and parts[:2]==['api','media-providers'] and method=='DELETE':return self.json(self.app.media_provider_request({'id':parts[2]},'delete'))
            if path=='/api/knowledge/embedding-default' and method=='POST':
                if body.get('id')=='embeddinggemma2':
                    from h3chat.embeddinggemma2 import checkpoint
                    target,_=checkpoint(ROOT/'models/EmbeddingGemma-2')
                    return self.json({'path':str(target)})
                if body.get('id')=='ovis-omni-3b':
                    from h3chat.ovis import checkpoint
                    target,_=checkpoint(ROOT/'models/Ovis-Omni-Embedding-3B')
                    return self.json({'path':str(target)})
                if body.get('id','embeddinggemma')!='embeddinggemma':raise ValueError('Modello embedding sconosciuto.')
                target=ROOT/'models/embeddinggemma/embeddinggemma-300M-Q8_0.gguf'
                if not target.is_file():raise ValueError('Scarica prima EmbeddingGemma dalle Preferenze.')
                return self.json({'path':str(target)})
            if path=='/api/knowledge/options' and method=='POST':return self.json(self.app.save_rag_options(body))
            if path=='/api/projects' and method=='POST':return self.json(self.app.knowledge.save(body),201)
            if len(parts)>=3 and parts[:2]==['api','projects']:
                ident=parts[2]
                if len(parts)==3 and method=='PATCH':return self.json(self.app.knowledge.save(body,ident))
                if len(parts)==3 and method=='DELETE':return self.json(self.app.knowledge.delete(ident))
                if len(parts)==4 and parts[3]=='sources' and method=='POST':return self.json(self.app.knowledge.add(ident,body),202)
                if len(parts)==4 and parts[3]=='import' and method=='POST':return self.json(self.app.knowledge.import_file(ident,body),201)
                if len(parts)==5 and parts[3:]==['import','start'] and method=='POST':return self.json(self.app.knowledge.uploads.start(ident,body),201)
                if len(parts)==6 and parts[3]=='import' and parts[5]=='finish' and method=='POST':return self.json(self.app.knowledge.uploads.finish(ident,parts[4]),201)
                if len(parts)==5 and parts[3]=='import' and method=='DELETE':return self.json(self.app.knowledge.uploads.cancel(ident,parts[4]))
                if len(parts)==4 and parts[3]=='refresh' and method=='POST':return self.json(self.app.knowledge.refresh(ident),202)
                if len(parts)==4 and parts[3]=='web-sources' and method=='POST':return self.json(self.app.save_web_sources(ident,body),202)
                if len(parts)==5 and parts[3]=='sources' and method=='DELETE':return self.json(self.app.knowledge.remove(ident,parts[4]))
                if len(parts)==5 and parts[3]=='roots' and method=='DELETE':
                    self.app.knowledge.mutable(ident);self.app.store.execute('DELETE FROM project_roots WHERE id=? AND project_id=?',(parts[4],ident));return self.json({'ok':True})
            if path in ('/api/providers','/api/providers/models','/api/providers/test') and method=='POST':
                return self.json(self.app.provider_request(body,'models' if path.endswith('/models') else 'test' if path.endswith('/test') else 'save'))
            if len(parts)==3 and parts[:2]==['api','providers'] and method=='DELETE':
                return self.json(self.app.remove_provider(parts[2]))
            if path == "/api/loras" and method == "POST":
                return self.json(self.app.loras.scan(self.app.store.settings()["lora_dirs"],refresh=body.get("refresh") is True))
            if path == "/api/model-files/browse" and method == "POST":
                return self.json(browse(body))
            if path == "/api/model-files/suggest" and method == "POST":
                return self.json(suggest(body))
            if path == "/api/external-models" and method == "POST":
                return self.json(self.app.external_model(body),201)
            if len(parts)==3 and parts[:2]==["api","external-models"] and method=="DELETE":
                return self.json(self.app.remove_external_model(parts[2]))
            if path == "/api/export/pdf" and method == "POST":
                return self.json(self.app.store.gallery.exported(export_pdf(ROOT, self.app.data, body)))
            if path == "/api/export/audio" and method == "POST":
                from h3chat.audio_export import export_audio
                media=self.app.validate_media([{'id':body.get('id')}],canvas=True)[0]
                return self.json(self.app.store.gallery.exported(export_audio(ROOT,self.app.data,media,body.get('format'))))
            if path == "/api/export/html" and method == "POST":
                from h3chat.pdf_export import export_html
                return self.json(self.app.store.gallery.exported(export_html(ROOT, self.app.data, body)))
            if path == "/api/memory/release" and method == "POST":
                return self.json(self.app.release_memory())
            if path == "/api/assess" and method == "POST":
                return self.json(self.app.assess(body))
            if path == "/api/settings" and method == "POST":
                return self.json(self.app.save_settings(body))
            if len(parts)==4 and parts[:3]==['api','slides','images'] and method=='POST':
                from h3chat.slide_images import request
                return self.json(request(self.app,parts[3],body))
            if path == "/api/uploads" and method == "POST":
                return self.json(self.app.upload(body), 201)
            if path == "/api/chats" and method == "POST":
                return self.json(self.app.store.create_chat(collection_id=body.get("collection_id"),project_id=body.get('project_id')), 201)
            if path == "/api/downloads" and method == "POST":
                return self.json({"id": self.app.downloads.start(body["id"], body.get("kind", "model"))}, 202)
            if len(parts) == 4 and parts[:2] == ["api", "downloads"] and parts[3] == "cancel":
                self.app.downloads.cancel(parts[2])
                return self.json({"ok": True})
            if len(parts) == 4 and parts[:2] == ["api", "jobs"] and parts[3] == "cancel":
                return self.json(self.app.cancel(parts[2]))
            if len(parts) == 4 and parts[:2] == ["api", "chats"] and parts[3] == "messages" and method == "POST":
                return self.json(self.app.send(parts[2], body), 202)
            if len(parts) == 4 and parts[:2] == ["api", "chats"] and parts[3] == "regenerate" and method == "POST":
                return self.json(self.app.regenerate(parts[2]), 202)
            if len(parts) == 4 and parts[:2] == ['api','chats'] and parts[3] == 'recover-manim' and method == 'POST':
                from h3chat.manim_artifact import recover
                return self.json(recover(self.app,parts[2],body.get('message_id')))
            if len(parts) == 3 and parts[:2] == ["api", "chats"]:
                chat_id = parts[2]
                if method == "DELETE":
                    return self.json(self.app.delete_chat(chat_id))
                if method == "PATCH":
                    allowed = {"title", "pinned", "archived", "collection_id", "project_id"}
                    if not body or set(body) - allowed:
                        raise ValueError("Modifica chat non valida.")
                    for key, value in body.items():
                        if key=='project_id':
                            if self.app.store.one("SELECT id FROM jobs WHERE chat_id=? AND status IN ('queued','running')",(chat_id,)):raise ValueError('Attendi il lavoro prima di spostare la chat.')
                            if value is not None:self.app.knowledge.project(value)
                        if key == "title" and (not isinstance(value, str) or not value.strip() or len(value) > 150):
                            raise ValueError("Titolo non valido.")
                        if key in ("pinned", "archived") and type(value) is not bool:
                            raise ValueError("Valore non valido.")
                    values = list(body.values()) + [time.time(), chat_id]
                    self.app.store.execute("UPDATE chats SET " + ",".join(k + "=?" for k in body) + ",updated=? WHERE id=?", values)
                    return self.json(self.app.store.chat(chat_id))
            if path == "/api/collections" and method == "POST":
                name = body.get("name", "")
                if not isinstance(name, str) or not name.strip() or len(name) > 80:
                    raise ValueError("Nome raccolta non valido.")
                collection_id = uid()
                self.app.store.execute("INSERT INTO collections VALUES (?,?)", (collection_id, name.strip()))
                return self.json({"id": collection_id, "name": name.strip()}, 201)
            if len(parts) == 3 and parts[:2] == ["api", "collections"]:
                if method == "DELETE":
                    self.app.store.execute("DELETE FROM collections WHERE id=?", (parts[2],))
                    return self.json({"ok": True})
                if method == "PATCH":
                    name = body.get("name", "")
                    if not isinstance(name, str) or not name.strip() or len(name) > 80:
                        raise ValueError("Nome raccolta non valido.")
                    self.app.store.execute("UPDATE collections SET name=? WHERE id=?", (name.strip(), parts[2]))
                    return self.json({"ok": True})
            if len(parts) == 3 and parts[:2] == ["api", "canvas"] and method == "PUT":
                self.app.store.chat(parts[2])
                title, content = body.get("title", "Canvas"), body.get("content", "")
                if not isinstance(title, str) or len(title) > 150 or not isinstance(content, str) or len(content) > 200000:
                    raise ValueError("Canvas troppo grande o non valido.")
                if self.app.store.one("SELECT id FROM jobs WHERE chat_id=? AND status IN ('queued','running') AND json_extract(payload,'$.canvas')=1", (parts[2],)):
                    raise ValueError("Il motore sta scrivendo nel canvas. Attendi o interrompilo prima di modificare.")
                media = self.app.validate_media(body.get("media", []),canvas=True)
                from h3chat.slides import validate_content
                validate_content(content,media)
                if body.get('id') is not None and not isinstance(body['id'], str):
                    raise ValueError('Riferimento artefatto non valido.')
                return self.json(self.app.store.canvas_history.save(parts[2], {'title':title, 'content':content, 'media':media}, edit_id=body.get('id'), editable=True))
            if len(parts) == 6 and parts[:2] == ['api', 'canvas'] and parts[3] == 'history' and parts[5] == 'restore' and method == 'POST':
                if self.app.store.one("SELECT id FROM jobs WHERE chat_id=? AND status IN ('queued','running') AND json_extract(payload,'$.canvas')=1", (parts[2],)):
                    raise ValueError('Il motore sta scrivendo nel canvas. Attendi o interrompilo prima di ripristinare.')
                return self.json(self.app.store.canvas_history.restore(parts[2], parts[4]))
            if path == "/api/shutdown" and method == "POST":
                self.json({"ok": True})
                threading.Thread(target=self.server.shutdown, daemon=True).start()
                return
            self.json({"error": "Operazione non trovata."}, 404)
        except LoginRequired as exc:
            self.json({'error':str(exc),'login':True},401)
        except LoginLimited as exc:
            self.json({'error':str(exc)},429,{'Retry-After':'600'})
        except PermissionError as exc:
            self.json({"error": str(exc)}, 403)
        except (ValueError, KeyError, TypeError, sqlite3.IntegrityError) as exc:
            self.json({"error": str(exc)}, 400)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            pass
        except Exception as exc:
            LOG.exception("Errore interno durante %s %s", self.command, urllib.parse.urlsplit(self.path).path)
            self.json({"error": str(exc)}, 500)

    do_GET = do_POST = do_PATCH = do_DELETE = do_PUT = handle_request

    def auth_request(self,path,method):
        access=self.server.access;identity=getattr(self,'identity',None)
        secure=not local_request(self)
        if path=='/api/auth/me' and method=='GET':
            return self.json({'configured':access.configured(),'local':local_request(self),'user':{k:identity[k] for k in ('id','name','role')} if identity else None,'csrf':identity.get('csrf','') if identity else ''})
        if path=='/api/auth/login' and method=='POST':
            body=self.read_body();peer=self.headers.get('Tailscale-User-Login') or self.client_address[0]
            raw,csrf=access.login(body,peer)
            return self.json({'ok':True},headers={'Set-Cookie':access.cookie(raw,secure)})
        if path=='/api/auth/setup' and method=='POST':
            if not local_request(self) or not identity.get('bootstrap'):raise PermissionError('Configura l’amministratore dal PC che ospita H3-Chat.')
            user=access.create(self.read_body(),owner=True);raw,_=access.session(user)
            return self.json({'ok':True},201,{'Set-Cookie':access.cookie(raw,secure)})
        if not identity:raise LoginRequired('Accedi prima di continuare.')
        if identity.get('bootstrap'):raise ValueError('Configura prima l’amministratore.')
        if path=='/api/auth/logout' and method=='POST':
            self.read_body();access.logout(identity)
            return self.json({'ok':True},headers={'Set-Cookie':access.cookie('',secure)})
        if path=='/api/auth/users':
            if identity['role']!='owner':raise PermissionError('Gestione account riservata all’amministratore.')
            if method=='GET':return self.json({'users':access.users()})
            if method=='POST':return self.json(access.create(self.read_body()),201)
        parts=path.strip('/').split('/')
        if len(parts)==4 and parts[:3]==['api','auth','users'] and method=='PATCH':
            if identity['role']!='owner':raise PermissionError('Gestione account riservata all’amministratore.')
            body=self.read_body()
            if not body or set(body)-{'enabled','password'}:raise ValueError('Modifica account non valida.')
            if 'password' in body:access.change_password(parts[3],body['password'])
            if 'enabled' in body:
                access.enabled(parts[3],body['enabled'])
                if not body['enabled']:self.server.workspaces.deactivate(parts[3])
            return self.json({'ok':True})
        if path=='/api/auth/password' and method=='POST':
            body=self.read_body()
            with access.connect() as db:row=db.execute('SELECT password FROM users WHERE id=?',(identity['id'],)).fetchone()
            old=body.get('old_password','')
            if not isinstance(old,str) or len(old)>256 or not row or not password_matches(old,row['password']):raise PermissionError('Password attuale non valida.')
            access.change_password(identity['id'],body.get('password'))
            return self.json({'ok':True},headers={'Set-Cookie':access.cookie('',secure)})
        if path=='/api/auth/keys':
            if method=='GET':return self.json({'keys':access.keys(identity)})
            if method=='POST':return self.json(access.create_key(identity,self.read_body()),201)
        if len(parts)==4 and parts[:3]==['api','auth','keys'] and method=='DELETE':
            self.read_body();access.revoke_key(identity,parts[3]);return self.json({'ok':True})
        return self.json({'error':'Operazione non trovata.'},404)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8787)
    parser.add_argument("--data", type=Path)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    app = Service(ROOT, args.data)
    try:
        server.app = app
        server.access=Access(app.data)
        server.workspaces=Workspaces(app)
        server.network = TailscaleAccess(server.server_port)
        network = server.network.refresh()
        LOG.info('Tailscale: %s', network.get('url') or network['message'])
        server.daemon_threads = True
        LOG.info("H3-Chat %s pronto: http://127.0.0.1:%s", __version__, args.port)
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        LOG.info("Arresto di H3-Chat e dei motori…")
        if getattr(server,'workspaces',None):server.workspaces.close()
        app.close()
        server.server_close()
        LOG.info("H3-Chat arrestato.")


if __name__ == "__main__":
    main()

"""Loopback-only HTTP host for H3-Chat. No Python packages required."""
from __future__ import annotations
import argparse
import hashlib
import json
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
from h3chat.external_models import browse, suggest
from h3chat.pdf_export import export_pdf
from h3chat.store import uid

ROOT = Path(__file__).resolve().parent


class Handler(BaseHTTPRequestHandler):
    server_version = "H3Chat/0.1"

    @property
    def app(self):
        return self.server.app

    def log_message(self, format, *args):
        pass

    def json(self, value, status=200):
        body = json.dumps(value, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def guard(self):
        allowed = {f"127.0.0.1:{self.server.server_port}", f"localhost:{self.server.server_port}"}
        if self.headers.get("Host") not in allowed:
            raise PermissionError("Host non consentito.")
        origin = self.headers.get("Origin")
        if origin and origin not in {"http://" + host for host in allowed}:
            raise PermissionError("Origine non consentita.")
        if self.headers.get("Sec-Fetch-Site") == "cross-site":
            raise PermissionError("Richiesta da un altro sito non consentita.")
        if self.command in ("POST", "PATCH", "DELETE", "PUT"):
            if not secrets.compare_digest(self.headers.get("X-H3-Token", ""), self.app.token):
                raise PermissionError("Sessione scaduta. Ricarica la pagina.")

    def read_body(self):
        if "application/json" not in self.headers.get("Content-Type", ""):
            raise ValueError("È richiesto un corpo JSON.")
        length = int(self.headers.get("Content-Length", "0"))
        if length < 0 or length > 18 * 1024 * 1024:
            raise ValueError("Richiesta troppo grande.")
        body = json.loads(self.rfile.read(length) or b"{}")
        if not isinstance(body, dict):
            raise ValueError("Il corpo deve essere un oggetto.")
        return body

    def file(self, path):
        if not path.is_file():
            self.json({"error": "File non trovato."}, 404)
            return
        body = path.read_bytes()
        self.send_response(200)
        mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; font-src 'self' data:; connect-src 'self'; object-src 'none'; frame-src 'none'; base-uri 'self'; form-action 'self'")
        self.end_headers()
        self.wfile.write(body)

    def handle_request(self):
        try:
            self.guard()
            path = urllib.parse.unquote(urllib.parse.urlsplit(self.path).path)
            parts = [p for p in path.split("/") if p]
            method = self.command
            if method == "GET":
                if path == "/api/health":
                    return self.json({"app": "h3-chat", "version": __version__, "instance": hashlib.sha256(str(ROOT).encode()).hexdigest()[:16]})
                if path == "/api/state":
                    return self.json(self.app.state())
                if path == "/api/hardware":
                    return self.json(self.app.hardware())
                if len(parts) == 3 and parts[:2] == ["api", "chats"]:
                    return self.json(self.app.store.chat(parts[2]))
                if len(parts) == 3 and parts[:2] == ["api", "canvas"]:
                    self.app.store.chat(parts[2])
                    canvas = self.app.store.one("SELECT * FROM canvases WHERE chat_id=?", (parts[2],))
                    if canvas:
                        canvas["media"] = json.loads(canvas["media"])
                    return self.json(canvas or {"title": "Canvas", "content": "", "media": []})
                if path == "/":
                    return self.file(ROOT / "static/index.html")
                if path.startswith("/static/"):
                    return self.file(safe_join(ROOT / "static", path[len("/static/"):]))
                if path.startswith("/exports/"):
                    relative = path[len("/exports/"):]
                    if len(parts) != 3 or parts[-1] != "document.pdf":
                        raise PermissionError("File non disponibile.")
                    return self.file(safe_join(self.app.data / "exports", relative))
                if path.startswith("/media/"):
                    relative = path[len("/media/"):]
                    if not relative.startswith(("uploads/", "outputs/")) or Path(relative).suffix not in (".png", ".jpg"):
                        raise PermissionError("File non disponibile.")
                    return self.file(safe_join(self.app.data, relative))
                return self.json({"error": "Risorsa non trovata."}, 404)
            body = self.read_body()
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
                return self.json(export_pdf(ROOT, self.app.data, body))
            if path == "/api/memory/release" and method == "POST":
                return self.json(self.app.release_memory())
            if path == "/api/assess" and method == "POST":
                return self.json(self.app.assess(body))
            if path == "/api/settings" and method == "POST":
                return self.json(self.app.save_settings(body))
            if path == "/api/uploads" and method == "POST":
                return self.json(self.app.upload(body), 201)
            if path == "/api/chats" and method == "POST":
                return self.json(self.app.store.create_chat(collection_id=body.get("collection_id")), 201)
            if path == "/api/downloads" and method == "POST":
                return self.json({"id": self.app.downloads.start(body["id"], body.get("kind", "model"))}, 202)
            if len(parts) == 4 and parts[:2] == ["api", "downloads"] and parts[3] == "cancel":
                self.app.downloads.cancel(parts[2])
                return self.json({"ok": True})
            if len(parts) == 4 and parts[:2] == ["api", "jobs"] and parts[3] == "cancel":
                return self.json(self.app.cancel(parts[2]))
            if len(parts) == 4 and parts[:2] == ["api", "chats"] and parts[3] == "messages" and method == "POST":
                return self.json(self.app.send(parts[2], body), 202)
            if len(parts) == 3 and parts[:2] == ["api", "chats"]:
                chat_id = parts[2]
                if method == "DELETE":
                    return self.json(self.app.delete_chat(chat_id))
                if method == "PATCH":
                    allowed = {"title", "pinned", "archived", "collection_id"}
                    if not body or set(body) - allowed:
                        raise ValueError("Modifica chat non valida.")
                    for key, value in body.items():
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
                media = self.app.validate_media(body.get("media", []))
                self.app.store.execute("INSERT OR REPLACE INTO canvases VALUES (?,?,?,?,?)", (parts[2], title, content, json.dumps(media), time.time()))
                return self.json({"ok": True})
            if path == "/api/shutdown" and method == "POST":
                self.json({"ok": True})
                threading.Thread(target=self.server.shutdown, daemon=True).start()
                return
            self.json({"error": "Operazione non trovata."}, 404)
        except PermissionError as exc:
            self.json({"error": str(exc)}, 403)
        except (ValueError, KeyError, TypeError, sqlite3.IntegrityError) as exc:
            self.json({"error": str(exc)}, 400)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            pass
        except Exception as exc:
            self.json({"error": str(exc)}, 500)

    do_GET = do_POST = do_PATCH = do_DELETE = do_PUT = handle_request


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8787)
    parser.add_argument("--data", type=Path)
    args = parser.parse_args()
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    app = Service(ROOT, args.data)
    try:
        server.app = app
        server.daemon_threads = True
        print(f"H3-Chat http://127.0.0.1:{args.port}", flush=True)
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        app.close()


if __name__ == "__main__":
    main()

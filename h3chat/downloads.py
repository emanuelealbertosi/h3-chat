from __future__ import annotations

import hashlib
import json
import os
import re
import threading
import time
import urllib.error
import urllib.request
import zipfile
from pathlib import Path
from urllib.parse import urlparse


class Cancelled(Exception):
    pass


def safe_join(root, relative):
    root = Path(root).resolve()
    target = (root / relative).resolve()
    if target == root or not target.is_relative_to(root):
        raise ValueError("Percorso non consentito.")
    return target


def request(url, headers=None):
    if urlparse(url).scheme != "https":
        raise ValueError("Il download richiede HTTPS.")
    return urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "H3-Chat/0.1"} | (headers or {})), timeout=30)


def download(url, target, sha256, size, cancel, progress):
    """Resume into a .part; only publish verified, complete files."""
    target = Path(target)
    if not re.fullmatch(r"[0-9a-f]{64}", sha256 or "") or size <= 0:
        raise ValueError("Manifest privo di dimensione o SHA-256 verificabile.")
    target.parent.mkdir(parents=True, exist_ok=True)
    part = target.with_name(target.name + ".part")
    if target.exists():
        if target.stat().st_size == size and file_hash(target, cancel) == sha256:
            return
        raise ValueError(f"File esistente non valido: {target.name}. Rimuovilo prima di riscaricarlo.")
    offset = part.stat().st_size if part.exists() else 0
    if offset > size:
        part.unlink()
        offset = 0
    if offset < size:
        with request(url, {"Range": f"bytes={offset}-"} if offset else {}) as response:
            if offset and response.status == 206:
                if not response.headers.get("Content-Range", "").startswith(f"bytes {offset}-"):
                    raise ValueError("Il server ha restituito un intervallo errato.")
            elif response.status == 200:
                offset = 0
            else:
                raise ValueError("Risposta di download inattesa.")
            with part.open("ab" if offset else "wb") as output:
                while block := response.read(1024 * 1024):
                    if cancel.is_set():
                        raise Cancelled()
                    offset += len(block)
                    if offset > size:
                        raise ValueError("Download più grande del manifest.")
                    output.write(block)
                    progress(offset, size)
    if offset != size:
        raise ValueError("Download incompleto. Premi Riprendi per continuare.")
    progress(size, size)
    if file_hash(part, cancel) != sha256:
        part.unlink()
        raise ValueError("SHA-256 diverso dal manifest. Il file non è stato installato.")
    os.replace(part, target)


def file_hash(path, cancel=None):
    digest = hashlib.sha256()
    with open(path, "rb") as source:
        while block := source.read(4 * 1024 * 1024):
            if cancel is not None and cancel.is_set():
                raise Cancelled()
            digest.update(block)
    return digest.hexdigest()


def extract_zip(archive, destination):
    """Reject traversal and symlinks before extracting any member."""
    with zipfile.ZipFile(archive) as bundle:
        for item in bundle.infolist():
            safe_join(destination, item.filename)
            if (item.external_attr >> 16) & 0o170000 == 0o120000:
                raise ValueError("Link simbolico non consentito nel runtime.")
        bundle.extractall(destination)


class Downloads:
    def __init__(self, root, catalog, runtimes):
        self.root, self.catalog, self.runtimes = Path(root), catalog, runtimes
        self.lock = threading.Lock()
        self.tasks = {}

    def snapshot(self):
        with self.lock:
            return [{k: v for k, v in task.items() if k != "cancel"} for task in self.tasks.values()]

    def start(self, key, kind="model"):
        with self.lock:
            if any(t["status"] == "running" for t in self.tasks.values()):
                raise ValueError("È già in corso un download. Attendi o interrompilo.")
            if kind == "model":
                model = self.catalog[key]
                files = model["files"]
            elif kind == "runtime" and key in self.runtimes:
                files = self.runtimes[key]["files"]
            else:
                raise ValueError("Download sconosciuto.")
            task = {"id": key, "kind": kind, "status": "running", "file": "", "received": 0, "total": 0, "error": "", "cancel": threading.Event()}
            self.tasks[key] = task
        threading.Thread(target=self._run, args=(task, files), daemon=True).start()
        return key

    def _run(self, task, files):
        try:
            for entry in files:
                with self.lock:
                    task.update(file=entry["path"], received=0, total=entry["size"])
                target = safe_join(self.root, entry["path"])
                def progress(current, total):
                    with self.lock:
                        task.update(received=current, total=total)
                download(entry["url"], target, entry["sha256"], entry["size"], task["cancel"], progress)
                if entry.get("extract_to"):
                    extract_zip(target, safe_join(self.root, entry["extract_to"]))
            # Marker is only written after every model component has been verified.
            if task["kind"] == "model":
                marker = self.root / "models" / (task["id"] + ".ready.json")
                marker.parent.mkdir(parents=True, exist_ok=True)
                marker.write_text(json.dumps({"files": [{"path": e["path"], "size": e["size"], "sha256": e["sha256"]} for e in files]}), encoding="utf-8")
            with self.lock:
                task["status"] = "done"
        except Cancelled:
            with self.lock:
                task["status"] = "cancelled"
        except Exception as exc:
            with self.lock:
                task.update(status="failed", error=str(exc))

    def cancel(self, key):
        with self.lock:
            if key in self.tasks:
                self.tasks[key]["cancel"].set()


def model_ready(root, model):
    try:
        marker = json.loads((Path(root) / "models" / (model["id"] + ".ready.json")).read_text(encoding="utf-8"))
        expected = [{"path": e["path"], "size": e["size"], "sha256": e["sha256"]} for e in model["files"]]
        return marker["files"] == expected and all(safe_join(root, e["path"]).stat().st_size == e["size"] for e in model["files"])
    except (OSError, ValueError, KeyError):
        return False

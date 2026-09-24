"""Fetch and verify the exact upstream inference source used by the worker."""
import hashlib
import json
from pathlib import Path
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
REVISION = '3b4c0b0e457cf0a51cf3038e0a6750d8f96ce251'
SHA256 = '4c137bc8976866bed10f9fcb7e8ad0e489c40a1acf76fca2f7140bd0a106cde8'
URL = 'https://codeload.github.com/Comfy-Org/ComfyUI/zip/' + REVISION


def main():
    runtime = ROOT / 'runtime/vision'
    destination = runtime / 'core'
    if destination.exists():
        raise ValueError('Build in a clean checkout: runtime/vision/core already exists.')
    archive = ROOT / 'work/vision-core.zip'
    archive.parent.mkdir(parents=True, exist_ok=True)
    urllib.request.urlretrieve(URL, archive)
    if hashlib.sha256(archive.read_bytes()).hexdigest() != SHA256:
        raise ValueError('Upstream core SHA-256 mismatch.')
    prefix = 'ComfyUI-' + REVISION + '/'
    with zipfile.ZipFile(archive) as source:
        entries = []
        for entry in source.infolist():
            if not entry.filename.startswith(prefix):
                raise ValueError('Unexpected upstream archive layout.')
            relative = entry.filename[len(prefix):]
            if not relative or entry.is_dir():
                continue
            target = (destination / relative).resolve()
            if not target.is_relative_to(destination.resolve()) or (entry.external_attr >> 16) & 0o170000 == 0o120000:
                raise ValueError('Unsafe upstream archive entry.')
            entries.append((entry, target))
        for entry, target in entries:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(source.read(entry))
    (runtime / 'SOURCES.json').write_text(json.dumps({
        'project':'ComfyUI', 'revision':REVISION, 'url':URL,
        'sha256':SHA256, 'license':'GPL-3.0', 'modified':False,
    }, indent=2) + '\n', encoding='utf-8')
    print('Verified upstream core:', REVISION)


if __name__ == '__main__':
    main()

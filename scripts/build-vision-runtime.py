"""Build the optional offline runtime from an isolated, pinned wheel environment.

Run with that environment's Python (3.13, Windows x64). Only distribution RECORD
files are copied; no .pth, scripts, caches, user configuration or model weights.
Every recorded file hash is checked before copying. See docs/vision-engine.md.
"""
import base64
import hashlib
import importlib.metadata as metadata
import json
from pathlib import Path
import shutil
from packaging.requirements import Requirement

ROOT = Path(__file__).resolve().parents[1]
PACKAGES = 'torch torchvision torchsde numpy einops transformers tokenizers sentencepiece safetensors pyyaml Pillow scipy tqdm psutil comfy-kitchen comfy-aimdo requests pydantic aiohttp blake3 av alembic'.split()


def main():
    target = ROOT / 'runtime/vision/packages'
    target.mkdir(parents=True, exist_ok=True)
    pending, seen, versions = list(PACKAGES), set(), {}
    while pending:
        dist = metadata.distribution(pending.pop(0))
        name = dist.metadata['Name'].lower().replace('_', '-')
        if name in seen:
            continue
        seen.add(name)
        versions[name] = dist.version
        for value in dist.requires or []:
            requirement = Requirement(value)
            if requirement.marker is None or requirement.marker.evaluate():
                pending.append(requirement.name)
        for entry in dist.files or []:
            relative = Path(str(entry))
            if relative.is_absolute() or '..' in relative.parts or '__pycache__' in relative.parts or relative.suffix in ('.pyc', '.pth'):
                continue
            # Installer provenance can contain a local build path. It is not runtime code.
            if relative.name in ('direct_url.json', 'REQUESTED'):
                continue
            source = entry.locate()
            if not source.is_file():
                raise ValueError(f'Missing wheel file: {entry}')
            if entry.hash:
                with source.open('rb') as stream:
                    digest = hashlib.file_digest(stream, entry.hash.mode).digest()
                actual = base64.urlsafe_b64encode(digest).rstrip(b'=').decode()
                if actual != entry.hash.value:
                    raise ValueError(f'Modified wheel file: {entry}')
            destination = target / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
        print(name, dist.version, flush=True)
    (ROOT / 'runtime/vision/packages.json').write_text(json.dumps(versions, indent=2), encoding='utf-8')
    (ROOT / 'scripts/vision-requirements.txt').write_text('\n'.join(f'{k}=={v}' for k,v in sorted(versions.items()))+'\n', encoding='utf-8')


if __name__ == '__main__':
    main()

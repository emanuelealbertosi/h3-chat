"""Copy only small pipeline assets and the unchanged original VAE, offline."""
import json,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
report=json.loads((ROOT/'work/fibo2-research-2026-10-20/int8-download.json').read_text())
if not report.get('ready_weights'):raise RuntimeError('Completare prima il download INT8 verificato.')
original=Path('F:/sd-webui-forge-neo/models/Stable-diffusion/Fibo-2.0-dev')
target=Path(report['path'])
names=['model_index.json','transformer/config.json','text_encoder/config.json','vae/config.json',
       'vae/diffusion_pytorch_model.safetensors','scheduler/scheduler_config.json']
for folder in ('fonts','processor'):
    names.extend(str(p.relative_to(original)).replace('\\','/') for p in (original/folder).rglob('*') if p.is_file())
for name in names:
    source=original/name;destination=target/name;destination.parent.mkdir(parents=True,exist_ok=True)
    if destination.exists():
        if source.stat().st_size!=destination.stat().st_size:raise RuntimeError('Asset esistente diverso: '+name)
    else:shutil.copy2(source,destination)
(target/'H3-SOURCES.json').write_text(json.dumps({'weights':report,'assets_source':str(original),'copied_assets':names},indent=2),encoding='utf-8')
print('INT8 pipeline assets ready; original BF16 files preserved.')

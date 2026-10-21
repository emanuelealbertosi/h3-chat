"""Explicit pinned, hash-verified public INT8 downloads; preserve BF16 files."""
import hashlib,importlib.util,json,shutil,sys,urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('fibo_download',ROOT/'scripts/download-fibo2.py')
source=importlib.util.module_from_spec(spec);spec.loader.exec_module(source)
REPO='Comfy-Org/Fibo-2.0'
NAMES=('diffusion_models/fibo2_dev_int8_convrot.safetensors',
       'text_encoders/qwen3vl_4b_int8_convrot.safetensors','vae/flux2-vae.safetensors')
folder=ROOT/'work/fibo2-research-2026-10-20'
manifest=folder/'int8-manifest.json'
if manifest.exists():meta=json.loads(manifest.read_text())
else:
    with urllib.request.urlopen('https://huggingface.co/api/models/'+REPO+'?blobs=true',timeout=30) as response:meta=json.load(response)
    manifest.write_text(json.dumps(meta,indent=2),encoding='utf-8')
target=Path('F:/sd-webui-forge-neo/models/Stable-diffusion/Fibo-2.0-Comfy-INT8')
files=[next(x for x in meta['siblings'] if x['rfilename']==name) for name in NAMES]
needed=sum(x['size'] for x in files if not (target/x['rfilename']).is_file())
if shutil.disk_usage(target.parent).free<needed+8*1024**3:raise RuntimeError('Spazio insufficiente per INT8 e margine di 8 GiB.')
checked=[]
for entry in files:
    path=target/entry['rfilename']
    if not path.is_file() or path.stat().st_size!=entry['size']:
        source.fetch('https://huggingface.co/'+REPO+'/resolve/'+meta['sha']+'/'+entry['rfilename'],path,entry['size'],None)
    with path.open('rb') as stream:actual=hashlib.file_digest(stream,'sha256').hexdigest()
    if actual!=entry['lfs']['sha256']:raise RuntimeError('SHA256 errato: '+entry['rfilename'])
    checked.append({'path':str(path),'sha256':actual,'bytes':entry['size']});print('Verified '+entry['rfilename'],flush=True)
report={'repository':REPO,'revision':meta['sha'],'path':str(target),'verified_files':checked,'ready_weights':True}
(folder/'int8-download.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print('FIBO INT8 download verified; original BF16 files preserved.',flush=True)

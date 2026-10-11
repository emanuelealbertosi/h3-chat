"""Install an isolated score-reader runtime; model paths are selected separately."""
import hashlib,json,os,subprocess,sys,urllib.request,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
PYTHON_SHA='009d6bf7e3b2ddca3d784fa09f90fe54336d5b60f0e0f305c37f400bf83cfd3b'

def get(url,path,expected=None):
    part=path.with_suffix('.partial');path.parent.mkdir(parents=True,exist_ok=True)
    with urllib.request.urlopen(url,timeout=120) as src,part.open('wb') as out:
        while block:=src.read(4*1024*1024):out.write(block)
    if expected and hashlib.sha256(part.read_bytes()).hexdigest()!=expected:raise RuntimeError('Checksum del runtime spartiti non valido.')
    part.replace(path)

def main():
    target=ROOT/'runtime/remix/transcription'
    if (target/'ready.json').is_file():print('Lettore spartiti già installato.');return
    target.mkdir(parents=True,exist_ok=True)
    cache=ROOT/'runtime/remix/install-cache';cache.mkdir(parents=True,exist_ok=True)
    archive=cache/'python311.zip'
    print('Installazione Python privato per SheetSage2',flush=True)
    get('https://www.python.org/ftp/python/3.11.9/python-3.11.9-embed-amd64.zip',archive,PYTHON_SHA)
    with zipfile.ZipFile(archive) as bundle:bundle.extractall(target)
    (target/'python311._pth').write_text('python311.zip\n.\nLib/site-packages\nimport site\n',encoding='utf-8')
    # Bootstrap a pinned pip wheel using the package index's SHA-256 metadata.
    with urllib.request.urlopen('https://pypi.org/pypi/pip/24.3.1/json',timeout=60) as r:metadata=json.load(r)
    wheel=next(x for x in metadata['urls'] if x['filename'].endswith('.whl'))
    pip=cache/wheel['filename'];get(wheel['url'],pip,wheel['digests']['sha256'])
    with zipfile.ZipFile(pip) as bundle:bundle.extractall(target/'Lib/site-packages')
    python=target/'python.exe';env=os.environ.copy();env['PYTHONUTF8']='1'
    def install(args):subprocess.run([str(python),'-m','pip','install','--disable-pip-version-check','--no-cache-dir',*args],env=env,check=True)
    print('Installazione Torch CUDA · utilizzabile anche su CPU',flush=True)
    install(['torch==2.8.0+cu128','torchaudio==2.8.0+cu128','--index-url','https://download.pytorch.org/whl/cu128'])
    install(['transformers==4.45.2','huggingface-hub==0.36.0','safetensors==0.5.3','numpy==1.24.3','scipy==1.13.1','mir_eval==0.8.2','pretty_midi==0.2.10','mido==1.3.3','setuptools==78.1.1'])
    subprocess.run([str(python),'-c','import torch,torchaudio,transformers,pretty_midi,mir_eval; print(torch.__version__)'],check=True,env=env)
    (target/'ready.json').write_text(json.dumps({'python':'3.11.9','torch':'2.8.0+cu128','transformers':'4.45.2'}),encoding='utf-8')
    print('Lettore spartiti installato. Seleziona SheetSage2 e MERT nelle impostazioni Remix.',flush=True)

if __name__=='__main__':main()

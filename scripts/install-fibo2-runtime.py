"""Install FIBO's pinned Diffusers overlay without touching shared packages."""
import hashlib,json,os,re,subprocess,sys,urllib.request,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from h3chat.fibo2 import DIFFUSERS_REVISION

def main():
    folder=ROOT/'runtime/fibo2';packages=folder/'packages';packages.mkdir(parents=True,exist_ok=True)
    env=os.environ.copy();env.update(TEMP='F:/H3-TestTmp',TMP='F:/H3-TestTmp',PIP_CACHE_DIR=str(folder/'cache/pip'),CUDA_VISIBLE_DEVICES='')
    dependencies=[];versions={}
    pins={'accelerate':'1.15.0','importlib-metadata':'9.0.1','zipp':'4.1.1','huggingface-hub':'1.32.0'}
    for name,version in pins.items():
        with urllib.request.urlopen('https://pypi.org/pypi/'+name+'/'+version+'/json',timeout=60) as response:value=json.load(response)
        wheel=next(v for v in value['urls'] if v['filename'].endswith('none-any.whl'))
        dependencies.append(wheel['url']);versions[name]=value['info']['version']
    pip=ROOT/'runtime/bootstrap/pip.pyz'
    if not pip.is_file():raise RuntimeError('Bootstrap pip locale non disponibile.')
    archive=folder/('diffusers-'+DIFFUSERS_REVISION+'.zip')
    if not archive.is_file():
        with urllib.request.urlopen(f'https://codeload.github.com/huggingface/diffusers/zip/{DIFFUSERS_REVISION}',timeout=60) as response:archive.write_bytes(response.read())
    # The embedded interpreter has no build-system site-packages. Diffusers is
    # pure Python: install the pinned source tree directly and record metadata.
    with zipfile.ZipFile(archive) as bundle:
        prefix=f'diffusers-{DIFFUSERS_REVISION}/src/'
        for entry in bundle.infolist():
            if not entry.is_dir() and entry.filename.startswith(prefix+'diffusers/'):
                relative=Path(entry.filename[len(prefix):])
                if '..' in relative.parts:raise RuntimeError('Percorso archivio non valido.')
                target=packages/relative;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(bundle.read(entry))
    version=re.search(r'__version__\s*=\s*"([^"]+)"',(packages/'diffusers/__init__.py').read_text()).group(1)
    metadata=packages/f'diffusers-{version}.dist-info';metadata.mkdir(exist_ok=True)
    (metadata/'METADATA').write_text('Metadata-Version: 2.1\nName: diffusers\nVersion: '+version+'\n')
    subprocess.run([str(ROOT/'runtime/python/python.exe'),str(pip),'install','--upgrade','--no-deps','--no-cache-dir','--disable-pip-version-check',
        '--target',str(packages),*dependencies],env=env,check=True)
    # Import is CPU-only: no model loaded, no CUDA context initialized.
    code='import sys;sys.path[:0]='+repr([str(packages),str(ROOT/'runtime/vision/packages')])+';from diffusers import BriaFibo2Pipeline;import torch;print("FIBO pipeline import OK; CUDA initialized:",torch.cuda.is_initialized())'
    subprocess.run([str(ROOT/'runtime/python/python.exe'),'-X','utf8','-c',code],env=env,check=True)
    report={'diffusers_revision':DIFFUSERS_REVISION,'source_archive_sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),'dependencies':versions,'gpu_test':False}
    (folder/'ready.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report))
if __name__=='__main__':main()

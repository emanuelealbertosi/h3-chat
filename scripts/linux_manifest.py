"""Resolve Linux wheels at build time; installers use only pinned URLs/hashes."""
import json
from pathlib import Path
import subprocess
import sys
import urllib.parse
import urllib.request
import zipfile

ROOT=Path(__file__).resolve().parents[1]


def wheels(stage,name,requirements,destination,*,constraints=None,index=None,python=None):
    folder=ROOT/'build/linux-locks';folder.mkdir(parents=True,exist_ok=True)
    report=folder/(name+'.json');python=python or Path(stage)/'runtime/python/bin/python3'
    args=[str(python),'-m','pip','install','--dry-run','--ignore-installed','--only-binary=:all:','--report',str(report),*requirements]
    if constraints:args+=['--constraint',str(constraints)]
    if index:args+=['--extra-index-url',index]
    subprocess.run(args,check=True)
    result=[]
    for item in json.loads(report.read_text())['install']:
        info=item['download_info'];url=info['url'];digest=info['archive_info']['hashes']['sha256'];filename=urllib.parse.unquote(urllib.parse.urlsplit(url).path.rsplit('/',1)[-1])
        if not filename.endswith('.whl') or 'win_amd64' in filename or 'macosx' in filename:raise ValueError('Non-Linux wheel in resolved manifest: '+filename)
        with urllib.request.urlopen(urllib.request.Request(url,method='HEAD'),timeout=60) as response:size=int(response.headers['Content-Length'])
        result.append({'url':url,'size':size,'sha256':digest,'path':'runtime/downloads/linux/'+filename,'extract_to':destination})
    return {'platform':'linux','files':result}


def build(stage):
    stage=Path(stage)
    upstream=json.loads((ROOT/'runtimes.json').read_text());values={key:{'platform':'linux','bundled':True,'files':[]} for key in ('cpu','vulkan','cuda','music_cpu','music_cuda','tools_documents','tools_lab','tools_latex','tools_asr')}
    vision=ROOT/'scripts/vision-requirements.txt';index='https://download.pytorch.org/whl/cu130'
    values['vision']=wheels(stage,'vision',['-r',str(vision),'sageattention==1.0.6'],'runtime/vision/packages',index=index)
    # The original source ZIP is verified and extracted through a fixed member
    # allowlist, preserving exactly the revision used by Windows workers.
    sys.path.insert(0,str(ROOT))
    import runpy
    core=runpy.run_path(str(ROOT/'scripts/prepare-vision-core.py'),run_name='h3_manifest_source')
    archive=ROOT/'build/linux-locks/comfy-core.zip'
    if not archive.exists():urllib.request.urlretrieve(core['URL'],archive)
    import hashlib
    if hashlib.file_digest(archive.open('rb'),'sha256').hexdigest()!=core['SHA256']:raise ValueError('Comfy source checksum mismatch.')
    prefix='ComfyUI-'+core['REVISION']+'/'
    with zipfile.ZipFile(archive) as bundle:
        members={v.filename:v.filename[len(prefix):] for v in bundle.infolist() if not v.is_dir() and v.filename.startswith(prefix)}
    values['vision']['files'].append({'url':core['URL'],'size':archive.stat().st_size,'sha256':core['SHA256'],'path':'runtime/downloads/linux/comfy-core.zip','extract_to':'runtime/vision/core','extract_members':members})
    values['voice']=wheels(stage,'voice',['accelerate==1.14.0','bitsandbytes==0.49.2'],'runtime/voice/packages',constraints=vision,index=index)
    values['embeddinggemma2']=wheels(stage,'embeddinggemma2',['torch==2.10.0+cpu','transformers==5.14.1','sentencepiece==0.2.2','safetensors==0.8.0'],'runtime/embeddinggemma2/packages',index='https://download.pytorch.org/whl/cpu')
    for entry in values['embeddinggemma2']['files']:
        if entry['path'].rsplit('/',1)[-1].startswith('torch-'):entry['extract_to']='runtime/embeddinggemma2/cpu'
    values['veda']=dict(upstream['veda'],platform='linux')
    values['remix_score']=wheels(stage,'remix_score',['torch==2.8.0+cu128','torchaudio==2.8.0+cu128','transformers==4.45.2','huggingface-hub==0.36.0','safetensors==0.5.3','numpy==1.24.3','scipy==1.13.1','mir_eval==0.8.2','mido==1.3.3','setuptools==78.1.1','six==1.17.0'],
        'runtime/remix/transcription/Lib/site-packages',index='https://download.pytorch.org/whl/cu128',python=stage/'runtime/remix/transcription/python.exe')
    (stage/'runtimes.json').write_text(json.dumps(values,indent=2),encoding='utf8')
    (stage/'remix-runtimes.json').write_text('{}',encoding='utf8')
    upscale={'upscale_rtx':wheels(stage,'upscale_rtx',['nvidia-vfx==0.2.0.0'],'runtime/upscale/packages',constraints=vision,index='https://pypi.nvidia.com')}
    (stage/'upscale-runtimes.json').write_text(json.dumps(upscale,indent=2),encoding='utf8')
    values.update(upscale)
    (stage/'runtimes.json').write_text(json.dumps(values,indent=2),encoding='utf8')
    return values


if __name__=='__main__':build(sys.argv[1])

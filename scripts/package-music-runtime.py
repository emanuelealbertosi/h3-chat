"""Package private workers; NVIDIA redistributables stay pinned to their official URLs."""
import hashlib,json,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
VERSION='0.8.0'
manifest=json.loads((ROOT/'runtimes.json').read_text())
crt={'msvcp140.dll','vcruntime140.dll','vcruntime140_1.dll','vcomp140.dll'}
for backend in ('cpu','cuda'):
 folder=ROOT/'runtime/music'/backend
 files=[p for p in folder.iterdir() if p.name=='h3-music-worker.exe' or p.name in crt or (p.suffix in ('.txt','.json') and not p.name.startswith(('cuda_cudart','libcublas')))]
 assert {p.name for p in files}>={'h3-music-worker.exe'}|crt
 out=ROOT/'dist'/f'H3-Chat-music-{backend}-{VERSION}-windows-x64.zip';out.parent.mkdir(exist_ok=True)
 with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as bundle:
  for p in sorted(files):bundle.write(p,p.name)
 digest=hashlib.sha256(out.read_bytes()).hexdigest()
 out.with_suffix('.zip.sha256').write_text(digest+'  '+out.name+'\n')
 entry={'path':'runtime/archives/'+out.name,'url':f'https://github.com/emanuelealbertosi/h3-chat/releases/download/v{VERSION}/'+out.name,'size':out.stat().st_size,'sha256':digest,'extract_to':'runtime/music/'+backend}
 manifest['music_'+backend]={'files':[entry]}
 print(out.name,out.stat().st_size,digest)
manifest['music_cuda']['files'] += [
 {'path':'runtime/archives/cuda_cudart-windows-x86_64-12.8.90-archive.zip','url':'https://developer.download.nvidia.com/compute/cuda/redist/cuda_cudart/windows-x86_64/cuda_cudart-windows-x86_64-12.8.90-archive.zip','size':3037735,'sha256':'4a39058fd8519444a81cfc7ae055d136f48d1a31ffa41ae255b35b2edd61e13b','extract_to':'runtime/music/cuda','extract_members':{'cuda_cudart-windows-x86_64-12.8.90-archive/bin/cudart64_12.dll':'cudart64_12.dll','cuda_cudart-windows-x86_64-12.8.90-archive/LICENSE':'cuda_cudart-LICENSE.txt'}},
 {'path':'runtime/archives/libcublas-windows-x86_64-12.8.4.1-archive.zip','url':'https://developer.download.nvidia.com/compute/cuda/redist/libcublas/windows-x86_64/libcublas-windows-x86_64-12.8.4.1-archive.zip','size':563660944,'sha256':'57a470112cec7e112c95253dde8b3c7184d795dbd92b0bde77a4cb7f8c94c8aa','extract_to':'runtime/music/cuda','extract_members':{'libcublas-windows-x86_64-12.8.4.1-archive/bin/cublas64_12.dll':'cublas64_12.dll','libcublas-windows-x86_64-12.8.4.1-archive/bin/cublasLt64_12.dll':'cublasLt64_12.dll','libcublas-windows-x86_64-12.8.4.1-archive/LICENSE':'libcublas-LICENSE.txt'}}]
(ROOT/'runtimes.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')

"""Copy the locally verified engine and CUDA runtime, without loading any model/GPU."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from h3chat.llm_acceleration import FOLDER, RUNTIME_FILES

EXPECTED={
 'ggml-base.dll':'C1EE72275D394BE9CCD624F573BEDCC13A8F4F985F35BD572D4E5C68AC358959',
 'ggml-cpu.dll':'A59D69CE1B2132DCF872097258CBE28748454D68A13B0C713053B4812DEE13A5',
 'ggml-cuda.dll':'A389A67896B34C89B04AED3339800C31BEB409D75CDE8F681DB21C64014239C7',
 'ggml.dll':'0C98DE5E289A963E5C86C2ABF02BDEF1398357B750D55C49C5461993D6321922',
 'llama-common.dll':'0BBDD7ABF2CA57C54459DC316D6171B78E5A681A876278DAD8129E5136AD30BE',
 'llama-server-impl.dll':'A486AB41142010970ACE190241A65E0091B3C41FB11ADA9EEDFC25A0B8211DE5',
 'llama-server.exe':'9F80A0CF4458FA17B1791CA382394450F06B5E5B18007F80D6CF216728A9FCEF',
 'llama.dll':'48895A9763490CA968DA2DA6D53711BF9089E81AF29B96FDF687333D6627137A',
 'mtmd.dll':'0B29B7A6A1DD9E0FFDD4B28D6FEB7922C2C99CCCD124E13E1DA4CFC5452F3D98'
}


def digest(path):
 with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def main(argv=None):
 p=argparse.ArgumentParser(description=__doc__)
 p.add_argument('--source',type=Path,required=True,help='Directory containing the exact verified compiled engine.')
 p.add_argument('--cuda',type=Path,required=True,help='Existing CUDA 12.8 Toolkit directory containing bin and original licenses.')
 p.add_argument('--license',type=Path,required=True,help='Original llama.cpp LICENSE matching this engine build.')
 p.add_argument('--system32',type=Path,default=Path(os.environ.get('WINDIR','C:/Windows'))/'System32',help='Microsoft CRT source directory.')
 args=p.parse_args(argv)
 for key in ('source','cuda','license','system32'):setattr(args,key,getattr(args,key).expanduser().resolve())
 target=ROOT/FOLDER
 sources={name:args.source/name for name in EXPECTED}
 sources.update({name:args.cuda/'bin'/name for name in ('cublas64_12.dll','cublasLt64_12.dll','cudart64_12.dll')})
 sources.update({name:args.system32/name for name in ('vcomp140.dll','msvcp140.dll','vcruntime140.dll','vcruntime140_1.dll')})
 if set(sources)!=set(RUNTIME_FILES):raise RuntimeError('Incomplete runtime definition')
 # Validate before touching the installation; never overwrite a different/live build.
 hashes={name:digest(path) for name,path in sources.items()}
 for name,expected in EXPECTED.items():
  if hashes[name].upper()!=expected:raise RuntimeError('Unverified source engine: '+name)
 for name in sources:
  destination=target/name
  if destination.exists() and digest(destination)!=hashes[name]:
   raise RuntimeError('Different installed library; preserving it: '+str(destination))
 notices={'llama-LICENSE.txt':args.license,'CUDA-EULA.txt':args.cuda/'EULA.txt',
          'CUDA-LICENSE.txt':args.cuda/'LICENSE','Microsoft-CRT-NOTICE.txt':ROOT/'native/redist/NOTICE.txt'}
 for path in notices.values():
  if not path.is_file():raise RuntimeError('Missing runtime license: '+str(path))
 target.mkdir(parents=True,exist_ok=True)
 for name,path in sources.items():
  if not (target/name).exists():shutil.copy2(path,target/name)
 for name,path in notices.items():shutil.copy2(path,target/name)
 manifest={'profile':'qwen27-iq3s-mtp2-window8k','source_commit':'555d1ec9daa4564cb06adb39c469acfdcd1d1e93',
           'cuda':'12.8','compiled_sm':[120],'sha256':hashes,
           'sources':{name:str(path) for name,path in sources.items()},
           'modification':'Only llama-common: bounded drafter KV, target full context preserved',
           'process_ownership':'H3-Chat Session; no external service or autostart'}
 (target/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
 print(json.dumps({'installed':str(target),'bytes':sum((target/n).stat().st_size for n in sources),
                   'gpu_used':False,'model_weights_copied':False}),flush=True)


if __name__=='__main__':main()

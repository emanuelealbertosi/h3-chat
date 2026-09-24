"""Package unmodified x64 Microsoft release CRT redistributables for app-local use.

Supply the Microsoft.VC143.CRT directory from the licensed VC Redist distribution.
Do not use debug_nonredist, System32 wholesale, or an application's DLL directory.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import zipfile

ROOT=Path(__file__).resolve().parents[1]
FILES=('concrt140.dll','msvcp140.dll','msvcp140_1.dll','msvcp140_2.dll',
       'msvcp140_atomic_wait.dll','msvcp140_codecvt_ids.dll','vccorlib140.dll',
       'vcruntime140.dll','vcruntime140_1.dll','vcruntime140_threads.dll')
NOTICE='''Microsoft Visual C++ Runtime, x64.
Copyright Microsoft Corporation. All rights reserved.
Unmodified redistributable files from Visual Studio VC Redist.
https://visualstudio.microsoft.com/license-terms/vs2022-cruntime/
https://learn.microsoft.com/cpp/windows/redistributing-visual-cpp-files
These libraries retain their Microsoft license, not the app MIT or worker GPL.
'''


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--redist-dir',type=Path,required=True)
    args=parser.parse_args()
    source=args.redist_dir.resolve()
    if 'debug_nonredist' in source.parts or source.name!='Microsoft.VC143.CRT' or source.parent.name!='x64':
        raise ValueError('Select the x64 Microsoft.VC143.CRT release redistributable directory.')
    destination=ROOT/'runtime/vision/dlls'
    destination.mkdir(parents=True,exist_ok=True)
    for name in FILES:shutil.copy2(source/name,destination/name)
    (destination/'NOTICE.txt').write_text(NOTICE,encoding='utf-8')
    output=ROOT/'dist/H3-Chat-vision-crt-0.7.0-windows-x64.zip'
    output.parent.mkdir(exist_ok=True)
    with zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as archive:
        for name in (*FILES,'NOTICE.txt'):archive.write(destination/name,name)
    sha=hashlib.sha256(output.read_bytes()).hexdigest()
    output.with_suffix('.zip.sha256').write_text(sha+'  '+output.name+'\n',encoding='utf-8')
    path=ROOT/'runtimes.json'
    runtimes=json.loads(path.read_text(encoding='utf-8'))
    files=[f for f in runtimes.get('vision',{}).get('files',[]) if f.get('extract_to')!='runtime/vision/dlls']
    files.append({'path':'runtime/downloads/'+output.name,'extract_to':'runtime/vision/dlls',
        'url':'https://github.com/emanuelealbertosi/h3-chat/releases/download/v0.7.0/'+output.name,
        'size':output.stat().st_size,'sha256':sha})
    runtimes['vision']={'files':files}
    path.write_text(json.dumps(runtimes,indent=2)+'\n',encoding='utf-8')
    print(output,sha)


if __name__=='__main__':main()

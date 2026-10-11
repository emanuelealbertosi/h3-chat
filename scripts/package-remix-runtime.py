"""Package the private prebuilt audio.cpp CLI and FFmpeg, without model weights."""
import hashlib,json,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
VERSION='0.18.47'
def main():
    result={};out=ROOT/'dist';out.mkdir(exist_ok=True)
    for key,folder in [('remix_media',ROOT/'runtime/remix'),('remix_cpu',ROOT/'runtime/remix/cpu'),('remix_cuda',ROOT/'runtime/remix/cuda')]:
        files=[p for p in folder.iterdir() if p.is_file() and (p.name=='ffmpeg.exe' if key=='remix_media' else p.suffix in ('.exe','.dll','.txt','.json'))]
        if key=='remix_media':files+=list((ROOT/'licenses').glob('remix-*'))
        archive=out/f'H3-Chat-{key}-{VERSION}-windows-x64.zip'
        with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
            for p in sorted(files):z.write(p,p.name)
        sha=hashlib.sha256(archive.read_bytes()).hexdigest();archive.with_suffix('.zip.sha256').write_text(sha+'  '+archive.name+'\n')
        result[key]={'files':[{'path':'runtime/archives/'+archive.name,'url':f'https://github.com/emanuelealbertosi/h3-chat/releases/download/v{VERSION}/'+archive.name,'size':archive.stat().st_size,'sha256':sha,'extract_to':folder.relative_to(ROOT).as_posix()}]}
        print(archive.name,archive.stat().st_size,sha,flush=True)
    shared=json.loads((ROOT/'runtimes.json').read_text(encoding='utf-8'))['music_cuda']['files'][1:]
    result['remix_cuda']['files']+=shared
    result['remix_score']={'files':[]}
    (ROOT/'remix-runtimes.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
if __name__=='__main__':main()

"""Build a self-contained portable Apple Silicon distribution on an Apple runner."""
import hashlib,json,os,platform,plistlib,shutil,stat,subprocess,sys,tarfile,urllib.request,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from h3chat import __version__


def run(args,**kw):subprocess.run([str(v) for v in args],check=True,**kw)


def archive(source,target,cache):
    cache.mkdir(parents=True,exist_ok=True);path=cache/source['url'].rsplit('/',1)[-1]
    if not path.exists():
        with urllib.request.urlopen(source['url'],timeout=120) as response,path.open('wb') as out:shutil.copyfileobj(response,out)
    if path.stat().st_size!=source['size'] or hashlib.sha256(path.read_bytes()).hexdigest()!=source['sha256']:raise ValueError('Archive checksum mismatch: '+path.name)
    target.mkdir(parents=True,exist_ok=True)
    with tarfile.open(path) as package:package.extractall(target,filter='data')


def build():
    if sys.platform!='darwin' or platform.machine()!='arm64':raise ValueError('Run this build on native Apple Silicon macOS.')
    source=json.loads((ROOT/'scripts/macos-sources.json').read_text())
    stage=ROOT/'build/macos/H3-Chat';stage.mkdir(parents=True,exist_ok=True)
    # Deliberate allowlist: no production data, weights, Windows binaries or private handoff.
    from scripts.package import release_file
    for name in ('h3chat','static','ui','licenses','skills/h3','docs'):
        for path in (ROOT/name).rglob('*'):
            if path.is_file() and release_file(path,ROOT) and path.suffix not in ('.exe','.dll','.pyd'):
                dest=stage/path.relative_to(ROOT);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,dest)
    for name in ('app.py','launcher.py','catalog.json','runtimes.json','tools-models.json','upscale-runtimes.json','remix-runtimes.json','README.md','LICENSE','NOTICE'):
        shutil.copy2(ROOT/name,stage/name)
    (stage/'native').mkdir(exist_ok=True)
    for path in (ROOT/'native').glob('*.py'):shutil.copy2(path,stage/'native'/path.name)
    (stage/'scripts').mkdir(exist_ok=True)
    for name in ('macos-requirements.txt','macos-sources.json','reset_admin_password.py','convert-glp-lora.py'):shutil.copy2(ROOT/'scripts'/name,stage/'scripts'/name)
    cache=ROOT/'build/macos-downloads';unpack=ROOT/'build/macos-unpack'
    archive(source['python'],unpack/'python',cache)
    shutil.copytree(unpack/'python/python',stage/'runtime/python',symlinks=True,dirs_exist_ok=True)
    archive(source['llama'],unpack/'llama',cache)
    executable=next((unpack/'llama').rglob('llama-server'))
    shutil.copytree(executable.parent,stage/'runtime/cpu/llama',symlinks=True,dirs_exist_ok=True)
    (stage/'runtime/metal').mkdir(exist_ok=True)
    (stage/'runtime/metal/llama').symlink_to('../cpu/llama',target_is_directory=True)
    python=stage/'runtime/python/bin/python3'
    run([python,'-m','pip','install','--only-binary=:all:','--no-compile','--target',stage/'runtime/tools/documents','-r',ROOT/'scripts/macos-requirements.txt'])
    (stage/'runtime/remix').mkdir(exist_ok=True)
    ffmpeg=next((stage/'runtime/tools/documents/imageio_ffmpeg/binaries').glob('ffmpeg-macos-*'))
    (stage/'runtime/remix/ffmpeg.exe').symlink_to(os.path.relpath(ffmpeg,stage/'runtime/remix'))
    env=os.environ|{'PLAYWRIGHT_BROWSERS_PATH':str(stage/'runtime/browser')}
    run(['npx','--yes','--package=playwright@'+source['playwright'],'playwright','install','chromium','--only-shell'],env=env)
    from h3chat.tools_runtime import mark_ready
    mark_ready(stage,'documents')
    app=stage/'H3-Chat.app/Contents';(app/'MacOS').mkdir(parents=True)
    (app/'Info.plist').write_bytes(plistlib.dumps({'CFBundleIdentifier':'org.h3-chat.desktop','CFBundleName':'H3-Chat','CFBundleDisplayName':'H3-Chat','CFBundleExecutable':'H3-Chat','CFBundlePackageType':'APPL','CFBundleShortVersionString':__version__,'CFBundleVersion':__version__,'LSMinimumSystemVersion':'15.0','NSHighResolutionCapable':True,'LSBackgroundOnly':True}))
    launch=app/'MacOS/H3-Chat'
    run(['clang','-O2','-arch','arm64','-mmacosx-version-min=15.0',ROOT/'scripts/macos-launcher.c','-o',launch])
    run(['clang','-O2','-arch','arm64','-mmacosx-version-min=15.0',ROOT/'scripts/posix-process-guard.c','-o',stage/'runtime/tools/h3-process-guard'])
    from scripts.build_posix_tools import build as cpu_tools
    cpu_tools(stage)
    stop=stage/'Ferma-H3-Chat.command';stop.write_text('#!/bin/zsh\nset -eu\nROOT="$(cd "$(dirname "$0")" && pwd)"\nexec "$ROOT/runtime/python/bin/python3" -X utf8 "$ROOT/launcher.py" --stop\n');stop.chmod(0o755)
    shutil.copy2(ROOT/'docs/macos.md',stage/'LEGGIMI-MAC.md')
    run(['codesign','--force','--sign','-',stage/'H3-Chat.app'])
    (ROOT/'build/macos-stage.json').write_text(json.dumps({'path':str(stage),'version':__version__}))
    print(stage)


def package(stage):
    stage=Path(stage);out=ROOT/'dist';out.mkdir(exist_ok=True)
    target=out/f'H3-Chat-{__version__}-macos-arm64.zip';manifest={}
    for path in sorted(stage.rglob('*')):
        if path.is_file() or path.is_symlink():
            relative=path.relative_to(stage)
            if '__pycache__' in relative.parts or '.links' in relative.parts or path.suffix in ('.pyc','.pyo'):continue
            if relative.parts[0] in ('data','models','work') or path.suffix in ('.sqlite','.log'):
                raise ValueError('Private or temporary package member: '+relative.as_posix())
            if path.is_symlink():
                if not path.resolve().is_relative_to(stage.resolve()):raise ValueError('External package symlink: '+str(path))
                data=os.readlink(path).encode()
            else:data=path.read_bytes()
            manifest[path.relative_to(stage).as_posix()]=hashlib.sha256(data).hexdigest()
    with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as package:
        for name in manifest:
            path=stage/name
            if path.is_symlink():
                info=zipfile.ZipInfo('H3-Chat/'+name);info.create_system=3;info.external_attr=(stat.S_IFLNK|0o777)<<16;package.writestr(info,os.readlink(path))
            else:package.write(path,'H3-Chat/'+name)
        package.writestr('H3-Chat/FILES-SHA256.json',json.dumps(manifest,indent=2))
    digest=hashlib.sha256(target.read_bytes()).hexdigest();target.with_name(target.name+'.sha256').write_text(digest+'  '+target.name+'\n')
    with zipfile.ZipFile(target) as package:
        for name,value in manifest.items():assert hashlib.sha256(package.read('H3-Chat/'+name)).hexdigest()==value,name
    result={'status':'passed','archive':target.name,'sha256':digest,'size':target.stat().st_size,'verified_files':len(manifest),'all_member_sha256_verified':True,'private_data_and_generative_model_weights_excluded':True,'architecture':'arm64'}
    target.with_name(target.stem+'.verification.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))


if __name__=='__main__':
    if len(sys.argv)>1 and sys.argv[1]=='--package':package(json.loads((ROOT/'build/macos-stage.json').read_text())['path'])
    else:build()

"""Native Ubuntu/Kali x86_64 build. CPU/API works without an NVIDIA GPU."""
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tarfile

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))


def run(args,**kw):return subprocess.run(list(map(str,args)),check=True,**kw)


def source(project,revision):
    dest=ROOT/'build/linux-sources'/project
    if not (dest/'.git').exists():
        dest.mkdir(parents=True,exist_ok=True);run(['git','init',dest])
        run(['git','-C',dest,'remote','add','origin','https://github.com/'+{'sd':'leejet/stable-diffusion.cpp','music':'0xShug0/audio.cpp','llama':'ggml-org/llama.cpp'}[project]+'.git'])
    run(['git','-C',dest,'fetch','--depth','1','origin',revision]);run(['git','-C',dest,'checkout','--detach','FETCH_HEAD'])
    run(['git','-C',dest,'submodule','update','--init','--recursive','--depth','1'])
    return dest


def build_native(stage,backend='cpu'):
    stage=Path(stage);spec=json.loads((ROOT/'scripts/linux-sources.json').read_text())
    (stage/'native').mkdir(parents=True,exist_ok=True)
    sd=source('sd',spec['sd_revision']);audio=source('music',spec['music_revision'])
    patch=ROOT/'native/music/h3-artifacts.patch'
    if 'std::string h3_artifact_dir;' not in (audio/'include/engine/models/yue2/types.h').read_text():
        run(['git','-C',audio,'apply','--ignore-space-change',patch])
    cuda=backend=='cuda';build=ROOT/'build'/('linux-native-'+backend);build.mkdir(parents=True,exist_ok=True)
    sd_build=build/'sd';music_build=build/'music'
    common=['-G','Ninja','-DCMAKE_BUILD_TYPE=Release','-DCMAKE_INSTALL_RPATH=$ORIGIN','-DCMAKE_BUILD_WITH_INSTALL_RPATH=ON']
    run(['cmake','-S',sd,'-B',sd_build,*common,'-DSD_BUILD_SHARED_LIBS=ON','-DSD_CUDA='+('ON' if cuda else 'OFF'),'-DSD_VULKAN='+('ON' if backend=='vulkan' else 'OFF'),'-DGGML_NATIVE=OFF','-DCMAKE_CUDA_ARCHITECTURES=86-virtual;120-real'])
    run(['cmake','--build',sd_build,'--parallel','2'])
    sd_out=stage/'runtime'/backend/'sd';sd_out.mkdir(parents=True,exist_ok=True)
    for p in sd_build.rglob('*'):
        if p.is_file() and ('.so' in p.name or p.name=='sd-cli'):shutil.copy2(p,sd_out/p.name)
    run(['c++','-O2','-std=c++17',ROOT/'native/sd-worker.cpp','-ldl','-pthread','-o',stage/'native/h3-sd-worker'])
    notices=stage/'licenses/linux-native';notices.mkdir(parents=True,exist_ok=True)
    for project,tree in (('stable-diffusion',sd),('audio-cpp',audio)):
        for license in tree.glob('LICENSE*'):
            if license.is_file():shutil.copy2(license,notices/(project+'-'+license.name))
    if backend=='vulkan':return stage
    run(['cmake','-S',ROOT/'native/music','-B',music_build,*common,'-DAUDIOCPP_SOURCE_DIR='+str(audio),'-DAUDIOCPP_MODEL_SET=custom','-DAUDIOCPP_MODELS=yue2;htdemucs;seed_vc','-DENGINE_ENABLE_CUDA='+('ON' if cuda else 'OFF'),'-DENGINE_ENABLE_NATIVE_CPU=OFF','-DENGINE_BUILD_TESTS=OFF','-DCMAKE_CUDA_ARCHITECTURES=86-virtual;120-real'])
    run(['cmake','--build',music_build,'--target','h3-music-worker','audiocpp_cli','--parallel','2'])
    music_out=stage/'runtime/music'/backend;remix=stage/'runtime/remix'/backend
    music_out.mkdir(parents=True,exist_ok=True);remix.mkdir(parents=True,exist_ok=True)
    for p in music_build.rglob('*'):
        if p.is_file() and ('.so' in p.name or p.name in ('h3-music-worker','audiocpp_cli')):
            shutil.copy2(p,music_out/p.name);shutil.copy2(p,remix/p.name)
    if cuda:
        llama=source('llama',spec['llama_revision']);llama_build=build/'llama'
        run(['cmake','-S',llama,'-B',llama_build,*common,'-DGGML_CUDA=ON','-DGGML_NATIVE=OFF','-DLLAMA_CURL=OFF','-DLLAMA_BUILD_TESTS=OFF','-DCMAKE_CUDA_ARCHITECTURES=86-virtual;120-real'])
        run(['cmake','--build',llama_build,'--target','llama-server','--parallel','2'])
        llama_out=stage/'runtime/cuda/llama';llama_out.mkdir(parents=True,exist_ok=True)
        for p in llama_build.rglob('*'):
            if p.is_file() and ('.so' in p.name or p.name=='llama-server'):shutil.copy2(p,llama_out/p.name)
        for folder in (llama_out,sd_out,music_out,remix):
            for stem in ('libcudart.so','libcublas.so','libcublasLt.so'):
                for lib in Path('/usr/local/cuda/lib64').glob(stem+'*'):
                    target=folder/lib.name
                    if lib.is_symlink():
                        if not target.exists():target.symlink_to(os.readlink(lib))
                    elif lib.is_file():shutil.copy2(lib,target)
        for name in ('LICENSE','EULA.txt'):
            if (Path('/usr/local/cuda')/name).is_file():shutil.copy2(Path('/usr/local/cuda')/name,notices/('CUDA-'+name))
        shutil.copy2(llama/'LICENSE',notices/'llama-LICENSE')
    return stage


def build():
    if not sys.platform.startswith('linux') or platform.machine() not in ('x86_64','AMD64'):raise ValueError('Build on native Linux x86_64.')
    from scripts.package import release_file
    from scripts.build_macos import archive
    stage=ROOT/'build/linux/H3-Chat';stage.mkdir(parents=True,exist_ok=True)
    for name in ('h3chat','static','ui','licenses','skills/h3','docs','native','scripts'):
        for p in (ROOT/name).rglob('*'):
            if p.is_file() and release_file(p,ROOT) and p.suffix.lower() not in ('.exe','.dll','.pyd','.zip','.whl'):
                dest=stage/p.relative_to(ROOT);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,dest)
    for name in ('app.py','launcher.py','catalog.json','tools-models.json','upscale-runtimes.json','remix-runtimes.json','README.md','LICENSE','NOTICE','runtimes.json'):shutil.copy2(ROOT/name,stage/name)
    spec=json.loads((ROOT/'scripts/linux-sources.json').read_text());cache=ROOT/'build/linux-downloads';unpack=ROOT/'build/linux-unpack'
    archive(spec['python'],unpack/'python',cache);shutil.copytree(unpack/'python/python',stage/'runtime/python',symlinks=True,dirs_exist_ok=True)
    archive(spec['llama'],unpack/'llama',cache);exe=next((unpack/'llama').rglob('llama-server'));shutil.copytree(exe.parent,stage/'runtime/cpu/llama',symlinks=True,dirs_exist_ok=True)
    python=stage/'runtime/python/bin/python3'
    run([python,'-m','pip','install','--only-binary=:all:','--no-compile','--target',stage/'runtime/tools/documents','-r',ROOT/'scripts/linux-requirements.txt'])
    env=os.environ|{'PLAYWRIGHT_BROWSERS_PATH':str(stage/'runtime/browser')}
    run(['npx','--yes','--package=playwright@'+spec['playwright'],'playwright','install','chromium','--only-shell'],env=env)
    from scripts.build_posix_tools import build as tools
    tools(stage)
    media=stage/'runtime/remix';media.mkdir(parents=True,exist_ok=True)
    ffmpeg=next((stage/'runtime/tools/documents/imageio_ffmpeg/binaries').glob('ffmpeg-linux-*'))
    (media/'ffmpeg.exe').symlink_to(os.path.relpath(ffmpeg,media))
    transcription=media/'transcription';transcription.mkdir(exist_ok=True)
    archive(spec['score_python'],transcription,cache)
    (transcription/'python.exe').symlink_to('python/bin/python3')
    # pretty_midi is pure Python but its publisher distributes only an sdist.
    # Build its wheel on CI; never run a source build on an end-user machine.
    score_wheels=ROOT/'build/linux-score-wheels';score_wheels.mkdir(parents=True,exist_ok=True)
    run([transcription/'python.exe','-m','pip','wheel','--no-deps','--wheel-dir',score_wheels,'pretty_midi==0.2.10'])
    run([transcription/'python.exe','-m','pip','install','--no-index','--no-deps','--find-links',score_wheels,'--target',transcription/'Lib/site-packages','pretty_midi==0.2.10'])
    for filename,flags in (('Avvia-H3-Chat.sh',''),('Ferma-H3-Chat.sh','--stop')):
        p=stage/filename;p.write_text('#!/bin/sh\nset -eu\nHERE="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"\nexec "$HERE/runtime/python/bin/python3" -X utf8 "$HERE/launcher.py" '+flags+'\n');p.chmod(0o755)
    shutil.copy2(ROOT/'scripts/install-linux-system.sh',stage/'Installa-dipendenze-Linux.sh');(stage/'Installa-dipendenze-Linux.sh').chmod(0o755)
    build_native(stage)
    build_native(stage,'vulkan')
    vulkan={'url':'https://github.com/ggml-org/llama.cpp/releases/download/b10809/llama-b10809-bin-ubuntu-vulkan-x64.tar.gz','size':33799345,'sha256':'07f029cef440c82c3cff5310641eb6347e5cbcd865a5d88990215058aa049e93'}
    archive(vulkan,unpack/'vulkan',cache);exe=next((unpack/'vulkan').rglob('llama-server'));shutil.copytree(exe.parent,stage/'runtime/vulkan/llama',symlinks=True,dirs_exist_ok=True)
    from scripts.linux_manifest import build as manifest
    manifest(stage)
    (ROOT/'build/linux-stage.json').write_text(json.dumps({'path':str(stage)}));return stage


def package(stage):
    from h3chat import __version__
    stage=Path(stage);out=ROOT/'dist';out.mkdir(exist_ok=True)
    target=out/f'H3-Chat-{__version__}-linux-x64.tar.gz'
    def allowed(info):
        path=Path(info.name)
        if len(path.parts)>1 and path.parts[1] in ('data','models','work') or any(v in path.parts for v in ('.git','__pycache__')) or path.suffix in ('.pyc','.log','.sqlite'):return None
        if info.issym() and not (stage.parent/info.name).resolve().is_relative_to(stage.resolve()):raise ValueError('External symlink in package: '+info.name)
        return info
    with tarfile.open(target,'w:gz',compresslevel=6) as archive:archive.add(stage,arcname='H3-Chat',filter=allowed)
    digest=hashlib.file_digest(target.open('rb'),'sha256').hexdigest();target.with_name(target.name+'.sha256').write_text(digest+'  '+target.name+'\n')
    print(json.dumps({'archive':str(target),'sha256':digest,'size':target.stat().st_size,'platform':'linux-x64'}))


if __name__=='__main__':
    if '--native-cuda' in sys.argv:build_native(Path(sys.argv[-1]),'cuda')
    elif '--package' in sys.argv:package(json.loads((ROOT/'build/linux-stage.json').read_text())['path'])
    else:build()

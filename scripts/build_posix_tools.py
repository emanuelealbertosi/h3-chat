"""Build portable CPU tools; build dependencies stay on the CI host."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))


def build(stage):
    stage=Path(stage)
    from h3chat.platform_runtime import python_executable
    from h3chat.tools_runtime import mark_ready
    from scripts.build_macos import archive
    python=python_executable(stage)
    run=lambda args,**kw:subprocess.run(list(map(str,args)),check=True,**kw)
    requirements=ROOT/'scripts/lab-requirements.txt'
    wheels=ROOT/'build/posix-tool-wheels';wheels.mkdir(parents=True,exist_ok=True)
    # Pango/Cairo are compiled only on the build machine. macOS dylibs are
    # repaired into their wheels so users do not need Homebrew installed.
    run([python,'-m','pip','wheel','--wheel-dir',wheels,'-r',requirements])
    wheel_source=wheels
    if sys.platform=='darwin':
        run([sys.executable,'-m','pip','install','delocate==0.13.0'])
        repaired=ROOT/'build/macos-repaired-wheels';repaired.mkdir(parents=True,exist_ok=True)
        for wheel in wheels.glob('*.whl'):
            if (repaired/wheel.name).exists():continue
            if 'none-any' in wheel.name:shutil.copy2(wheel,repaired/wheel.name)
            else:run([sys.executable,'-m','delocate.cmd.delocate_wheel','-w',repaired,wheel])
        wheel_source=repaired
    run([python,'-m','pip','install','--no-index','--find-links',wheel_source,'--no-compile','--target',stage/'runtime/tools/lab','-r',requirements])
    run([python,'-m','pip','install','--only-binary=:all:','--no-compile','--target',stage/'runtime/tools/asr','-r',ROOT/'scripts/posix-asr-requirements.txt'])
    sources=json.loads((ROOT/'scripts/posix-tools-sources.json').read_text())
    latex=stage/'runtime/tools/latex'
    archive(sources['tinytex_mac' if sys.platform=='darwin' else 'tinytex_linux'],latex,ROOT/'build/posix-downloads')
    # The official archive has .TinyTeX on Unix. Keep one portable app path.
    candidates=[p for p in latex.iterdir() if p.is_dir() and (p/'bin').is_dir()]
    if len(candidates)!=1:raise ValueError('Unexpected TinyTeX archive layout.')
    if candidates[0].name!='TinyTeX':candidates[0].rename(latex/'TinyTeX')
    if sys.platform.startswith('linux'):
        # The pinned official Linux TinyTeX base omits dvisvgm (the macOS
        # archive includes it). Install the actual TeX Live package at BUILD
        # time; users must not need a package manager or a download on render.
        bins=[p for p in (latex/'TinyTeX/bin').iterdir() if p.is_dir()]
        if len(bins)!=1:raise ValueError('Unexpected TinyTeX executable directory.')
        if not (bins[0]/'dvisvgm').is_file():run([bins[0]/'tlmgr','install','dvisvgm'])
        if not all((bins[0]/name).is_file() for name in ('latex','dvisvgm')):raise ValueError('Incomplete packaged TinyTeX: latex/dvisvgm missing.')
    for name in ('lab-requirements.txt','macos-requirements.txt','posix-asr-requirements.txt'):
        shutil.copy2(ROOT/'scripts'/name,stage/'scripts'/name)
    # Mark with the packaged manifest, never the build host's paths.
    for kind in ('documents','lab','asr'):mark_ready(stage,kind)


if __name__=='__main__':build(sys.argv[1])

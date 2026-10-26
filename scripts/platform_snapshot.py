"""Copy release source changes to a separate build checkout; never user data."""
import json
from pathlib import Path
import shutil
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from scripts.package import release_file


def copy(target):
    target=Path(target).resolve()
    if not (target/'.git').exists():raise ValueError('Target must be a separate Git build checkout.')
    if not target.is_relative_to(ROOT/'work'):raise ValueError('Build checkout must stay in this task work directory.')
    bases=('h3chat','ui','static','native','scripts','tests','licenses','docs','skills/h3','.github')
    roots=('app.py','launcher.py','catalog.json','runtimes.json','tools-models.json','upscale-runtimes.json','remix-runtimes.json','README.md','LICENSE','NOTICE','package.json','package-lock.json','.gitignore')
    files=[]
    for base in (*bases,*roots):
        p=ROOT/base
        for file in p.rglob('*') if p.is_dir() else [p]:
            if not file.is_file() or not release_file(file,ROOT) or file.suffix.lower() in ('.exe','.dll','.pyd','.zip','.tar','.gz','.whl'):continue
            rel=file.relative_to(ROOT);dest=target/rel
            if dest.exists() and dest.read_bytes()==file.read_bytes():continue
            dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(file,dest);files.append(rel.as_posix())
    print(json.dumps({'copied':len(files),'private_data':False,'target':str(target)}))


if __name__=='__main__':copy(sys.argv[1])

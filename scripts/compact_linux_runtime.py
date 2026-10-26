"""Hard-link byte-identical runtime libraries before tar packaging."""
import hashlib
import json
import os
from pathlib import Path
import sys
import uuid

def compact(stage):
    root=(Path(stage).resolve()/'runtime');groups={};count=saved=0
    for p in root.rglob('*.so*'):
        if p.is_symlink() or not p.is_file():continue
        size=p.stat().st_size
        if size>=1024**2:groups.setdefault((p.name,size,p.stat().st_mode & 0o777),[]).append(p)
    for paths in groups.values():
        if len(paths)<2:continue
        hashes={}
        for p in sorted(paths):
            with p.open('rb') as f:digest=hashlib.file_digest(f,'sha256').hexdigest()
            first=hashes.setdefault(digest,p)
            if first==p or os.path.samefile(first,p):continue
            temp=p.with_name(p.name+'.dedup-'+uuid.uuid4().hex)
            try:
                os.link(first,temp);os.replace(temp,p)
            finally:
                if temp.exists():temp.unlink()
            count+=1;saved+=p.stat().st_size
    report={'status':'passed','hardlinks_created':count,'duplicate_bytes_removed':saved,'file_paths_unchanged':True}
    print(json.dumps(report));return report

if __name__=='__main__':compact(sys.argv[1])

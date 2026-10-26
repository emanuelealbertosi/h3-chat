"""Resolve an application-owned renderer on every supported desktop."""
import os
from pathlib import Path


def executable(root):
    base=Path(root)/'runtime/browser'
    names={'headless_shell','chrome-headless-shell','chrome','Chromium','Google Chrome for Testing'}
    if base.is_dir():
        found=[p for p in base.rglob('*') if p.is_file() and p.name in names and os.access(p,os.X_OK)]
        if found:return sorted(found,key=lambda p:('headless' not in p.name,str(p)))[0]
    if os.name=='nt':
        for key,default in (('PROGRAMFILES(X86)','C:/Program Files (x86)'),('PROGRAMFILES','C:/Program Files')):
            p=Path(os.environ.get(key,default))/'Microsoft/Edge/Application/msedge.exe'
            if p.is_file():return p
    return None

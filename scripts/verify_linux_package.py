"""Verify the real Linux release archive without extracting or executing it."""
import hashlib
import json
from pathlib import Path,PurePosixPath
import posixpath
import sys
import tarfile

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from h3chat import __version__
from scripts.verify_feature_files import verify_members

def verify(path):
    path=Path(path);names=set();regular=0
    auxiliary={f'H3-Chat/h3chat/vendor_pdd/{folder}/{stem}{kind}.safetensors'
        for folder,stem in (('adaln_basis','basis_'),('partition_fingerprints','video_out_')) for kind in ('fl2va','ref2va')}
    with tarfile.open(path,'r:gz') as package:
        for member in package:
            name=member.name;p=PurePosixPath(name)
            if p.is_absolute() or '..' in p.parts or not p.parts or p.parts[0]!='H3-Chat' or name in names:raise ValueError('Unsafe or duplicate archive member: '+name)
            names.add(name)
            if len(p.parts)>1 and p.parts[1] in ('data','models','work') or name.endswith(('docs/h3-session-state.json','.sqlite','.log')):raise ValueError('Private archive member: '+name)
            if p.suffix.lower() in ('.gguf','.ckpt','.safetensors') and name not in auxiliary:raise ValueError('Unexpected model weights: '+name)
            if member.issym() or member.islnk():
                target=posixpath.normpath(posixpath.join(str(p.parent),member.linkname)) if member.issym() else posixpath.normpath(member.linkname)
                if not target.startswith('H3-Chat/'):raise ValueError('External archive link: '+name)
            elif member.isfile():
                with package.extractfile(member) as stream:
                    size=0
                    while block:=stream.read(4*1024**2):size+=len(block)
                    if size!=member.size:raise ValueError('Incomplete archive member: '+name)
                regular+=1
            elif not member.isdir():raise ValueError('Unsupported archive object: '+name)
    for name in ('Avvia-H3-Chat.sh','Ferma-H3-Chat.sh','Installa-dipendenze-Linux.sh','runtime/python/bin/python3','native/h3-sd-worker','runtime/cpu/llama/llama-server','skills/h3/SKILL.md'):
        if 'H3-Chat/'+name not in names:raise ValueError('Required packaged file missing: '+name)
    features=verify_members(names)
    with path.open('rb') as stream:digest=hashlib.file_digest(stream,'sha256').hexdigest()
    if path.with_name(path.name+'.sha256').read_text().split()[0]!=digest:raise ValueError('Archive checksum mismatch.')
    report={'status':'passed','archive':path.name,'size':path.stat().st_size,'sha256':digest,'verified_members':len(names),'regular_files':regular,'all_member_payloads_read':True,'private_data_and_generative_weights_excluded':True,'links_confined_to_package':True,'gpu_inference_tested':False,'feature_files':features}
    path.with_name(f'H3-Chat-{__version__}-linux-x64.verification.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report));return report

if __name__=='__main__':verify(sys.argv[1] if len(sys.argv)>1 else ROOT/'dist'/f'H3-Chat-{__version__}-linux-x64.tar.gz')

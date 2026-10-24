from pathlib import Path
import hashlib,json,zipfile

R=Path(__file__).resolve().parents[1]
import sys
sys.path.insert(0,str(R))
from h3chat import __version__
W=R/'dist'
archive=W/f'H3-Chat-{__version__}-windows-x64.zip'
with zipfile.ZipFile(archive) as package:
    manifest=json.loads(package.read('H3-Chat/FILES-SHA256.json'))
    names=set(package.namelist())
    assert names=={'H3-Chat/'+name for name in manifest}|{'H3-Chat/FILES-SHA256.json'}
    for name,digest in manifest.items():
        assert hashlib.sha256(package.read('H3-Chat/'+name)).hexdigest()==digest,name
    required=('Installa-API-senza-GPU.bat','skills/h3/SKILL.md','h3chat/slide_resume.py','h3chat/embeddinggemma2.py','docs/api-only-windows.md')
    assert all('H3-Chat/'+name in names for name in required)
    private=('H3-Chat/data/','H3-Chat/models/','H3-Chat/work/','H3-Chat/runtime/installation-profile.json','H3-Chat/docs/h3-session-state.json')
    assert not any(name.startswith(private) for name in names)
    auxiliary={'H3-Chat/h3chat/vendor_pdd/'+folder+'/'+name+'.safetensors'
               for folder,prefix in (('adaln_basis','basis_'),('partition_fingerprints','video_out_'))
               for name in (prefix+'fl2va',prefix+'ref2va')}
    assert not any(name.endswith(('.safetensors','.gguf','.ckpt','.sqlite','.log')) and name not in auxiliary for name in names)
digest=hashlib.sha256(archive.read_bytes()).hexdigest()
assert archive.with_name(archive.name+'.sha256').read_text().split()[0]==digest
result={'status':'passed','archive':archive.name,'size':archive.stat().st_size,'sha256':digest,'verified_files':len(manifest),
        'api_only_installer_included':True,'private_data_and_generative_model_weights_excluded':True,'bundled_pdd_algorithm_tensors':4,'all_member_sha256_verified':True}
(W/f'H3-Chat-{__version__}-windows-x64.verification.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
print(json.dumps(result))

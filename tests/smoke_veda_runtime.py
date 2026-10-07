"""Opt-in native VEDA smoke: real predictor, tiny synthetic QKV, no video model.

Run with --gpu for the actual Triton self-test; default uses a CPU reference
backend only for verification, not as a supported CPU video mode.
"""
import json,os,sys,time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
root=Path(__file__).resolve().parents[1];gpu='--gpu' in sys.argv
if gpu:
    import urllib.request
    marker=root/'data/maintenance-token.txt'
    if marker.exists():
        token=marker.read_text().strip()
        try:state=json.load(urllib.request.urlopen(urllib.request.Request('http://127.0.0.1:8788/api/maintenance/state',headers={'X-H3-Token':token}),timeout=3))
        except urllib.error.URLError:state={}
        if any(j.get('status') in ('queued','running') for j in state.get('jobs',[])):raise RuntimeError('GPU occupata: test non avviato.')
runtime=root/'runtime/vision';sys.path[:0]=[str(root),str(runtime/'packages'),str(runtime/'core')]
os.environ['TRITON_CACHE_DIR']=str(runtime/'cache/triton')
os.environ['CC']=str(runtime/'packages/triton/runtime/tcc/tcc.exe')
os.environ['CUDA_PATH']=str(runtime/'packages/triton/backends/nvidia');os.environ['CUDA_HOME']=os.environ['CUDA_PATH']
import torch
import comfy.cli_args
comfy.cli_args.args.cpu=not gpu;comfy.cli_args.args.use_pytorch_cross_attention=True
from comfy.model_patcher import ModelPatcher
from comfy.ldm.minimax.model import PackedLayout
from comfy.ldm.modules import attention
from h3chat.veda import attach,report,release,REVISION
sys.path.insert(0,str(root/'runtime/veda'/REVISION))
device=torch.device('cuda:0' if gpu else 'cpu');torch.set_num_threads(4)
fake=torch.nn.Module();fake.diffusion_model=SimpleNamespace(blocks=[SimpleNamespace(attn=SimpleNamespace(heads=56,head_dim=128)) for _ in range(50)])
model=ModelPatcher(fake,device,torch.device('cpu'));model.set_model_optimized_attention(attention.attention_sage if gpu else attention.attention_pytorch)
events=[]
def emit(event,**value):events.append(value);print(value,flush=True)
def exercise():
    started=time.monotonic();patched,veda=attach(root,model,{'veda_sparsity':90,'veda_reference_sparsity':0},8,emit)
    layout=PackedLayout(8,4,16,16,4);opts=patched.model_options['transformer_options']|{'minimax_h3_layout':layout,'block_index':0}
    veda.on_prepare(patched,{'transformer_options':opts})
    q,k,v=[torch.randn((1,56,layout.seq_len,128),dtype=torch.bfloat16,device=device) for _ in range(3)]
    with torch.no_grad():
        result=attention.attention_pytorch(attention.AttentionTensorContainer(q),attention.AttentionTensorContainer(k),attention.AttentionTensorContainer(v),56,skip_reshape=True,transformer_options=opts)
    assert result.shape==(1,layout.seq_len,56*128) and torch.isfinite(result).all()
    veda.on_cleanup();actual=report(veda);assert actual['active'],actual;assert actual['sparse_calls']==1,actual
    print(json.dumps({'device':str(device),'shape':list(result.shape),'seconds':round(time.monotonic()-started,2),'veda':actual}),flush=True)
    assert model.model_options['transformer_options']['optimized_attention_override'] is not patched.model_options['transformer_options']['optimized_attention_override']
    release(veda);assert veda.bundle is None and not veda._engines
if gpu:exercise()
else:
    from veda_comfy.core.reference import block_sparse_attention
    class ReferenceBackend:
        display='CPU reference (test only)';dtypes=(torch.bfloat16,);name='reference'
        def attend(self,q,k,v,mask,layout):return block_sparse_attention(q,k,v,mask,layout)
    resolution=SimpleNamespace(backend=ReferenceBackend(),device=SimpleNamespace(label='CPU reference'),report=lambda:'CPU reference')
    with patch('veda_comfy.backends.resolve',return_value=resolution):exercise()

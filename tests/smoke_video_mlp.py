"""Opt-in INT8 MLP equivalence: CUDA, CPU-stored weights, partial batches."""
import json,os,sys,sqlite3
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import patch
root=Path(__file__).resolve().parents[1]
if '--gpu' not in sys.argv:
    print('Opt-in numerical GPU verification: pass --gpu.');raise SystemExit(0)
if (root/'data/chat.sqlite').exists():
    with sqlite3.connect((root/'data/chat.sqlite').as_uri()+'?mode=ro',uri=True) as db:
        assert not db.execute("SELECT 1 FROM jobs WHERE status IN ('running','queued')").fetchone(),'GPU queue busy'
runtime=root/'runtime/vision'
dll=os.add_dll_directory(str(runtime/'dlls')) if os.name=='nt' and (runtime/'dlls').is_dir() else None
sys.path[:0]=[str(root),str(runtime/'packages'),str(runtime/'core')]
os.environ['PYTORCH_ALLOC_CONF']='backend:cudaMallocAsync'
import comfy.cli_args
comfy.cli_args.args.cuda_malloc=True
import torch,comfy.ops
from comfy.ldm.minimax.model import MLP
from h3chat.video_mlp import run_chunked,supported
torch.manual_seed(734);torch.set_num_threads(4)
ops=comfy.ops;cases=[]
for rotated in (False,True):
    for offload in (False,True):
        mlp=MLP(256,1024,operations=ops.mixed_precision_ops(compute_dtype=torch.bfloat16))
        for fc in (mlp.fc1,mlp.fc2):
            data=torch.randn((fc.out_features,fc.in_features),dtype=torch.bfloat16,device='cuda')*.02
            q=ops.QuantizedTensor.from_float(data,'TensorWiseINT8Layout',scale='recalculate',is_weight=True,per_channel=True,convrot=rotated)
            if offload:q=q.to('cpu')
            fc.weight=torch.nn.Parameter(q,requires_grad=False)
            fc.layout_type='TensorWiseINT8Layout';fc.quant_format='int8_tensorwise'
        assert supported(mlp,ops)
        x=torch.randn((2,193,256),dtype=torch.bfloat16,device='cuda')
        with torch.no_grad():
            expected=mlp(x)
            with patch.object(ops,'CastBiasWeightContext',wraps=ops.CastBiasWeightContext) as transfers:
                actual=run_chunked(mlp,x,torch,ops,65536)
            assert transfers.call_count==2,transfers.call_count
            torch.cuda.synchronize()
        error=(actual.float()-expected.float()).abs()
        record={'rotated':rotated,'offloaded':offload,'equal':torch.equal(actual,expected),'max_error':error.max().item(),'mean_error':error.mean().item(),'transfers':transfers.call_count}
        print(json.dumps(record),flush=True);cases.append(record)
        assert torch.isfinite(actual).all()
        assert record['max_error']==0,record
print(json.dumps({'verified':True,'cases':cases}),flush=True)

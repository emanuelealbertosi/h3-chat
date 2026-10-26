"""Real pinned Comfy FinalLayer on CPU, no checkpoint and no GPU model."""
import json
from pathlib import Path
import sys
from types import SimpleNamespace
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'runtime/vision/packages'),str(ROOT/'runtime/vision/core')]
from comfy.cli_args import args
args.cpu=True
import torch
torch.set_num_threads(2)
import comfy.ops
from comfy.ldm.minimax.model import FinalLayer
from h3chat.fasth3 import install_head_bank
head=FinalLayer(4,4,96,32,1e-6,dtype=torch.float32,device='cpu',operations=comfy.ops.manual_cast)
head.video_out=comfy.ops.manual_cast.Linear(4,3072);head.audio_out=comfy.ops.manual_cast.Linear(4,1024)
with torch.no_grad():
    for p in head.parameters():torch.nn.init.uniform_(p,-.1,.1)
model=SimpleNamespace(final_layer=head,latents_dim=768,audio_latents_dim=1024,patch_size=(1,2,2),
    video_patch_proj=comfy.ops.manual_cast.Linear(96,4),audio_patch_proj=comfy.ops.manual_cast.Linear(32,4))
x=torch.randn(7,4);embedding=torch.randn(1,4);sigmas=torch.tensor([1.,.5,0.])
before=head(x,embedding,(4,7,0),(0,4,0),sigmas[0],sigmas,(12.,3.))
assert [list(v.shape) for v in before]==[[3,3072],[4,1024]]
report=install_head_bank(model)
assert (model.latents_dim,model.audio_latents_dim)==(24,32)
for sigma in sigmas[:-1]:
    after=head(x,embedding,(4,7,0),(0,4,0),sigma,sigmas,(12.,3.))
    assert [list(v.shape) for v in after]==[[3,96],[4,32]]
    assert all(torch.isfinite(v).all() and v.device.type=='cpu' for v in after)
assert install_head_bank(model)['heads']==32
print(json.dumps({'before':[[3,3072],[4,1024]],'after':[[3,96],[4,32]],'gpu_models_loaded':0,'report':report}))

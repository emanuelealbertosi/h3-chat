"""Folder-scoped YuE2 sidecars, always read from their original locations."""
import json
from pathlib import Path
from .models import metadata

SIDECARS={'tokenizer':'yue2-qwen.tiktoken','model_config':'yue2-model-config.json',
          'generation_config':'yue2-generation-config.json','vae_config':'yue2-vae-config.json'}

def sidecar_entries(folder):
 result=[]
 for role,name in SIDECARS.items():
  path=Path(folder)/'sidecars'/name;valid=False;size=0
  try:
   size=path.stat().st_size
   if 0<size<=8*1024**2:
    if role=='tokenizer':
     with path.open(encoding='utf-8') as source:valid=len(source.readline().split())==2
    else:
     obj=json.loads(path.read_text(encoding='utf-8'));valid=isinstance(obj,dict) and bool(obj)
  except (OSError,ValueError):pass
  result.append({'role':role,'path':str(path),'filename':name,'size':size,'valid':valid})
 return result

def weight_problems(files):
 issues=[]
 for role,anchors in (('model',{'model.embed_tokens.weight','vae2llm.weight','llm2vae.weight'}),
                      ('vae',{'decoder.layers.0.weight','decoder.layers.0.weight_g'})):
  info=metadata(files[role]);names={n.removeprefix(role+'_weights/') for n in info.get('_h3_tensor_names',())}
  compatible=anchors<=names if role=='model' else bool(anchors&names)
  if info.get('general.architecture')!='audiocpp' or not info.get('_h3_tensor_scan_ok') or not compatible:
   issues.append('YuE2: '+('pesi principali' if role=='model' else 'VAE audio')+' non riconosciuti o incompatibili.')
 return issues

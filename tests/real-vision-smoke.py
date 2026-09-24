"""Opt-in real-weight standalone tests; never writes to the user's chat database."""
import argparse
import json
from pathlib import Path
import sys
import threading
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from h3chat.service import Service

parser = argparse.ArgumentParser()
parser.add_argument('--weights', type=Path, required=True, help='Root containing Stable-diffusion, text_encoder and VAE')
parser.add_argument('--profile', choices=['ming','qwen21'], required=True)
parser.add_argument('--size', type=int, default=1024)
parser.add_argument('--edit', action='store_true')
args = parser.parse_args()
names = {
    'ming': ['ming_image_0.1_design_int8_convrot.safetensors', 'ming_image_0.1_ling_mini_2.0_w4a8.safetensors', 'ming_image_vae_bf16.safetensors'],
    'qwen21': ['qwen_image_2.1_int8_convrot.safetensors', 'qwen3vl_8b_int8_convrot.safetensors', 'qwen_image_2.1_vae_bf16.safetensors'],
}[args.profile]
data = ROOT / 'work' / ('real-vision-'+args.profile)
app = Service(ROOT, data, start_worker=False)
try:
    model = app.external_model({'profile':args.profile, 'name':args.profile, 'files':{
        role:str(args.weights / directory / name) for role,directory,name in zip(
            ['diffusion','llm','vae'], ['Stable-diffusion','text_encoder','VAE'], names)}})
    settings = app.save_settings({'profile':'balanced','backend':'cuda','threads':6,'memory_policy':'on_demand',
        'ram_cache_gb':0,'create_model':model['id'],'edit_model':model['id'],
        'seed':123456,'image_overrides':{model['id']:{'width':args.size,'height':args.size}}})
    prompt = 'A clean vector-style educational diagram on a white background. Three large rounded boxes, horizontally aligned. Left blue box label "INPUT"; centre orange box label "PROCESSO"; right green box label "OUTPUT". One straight black arrow from INPUT to PROCESSO, one from PROCESSO to OUTPUT. Exactly three boxes and two arrows. Clear Italian uppercase sans-serif text, generous whitespace, precise alignment. No extra text.'
    results = []
    refs = []
    for label in (['create','edit'] if args.edit else ['create']):
        started = time.monotonic()
        media = app.engine.generate(model, settings, prompt if label=='create' else 'Edit image 1: change the orange central box to purple. Keep all three labels, arrows and geometry exactly as in the reference.',
            refs, label, threading.Event(), lambda text:print(text,flush=True))
        result = {'mode':label,'seconds':round(time.monotonic()-started,2),'media':media,'memory':app.engine.snapshot()}
        results.append(result)
        print(json.dumps(result),flush=True)
        refs = [media]
    (data/'result.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
finally:
    app.close()

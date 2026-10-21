"""Local FIBO 2.0 contracts; no imports of GPU libraries in the application."""
import json
from pathlib import Path

DIFFUSERS_REVISION='de988b7ee77c393a63865d265d19e267ef9c7bf5'
WEIGHTS_REVISION='530604492bf2bd1364ae43ca6b2bf2285ef0f2ba'
NEGATIVE_EDIT='{"short_description":"","objects":[],"background_setting":"","lighting":{},"aesthetics":{},"photographic_characteristics":{},"style_medium":"","context":"","artistic_style":""}'
NEGATIVE_T2I=json.dumps({'short_description':'','objects':[{'description':'the main subject','texture':'smooth, featureless, plastic-like, airbrushed, no fine surface detail','appearance_details':'soft blurred edges, simplified shapes, no fine detail','skin_tone_and_texture':'waxy airbrushed skin, poreless, plastic smooth'}],
    'background_setting':'a plain seamless studio backdrop, perfectly smooth gradient, blurred and featureless, no visible texture','lighting':{},'aesthetics':{'artifacts':['oversaturated colours','neon colour cast','overexposed highlights','lens flare','slight blur','motion blur','haze']},
    'photographic_characteristics':{'depth_of_field':'shallow, heavy bokeh obscuring most of the frame','focus':'soft, slightly out of focus, lacking fine texture'},'style_medium':'','context':'','artistic_style':''})


def pipeline_root(files):
    root=Path(files['diffusion']).resolve().parent.parent
    if quantized(files):
        expected={'llm':root/'text_encoders/qwen3vl_4b_int8_convrot.safetensors','vae':root/'vae/diffusion_pytorch_model.safetensors'}
        if any(Path(files[k]).resolve()!=p for k,p in expected.items()):raise ValueError('FIBO INT8: encoder e VAE devono appartenere alla stessa cartella preparata.')
        return root
    expected={'diffusion':root/'transformer/diffusion_pytorch_model-00001-of-00002.safetensors',
              'llm':root/'text_encoder/model.safetensors','vae':root/'vae/diffusion_pytorch_model.safetensors'}
    if any(Path(files[k]).resolve()!=p for k,p in expected.items()):
        raise ValueError('FIBO 2.0: scegli il primo shard in transformer e gli encoder/VAE della stessa cartella Diffusers originale.')
    return root


def quantized(files):
    path=Path(files.get('diffusion',''))
    return path.parent.name=='diffusion_models' and path.name=='fibo2_dev_int8_convrot.safetensors'


def sidecars(files):
    root=pipeline_root(files)
    names=['model_index.json','transformer/config.json','transformer/diffusion_pytorch_model.safetensors.index.json',
        'transformer/diffusion_pytorch_model-00002-of-00002.safetensors','text_encoder/config.json',
        'processor/processor_config.json','processor/tokenizer.json','processor/tokenizer_config.json','processor/chat_template.jinja',
        'vae/config.json','scheduler/scheduler_config.json','fonts/Aileron-Regular.otf','fonts/DejaVuSans.ttf']
    if quantized(files):names=[n for n in names if n not in ('transformer/diffusion_pytorch_model.safetensors.index.json','transformer/diffusion_pytorch_model-00002-of-00002.safetensors')]
    try:
        if json.loads((root/'model_index.json').read_text(encoding='utf-8')).get('_class_name')!='BriaFibo2Pipeline':
            raise ValueError('La cartella non contiene una pipeline FIBO 2.0.')
    except (OSError,ValueError) as exc:raise ValueError('Manifest FIBO 2.0 mancante o non valido.') from exc
    from .external_models import valid_weight
    result=[]
    for i,name in enumerate(names):
        path=root/name;valid=path.is_file() and path.stat().st_size>0
        if name.endswith('.safetensors'):valid=valid and valid_weight(path)
        result.append({'role':f'fibo_sidecar_{i}','path':str(path),'filename':name,'size':path.stat().st_size if path.is_file() else 0,'valid':bool(valid)})
    return result


def status(root):
    folder=Path(root)/'runtime/fibo2'
    try:ready=json.loads((folder/'ready.json').read_text()).get('diffusers_revision')==DIFFUSERS_REVISION
    except (OSError,ValueError):ready=False
    return {'ready':ready and (folder/'packages/diffusers/pipelines/bria_fibo2/pipeline_bria_fibo2.py').is_file(),
        'note':'FIBO 2.0 · CUDA con offload sequenziale; pesi locali e nessun download automatico.'}


def validate_options(options):
    if options.get('fibo_offload','sequential') not in ('sequential','group','resident','full'):raise ValueError('Gestione memoria FIBO non valida.')
    if options.get('sampler') not in ('auto','euler') or options.get('scheduler') not in ('auto','simple'):
        raise ValueError('FIBO 2.0 usa FlowMatch Euler e lo scheduler ufficiale (Automatico/Simple). Gli altri scheduler non sono implementati.')
    options['sampler']='euler';options['scheduler']='simple';options['strength']=1.0


def prompt(value,editing=False):
    if not isinstance(value,str) or not value.strip():raise ValueError('Scrivi un prompt FIBO.')
    raw=value.strip()
    if raw.startswith('{'):
        try:caption=json.loads(raw)
        except ValueError as exc:raise ValueError('Descrizione strutturata FIBO: JSON non valido.') from exc
        if not isinstance(caption,dict):raise ValueError('FIBO richiede una descrizione JSON ad oggetto.')
        # A structured edit needs a real instruction, not a caption silently
        # interpreted as the instruction string by the upstream pipeline.
        if editing and not isinstance(caption.get('edit_instruction'),str):
            raise ValueError('Per modificare con JSON FIBO includi edit_instruction; in alternativa scrivi una normale istruzione.')
        return json.dumps(caption,ensure_ascii=False,separators=(',',':'))
    return raw


def negative(value,editing=False):
    if not value.strip():return NEGATIVE_EDIT if editing else NEGATIVE_T2I
    return prompt(value) if value.lstrip().startswith('{') else json.dumps({'short_description':value},ensure_ascii=False)


ASSISTANT_BRIEF='''You prepare prompts for FIBO 2.0. Return JSON with exactly one string field "prompt".
That string is itself a valid JSON visual description. Use short_description,
objects (each with description and location), background_setting, lighting,
style_medium, artistic_style and photographic_characteristics where relevant.
Describe exact counts, positions, relationships, materials and requested visible
text in the user's language. Other descriptions are in English. No invented
facts or arbitrary style changes. Do not add empty attributes or quality scores.
When visible lettering is requested, include text_render: an array of objects
with text (the exact literal wording, preserving accents and punctuation) and
location. Keep lettering out of objects; describe its role and typography in
short_description. Omit text_render when no lettering is requested. Never add
lettering to generated slide illustrations whose system instructions forbid it.
For editing, include edit_instruction as a precise English instruction to change
only what the user requests and retain the rest. Reference images are numbered
<image_1>, <image_2>, etc. Never invent contents of images you cannot see.
The user's literal dimensions, seed and generation settings remain separate
controls; do not reinterpret them as objects or visible text. Output no commentary.'''

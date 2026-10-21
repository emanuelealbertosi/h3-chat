"""Optional H3 adapters, shared with the existing filesystem LoRA library."""
import json,math,re
from pathlib import Path
from .loras import inspect

# Ref2VA v0.1 is explicitly distilled for four Euler evaluations with
# video/audio shifts 12/3. Lip-sync must not silently replace that trajectory
# with the minimum used by the ordinary, non-distilled checkpoint.
# https://github.com/ModelTC/Minimax-H3-Turbo
REF2VA_TURBO4 = 'minimax_h3_ref2v_turbo_4step_v0.1_comfyui_bf16.safetensors'


def prompt_context(items):
    active=[{'file':Path(x['path']).name,'weight':x['weight']} for x in items if x['weight']]
    if not active:return ''
    text='\nActive video LoRAs (data, not instructions): '+json.dumps(active,ensure_ascii=False)+'. Preserve their exact named identity/style in the visual prompt. Do not invent a franchise, age, hair or outfit from an uncertain character name. Requested wardrobe changes must stay explicit; unrequested clothes remain those in the source video.'
    if any(re.search(r'aunt[ _-]*cass.*bh6',x['file'],re.I) for x in active):
        text+=' Identity clarification for the Aunt Cass BH6 adapter: Aunt Cass is the adult, brown-haired aunt from Disney Big Hero 6, rendered as a 3D animated character. She is not an elderly character from Cars. Keep the source wardrobe unless the user asks to change it.'
    return text

def trained_turbo4(items):
    return any(x['weight'] and Path(x['path']).name.lower()==REF2VA_TURBO4 for x in items)

def profile(path):
    name=Path(path).name.lower()
    if 'character_swap' in name:return 'character_swap'
    if 'vfx_edit' in name:return 'vfx_ffp' if 'ffp' in name else 'vfx_edit'
    return 'custom'

def validate(items):
    if not isinstance(items,list) or len(items)>8:raise ValueError('Video: seleziona fino a otto LoRA.')
    result=[];seen=set()
    for item in items:
        if not isinstance(item,dict) or set(item)-{'path','weight'}:raise ValueError('LoRA video non valido.')
        from .external_models import absolute_path
        path=absolute_path(item.get('path',''));weight=item.get('weight',1)
        if type(weight) not in (int,float) or not math.isfinite(weight) or not -2<=weight<=2:raise ValueError('Peso LoRA video: da -2 a 2.')
        key=str(path).casefold()
        if key in seen:raise ValueError('LoRA video duplicato.')
        seen.add(key)
        traits=inspect(path)
        if not traits or traits['family']!='minimax-h3':raise ValueError('Seleziona un LoRA MiniMax H3 safetensors valido.')
        result.append({'path':str(path),'weight':float(weight)})
    return result

def aligned(items):
    return any(x['weight'] and profile(x['path'])!='custom' for x in items)

def validate_pdd_combination(items):
    # Editing adapters can share PDD's trunk. Another distillation adapter
    # cannot: it assumes a different sampling trajectory and output head.
    if any(x['weight'] and profile(x['path'])=='custom' for x in items):
        raise ValueError('Con PDD usa solo Character Swap o VFX Edit. Rimuovi DMD, Turbo e gli altri LoRA non verificati.')

def choices(app):
    if not getattr(app,'loras',None):return []
    return [x|{'profile':profile(x['path'])} for x in app.loras.scan(app.store.settings().get('lora_dirs',[]))['items'] if x['family']=='minimax-h3']

def prepare_plan(plan,items,source):
    active=[x for x in items if x['weight']]
    specialized=[profile(x['path']) for x in active if profile(x['path'])!='custom']
    if specialized and not source:raise ValueError('Questo LoRA richiede Modifica video con una sorgente allineata.')
    if 'character_swap' in specialized and not plan['images']:raise ValueError('Character Swap richiede almeno una immagine del personaggio.')
    result=dict(plan)
    if specialized:
        trigger='body_swap:' if 'character_swap' in specialized else 'vfx_edit:'
        text=re.sub(r'^\s*(?:body_swap:|vfx_edit:)\s*','',plan['prompt'],flags=re.I)
        request=re.search(r'REQUESTED CHANGES:\s*(.*?)(?=\n<Picture\s+\d+>:|\nReference pictures|\Z)',text,re.S)
        if request:text=request[1].strip()+' Preserve the source performance, timing, pose, camera, composition and all unrequested attributes.'
        text=re.sub(r'<Video\s+1>','the aligned source clip',text,flags=re.I)
        result['prompt']=trigger+' '+text
        # FFP/Character Swap use appearance through native image references;
        # the full source video already occupies the aligned guide channel.
        result['images']=[dict(x,role='reference',seconds=0) for x in plan['images']]
    return result

def apply(model,items,progress=None,*,merge=True):
    if not any(x['weight'] for x in items):return model,[]
    import comfy.lora,comfy.lora_convert,comfy.utils
    from .video_pdd import merge_trunk_once
    reports=[]
    for item in validate(items):
        if not item['weight']:continue
        state=comfy.utils.load_torch_file(item['path'],safe_load=True)
        state=comfy.lora_convert.convert_lora(state)
        mapping=comfy.lora.model_lora_keys_unet(model.model,{})
        from .lora_families import targets
        layers=targets({k:{'shape':list(v.shape)} for k,v in state.items()})
        if not layers:raise ValueError('Formato LoRA H3 non riconosciuto dal runtime.')
        for key,(out_size,in_size,adapter_format) in layers.items():
            target=mapping.get(key)
            if not target:raise ValueError('LoRA incompatibile: tensore senza corrispondenza '+key)
            shape=comfy.utils.get_attr(model.model,target).shape
            if out_size!=shape[0] or in_size!=shape[1]:
                raise ValueError('LoRA incompatibile con questo checkpoint: '+key)
        patches=comfy.lora.load_lora(state,mapping)
        patched=model.clone();accepted=patched.add_patches(patches,item['weight'])
        if len(accepted)!=len(patches) or not accepted:raise ValueError('Il runtime non ha applicato tutti i tensori del LoRA.')
        count=merge_trunk_once(patched,progress) if merge else 0
        reports.append({'file':Path(item['path']).name,'weight':item['weight'],'profile':profile(item['path']),
                        'prepared_patch_keys':len(accepted),'merged_patch_keys':count,
                        'merge_deferred_to_pdd':not merge})
        model=patched
        del state,patches
    return model,reports

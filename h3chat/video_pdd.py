"""Optional Alibaba PDD loading; never reinterpret it as an ordinary LoRA."""
import json,struct
from pathlib import Path

def check_header(path):
    with Path(path).open('rb') as stream:
        prefix=stream.read(8)
        if len(prefix)!=8:raise ValueError('Header PDD incompleto.')
        size=struct.unpack('<Q',prefix)[0]
        if not 2<=size<=16*1024**2:raise ValueError('Header PDD non valido.')
        try:header=json.loads(stream.read(size))
        except (ValueError,UnicodeError):raise ValueError('Header PDD non valido.')
    expected={'proj_out.weight':[32,96,5376],'proj_out.bias':[32,96],
              'audio_proj_out.weight':[32,32,5376],'audio_proj_out.bias':[32,32]}
    if not isinstance(header,dict) or any(not isinstance(header.get(key),dict) or header[key].get('shape')!=shape for key,shape in expected.items()):
        raise ValueError('Il file non è un adattatore Alibaba PDD 8 passi completo: mancano le proiezioni video/audio. Non usare un LoRA Turbo ordinario qui.')

def validate(parameters):
    enabled=parameters.get('pdd_enabled',False)
    if type(enabled) is not bool:raise ValueError('PDD: scegli attivo o disattivo.')
    path=parameters.get('pdd_lora','')
    if not isinstance(path,str) or len(path)>4096:raise ValueError('Percorso PDD non valido.')
    if path:
        from .external_models import absolute_path
        if absolute_path(path).suffix.lower()!='.safetensors':raise ValueError('PDD richiede un file safetensors.')
    if not enabled:return
    if not path:raise ValueError('Seleziona l’adattatore PDD prima di attivarlo.')
    from .external_models import valid_weight
    if not valid_weight(Path(path)):raise ValueError('Adattatore PDD assente o non valido.')
    check_header(path)
    if parameters.get('steps')!=8 or parameters.get('sampler')!='euler' or parameters.get('cfg')!=1 or parameters.get('shift_video')!=12 or parameters.get('shift_audio')!=3:
        raise ValueError('PDD richiede 8 passi, sampler Euler, CFG 1 e shift video/audio 12/3. Disattiva PDD per usare 12, 16 o 20 passi standard.')

def merge_trunk_once(patcher,progress=None):
    """Commit runtime-only quant-aware patches one module at a time.

    The worker owns a disposable model. Retaining restoration backups or
    dequantizing and reapplying LoRA on every MLP chunk defeats low-VRAM
    inference. Use Comfy's normal requantization setter, then return each
    changed parameter to CPU before proceeding. No checkpoint is written.
    """
    import comfy.utils
    if patcher.backup or patcher.loaded_size():
        raise ValueError('PDD deve essere preparato su un diffusore nuovo, prima del caricamento GPU.')
    keys=list(patcher.patches)
    for index,key in enumerate(keys):
        patcher.patch_weight_to_device(key,device_to=patcher.load_device)
        weight=comfy.utils.get_attr(patcher.model,key)
        comfy.utils.set_attr_param(patcher.model,key,weight.to(device='cpu'))
        del weight
        patcher.backup.pop(key,None)
        patcher.patches.pop(key)
        if progress and (index==0 or (index+1)%32==0 or index+1==len(keys)):
            progress(index+1,len(keys))
    return len(keys)

def apply(model,parameters,progress=None):
    """Apply both the quant-aware trunk patches and the trained head bank."""
    validate(parameters)
    if not parameters.get('pdd_enabled'):return model,None,{}
    import folder_paths
    from .vendor_pdd.nodes import MiniMaxH3PDDAccApply
    path=Path(parameters['pdd_lora']).resolve()
    folder_paths.add_model_folder_path('pdd_acc',str(path.parent),is_default=True)
    resolved=folder_paths.get_full_path_or_raise('pdd_acc',path.name)
    if Path(resolved).resolve()!=path:raise ValueError('Percorso PDD ambiguo: scegli un file con nome univoco.')
    patched,sigmas,info=MiniMaxH3PDDAccApply().apply(model,path.name,8,1.0,1.0,'error',partition_check='warn')
    count=merge_trunk_once(patched,progress)
    return patched,sigmas,{'active':True,'file':path.name,'steps':8,'sampler':'euler','cfg':1,'info':info,'experimental_hybrid':True,
                          'trunk_merged_once':True,'merged_patch_keys':count,'checkpoint_modified':False}

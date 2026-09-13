"""MTP detection for the pinned llama.cpp b10809, using actual GGUF tensors.

Sources and runtime limitations: docs/mtp.md. No model-name guessing and no
separate draft model: native MTP shares the weights of the selected model.
"""

# These architectures have a DECODER_MTP graph in b10809. Most implement one head.
ARCHITECTURES = {'qwen35', 'qwen35moe', 'qwen3next', 'deepseek2', 'deepseek4',
                 'glm4moe', 'glm-dsa', 'nemotron_h_moe', 'step35', 'hy_v3'}
MULTI_HEAD = {'step35', 'hy_v3'}


def inspect_mtp(root, model, info, ready):
    from .models import metadata, model_path
    arch=info.get('general.architecture','')
    count=info.get(arch+'.nextn_predict_layers',0)
    blocks=info.get(arch+'.block_count',0)
    result={'supported':False,'layers':0,'max_draft_tokens':8,'note':''}
    def unavailable(note):
        return result|{'note':note}
    if not ready:
        return unavailable('MTP da verificare: installa o ricollega tutti i file del modello.')
    if type(count) is not int or count<=0:
        return unavailable('Questo GGUF non dichiara moduli MTP (NextN).')
    if arch not in ARCHITECTURES or (count!=1 and arch not in MULTI_HEAD):
        return unavailable('MTP dichiarato, ma questa architettura o il numero di moduli non è supportato dal motore integrato.')
    if type(blocks) is not int or not 0<count<blocks<=1024:
        return unavailable('Metadati MTP incompleti o non validi.')
    names=set()
    entries=[e for e in model['files'] if e['role'] in ('model','shard')]
    for entry in entries:
        part=metadata(model_path(root,model,entry['path']))
        if not part.get('_h3_tensor_scan_ok'):
            return unavailable('Impossibile verificare i tensori MTP: intestazione GGUF incompleta o troppo grande.')
        names.update(part.get('_h3_tensor_names',()))
    if 'blk.0.attn_norm.weight' not in names or 'token_embd.weight' not in names:
        return unavailable('Il file sembra contenere solo il modulo MTP. Collega un GGUF completo, con modello e moduli MTP incorporati.')
    required={f'blk.{i}.nextn.{tensor}.weight' for i in range(blocks-count,blocks)
              for tensor in ('eh_proj','enorm','hnorm')}
    if not required<=names:
        return unavailable('MTP dichiarato, ma i tensori NextN sono assenti o incompleti nei file collegati. Usa una conversione GGUF che li includa.')
    limit=min(8,count) if arch in MULTI_HEAD else 8
    return result|{'supported':True,'layers':count,'max_draft_tokens':limit,
                   'note':'MTP disponibile: moduli NextN presenti nel GGUF. Il motore ne verifica l’attivazione al caricamento.'}


def mtp_tokens(model, settings):
    traits=model.get('mtp',{})
    if not settings.get('mtp_enabled',False) or not traits.get('supported',False):
        return 0
    return min(int(settings.get('mtp_draft_tokens',3)),traits.get('max_draft_tokens',8))

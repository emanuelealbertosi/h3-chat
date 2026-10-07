"""Offline official EmbeddingGemma 2 checkpoints and retrieval formatting."""
import json
from pathlib import Path
from .rag_profiles import visual_enabled

FORMAT_VERSION='embeddinggemma2-native-mean-768-v1'
DIMENSIONS=768

def checkpoint(path):
    folder=Path(path)
    if not folder.is_absolute() or not folder.is_dir():raise ValueError('Scegli la cartella locale di EmbeddingGemma 2.')
    try:
        config=json.loads((folder/'config.json').read_text(encoding='utf-8'))
        if not isinstance(config,dict) or config.get('model_type')!='embedding_gemma2' or config.get('text_config',{}).get('embedding_dim')!=DIMENSIONS:raise ValueError()
        names=['model.safetensors','config.json','tokenizer.json','tokenizer_config.json','processor_config.json','preprocessor_config.json']
        files=[folder/name for name in names]
        if not all(p.is_file() and p.stat().st_size>0 for p in files):raise ValueError()
    except (OSError,ValueError,TypeError) as error:
        raise ValueError('Cartella EmbeddingGemma 2 incompleta o incompatibile: servono pesi safetensors, configurazione, tokenizer e processor ufficiali.') from error
    return folder.resolve(),files

def formatted(text,query=False,image=False):
    # Instructions apply to text only. The placeholder marks image tokens.
    prefix='task: search result | query: ' if query else 'title: none | text: '
    return prefix+text if not image else '<|image|>'+(' '+prefix+text if text else '')

def runtime_ready(root):
    root=Path(root)
    return all((root/path).is_file() for path in (
        'runtime/vision/packages/torch/__init__.py',
        'runtime/embeddinggemma2/packages/transformers/models/embedding_gemma2/modeling_embedding_gemma2.py',
        'runtime/embeddinggemma2/packages/tokenizers/__init__.py',
        'runtime/embeddinggemma2/packages/huggingface_hub/__init__.py'))

def memory_assessment(settings,hardware):
    if settings.get('rag_embedding_profile')!='embeddinggemma2' or not settings.get('rag_embedding_model'):return None
    checkpoint(settings['rag_embedding_model'])
    gpu=settings.get('rag_device')=='gpu';parameters=440e6 if visual_enabled(settings) else 270e6
    # FP32 is safe everywhere; BF16 may reduce this conservative GPU estimate.
    weights=parameters*4/1024**3;required=round(weights+1,1)
    result={'status':'ok','title':'OK stimato · EmbeddingGemma 2','ram_gb':required,'vram_gb':required if gpu else 0,
            'advice':'Pesi completi 740M. Il RAG carica solo testo e, se attivo, Vision; il modulo audio resta scaricato. BF16 su GPU compatibili, FP32 altrove. Il processo viene chiuso dopo la ricerca.'}
    free=hardware.get('ram',{}).get('free_mb')
    if free is None:result.update(status='unknown',title='RAM libera non rilevata')
    elif required>max(0,free/1024-.5):result.update(status='oom',title='Rischio OOM · EmbeddingGemma 2')
    if gpu:
        devices=[g for g in hardware.get('gpu',[]) if g.get('vendor')=='NVIDIA']
        if len(devices)!=1 or devices[0].get('free_mb') is None:
            if result['status']!='oom':result.update(status='unknown',title='VRAM non misurabile')
        elif required>max(0,devices[0]['free_mb']/1024-.5):result.update(status='oom',title='Rischio OOM GPU · EmbeddingGemma 2')
    return result

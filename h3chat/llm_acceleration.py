"""Opt-in, isolated Qwen27B runtime; process ownership stays in Session."""
from functools import lru_cache
import hashlib
import json
import os
from pathlib import Path
import re

FOLDER = 'runtime/accelerators/qwen27-mtp-555d1ec-window8k'
FILENAME = 'Qwen3.8-27B-GSQ-RCO-IQ3_S-mtp.gguf'
MODEL_BYTES = 12120016960
ORCA_FILENAME = 'Qwen3.8-27B-OrcaRouter-GSQ-RCO-IQ3_XXS-v2.0-qatfa.gguf'
ORCA_BYTES = 10442846464
PROFILES = {
    'ista-iq3s': {'filename': FILENAME, 'bytes': MODEL_BYTES, 'name': 'ISTA IQ3_S',
                  'draft': 2, 'ubatch': 256, 'vision_ubatch': 128, 'free_mib': 15550},
    'orca-iq3xxs': {'filename': ORCA_FILENAME, 'bytes': ORCA_BYTES, 'name': 'Orca IQ3_XXS',
                    'draft': 4, 'ubatch': 512, 'vision_ubatch': 512, 'free_mib': 15000},
}
WINDOW = 8192
REQUIRED_FREE_MIB = 15550
# The reference threshold includes a safety reserve. Permit only small desktop
# fluctuations within it, keeping context, cache, GPU layers and draft unchanged.
PREFLIGHT_TOLERANCE_MIB = 128
TARGET_KV_BYTES_PER_TOKEN = 16 * 4 * (256 + 256) * (18 / 32)
RUNTIME_FILES = ('llama-server.exe', 'llama-server-impl.dll', 'llama-common.dll',
                 'llama.dll', 'ggml.dll', 'ggml-base.dll', 'ggml-cpu.dll',
                 'ggml-cuda.dll', 'mtmd.dll', 'cublas64_12.dll',
                 'cublasLt64_12.dll', 'cudart64_12.dll', 'vcomp140.dll',
                 'msvcp140.dll', 'vcruntime140.dll', 'vcruntime140_1.dll')


def model_profile(model):
    files = [f for f in model.get('files', []) if f.get('role') == 'model']
    p = model.get('parameters') or {}
    valid = (not model.get('api') and len(files) == 1
            and not any(f.get('role') == 'shard' for f in model.get('files', []))
            and (model.get('identity') or {}).get('architecture') == 'qwen35'
            and all(p.get(k) == v for k, v in
                    {'layers': 65, 'embedding': 5120, 'heads': 24, 'kv_heads': 4}.items())
            and (model.get('mtp') or {}).get('supported', False))
    if valid:
        for key, profile in PROFILES.items():
            if (Path(files[0].get('path') or '').name == profile['filename']
                    and files[0].get('size') == profile['bytes']):
                return key
    return None


def eligible(model):
    return model_profile(model) is not None


def traits(root, model):
    key = model_profile(model)
    profile = PROFILES.get(key)
    supported = profile is not None
    installed = (Path(root) / FOLDER / 'manifest.json').is_file()
    return {'supported': supported, 'installed': installed, 'profile': key,
            'draft_tokens': profile['draft'] if supported else None,
            'label': 'Qwen27B ' + profile['name'] + ' ottimizzato' if supported else 'Qwen27B ottimizzato',
            'note': (f"Profilo {profile['name']}: CUDA RTX 50, tutti i layer GPU, MTP{profile['draft']}, "
                     f"Vision CPU, fino a 128K. Cache della sola bozza MTP 8K; contesto principale completo. "
                     f"Servono almeno {profile['free_mib']} MiB VRAM liberi a 128K "
                     f"({required_free_mib(65536, key)} a 64K)."
                     if supported else 'Ottimizzazione riservata ai GGUF ISTA IQ3_S e Orca IQ3_XXS verificati; gli altri modelli usano il motore standard.')}


def stamp(root):
    folder = Path(root) / FOLDER
    result = []
    for name in ('manifest.json', *RUNTIME_FILES):
        try:
            st = (folder / name).stat()
            result.append((name, st.st_size, st.st_mtime_ns))
        except OSError:
            result.append((name, None, None))
    return tuple(result)


@lru_cache(maxsize=4)
def _verified(folder, fingerprint):
    folder = Path(folder)
    try:
        manifest = json.loads((folder / 'manifest.json').read_text(encoding='utf-8'))
        if manifest.get('profile') != 'qwen27-iq3s-mtp2-window8k' or set(manifest['sha256']) != set(RUNTIME_FILES):
            raise ValueError('Manifest del motore non valido.')
        for name in RUNTIME_FILES:
            with (folder / name).open('rb') as stream:
                digest = hashlib.file_digest(stream, 'sha256').hexdigest()
            if digest != manifest['sha256'][name]:
                raise ValueError('Libreria modificata: ' + name)
    except (OSError, KeyError, ValueError) as exc:
        raise ValueError('Motore Qwen27B incompleto o modificato. Ripristinalo oppure scegli Standard. ' + str(exc)) from exc
    return str(folder / 'llama-server.exe')


def plan(root, model, settings, files):
    if settings.get('llm_acceleration', 'standard') == 'standard':
        return None
    key = model_profile(model)
    if key is None:
        raise ValueError('Il profilo ottimizzato richiede un GGUF ISTA IQ3_S o Orca IQ3_XXS verificato. Scegli Standard per questo modello.')
    profile = PROFILES[key]
    if _model_size(files['model']) != profile['bytes']:
        raise ValueError('Il GGUF del profilo ottimizzato e cambiato o incompleto.')
    if settings['profile'] == 'cpu' or settings['backend'] != 'cuda':
        raise ValueError('Il profilo Qwen27B ottimizzato richiede CUDA NVIDIA.')
    if settings.get('memory_policy') != 'resident' and settings['gpu_layers'] < 66:
        raise ValueError('Il profilo ottimizzato richiede tutti i layer GPU (99 o 999).')
    if not settings.get('mtp_enabled') or settings.get('mtp_draft_tokens') != profile['draft']:
        raise ValueError(f"Il profilo {profile['name']} verificato richiede MTP attivo con {profile['draft']} token.")
    if not 16384 <= settings['context'] <= 131072:
        raise ValueError('Il profilo ottimizzato supporta contesti verificabili da 16K a 128K. Standard resta disponibile.')
    if 'mmproj' in files and settings.get('vision_device', 'cpu') != 'cpu':
        raise ValueError('Per questo profilo scegli Vision CPU oppure disattiva Vision.')
    if os.name != 'nt':
        raise ValueError('Il runtime ottimizzato locale e disponibile solo su Windows.')
    folder = (Path(root) / FOLDER).resolve()
    exe = _verified(str(folder), stamp(root))
    return {'exe': exe, 'profile': key, 'draft': profile['draft'], 'batch': 2048,
            'ubatch': profile['vision_ubatch'] if 'mmproj' in files else profile['ubatch'],
            'window': WINDOW, 'label': f"Qwen27B {profile['name']} · Q4 · MTP{profile['draft']} · bozza 8K"}


def _model_size(path):
    return Path(path).stat().st_size


def required_free_mib(context=131072, profile='ista-iq3s'):
    if type(context) is not int or not 16384 <= context <= 131072:
        raise ValueError('Contesto ottimizzato fuori intervallo 16K–128K.')
    # Keep the measured 128K safety margin; subtract only the exact target Q4 KV
    # allocation saved by an explicitly selected smaller context. Draft unchanged.
    saved = int((131072 - context) * TARGET_KV_BYTES_PER_TOKEN / 1024**2)
    return PROFILES[profile]['free_mib'] - saved


def estimate(model, settings, hardware, references=1):
    """Scoped hybrid Q4 estimate; never suggest partial offload for this profile."""
    context=settings['context']
    key=model_profile(model)
    profile=PROFILES.get(key,PROFILES['ista-iq3s'])
    vision=bool(settings.get('vision_enabled',True) and model.get('vision',{}).get('enabled'))
    projector=model.get('vision',{}).get('projector_size',0)/1024**3 if vision else 0
    # Sixteen full-attention target blocks, Q4_0 rows (18 bytes per 32 values).
    kv=context*TARGET_KV_BYTES_PER_TOKEN/1024**3
    workspace=(9560.20+748.12+720.28+9+140.28+700 if key=='orca-iq3xxs'
               else 11159.69+448.88+(564.27 if vision else 616.27)+9+97.27+700)
    vram=workspace/1024+kv
    ram=profile['bytes']/1024**3+projector*1.2+3+(min(references,8)*.25 if vision else 0)
    gpus=[g for g in hardware['gpu'] if g.get('vendor')=='NVIDIA']
    gpu=gpus[0] if len(gpus)==1 else None
    compatible=(eligible(model) and settings['profile']!='cpu' and settings['backend']=='cuda'
                and (settings.get('memory_policy')=='resident' or settings['gpu_layers']>=66)
                and settings.get('mtp_enabled') and settings.get('mtp_draft_tokens')==profile['draft']
                and 16384<=context<=131072 and (not vision or settings.get('vision_device','cpu')=='cpu'))
    status='ok';title='Profilo Qwen27B ottimizzato';advice='Cache principale Q4 e sola bozza MTP 8K. Margine stretto: evitare altri carichi GPU.';risk=False;patch={}
    if not compatible or (gpu and not re.search(r'RTX\s*50\d\d',gpu['name'],re.I)):
        status='unknown';title='Profilo non compatibile';advice=f"Richiede GGUF verificato, CUDA RTX 50, tutti i layer GPU, MTP{profile['draft']} e Vision CPU. Altrimenti scegli Standard.";patch={'llm_acceleration':'standard'}
    elif not gpu or gpu.get('free_mb') is None or hardware['ram'].get('free_mb') is None:
        status='unknown';title='Memoria non determinabile';advice='Verificare la GPU e la memoria libera prima di avviare questo profilo.'
    elif gpu['free_mb']<required_free_mib(context,key)-PREFLIGHT_TOLERANCE_MIB or hardware['ram']['free_mb']<max(16*1024,(ram+.75)*1024):
        status='oom';title='Memoria libera insufficiente';advice='Libera gli altri modelli. Questo profilo non applica offload parziale o riduzione automatica del contesto.';risk=True
    elif gpu['free_mb']<required_free_mib(context,key):
        status='warning';title='Margine VRAM stretto';advice=f"Mancano {required_free_mib(context,key)-gpu['free_mb']:.0f} MiB alla soglia prudenziale. È consentito un tentativo entro {PREFLIGHT_TOLERANCE_MIB} MiB del margine di riserva, mantenendo contesto e layer GPU.";risk=True
    return {'id':model['id'],'name':model['name'],'status':status,'title':title,'advice':advice,
            'oom_risk':risk,'ram_gb':round(ram,2),'vram_gb':round(vram,2),'cpu_ram_gb':round(ram+vram,2),
            'gpu_name':gpu['name'] if gpu else None,'recommended_patch':patch,
            'assumptions':[f'Stima dedicata: cache Q4 principale su 16 blocchi attenzione per {context} token; bozza MTP indipendente 8192.',
                           f"Comprende stato ricorrente MTP{profile['draft']}, workspace e margine runtime; non e una misurazione o garanzia del picco.",
                           'Il processo resta nella catena: in A richiesta viene chiuso prima del prossimo modello.']}


def check_hardware(context=131072, profile='ista-iq3s', *, stage=None):
    from .hardware import detect_hardware
    hardware = detect_hardware(refresh=True)
    gpus = [g for g in hardware['gpu'] if g.get('vendor') == 'NVIDIA']
    if len(gpus) != 1 or not re.search(r'RTX\s*50\d\d', gpus[0]['name'], re.I):
        raise ValueError('Questo runtime CUDA sm_120 richiede una sola GPU NVIDIA RTX 50. Usa Standard per altro hardware.')
    required = required_free_mib(context,profile)
    free=gpus[0].get('free_mb') or 0
    if free < required-PREFLIGHT_TOLERANCE_MIB:
        raise ValueError(f'VRAM insufficiente per Qwen27B ottimizzato a {context} token: liberi {free:.0f} MiB, soglia prudenziale {required} MiB, differenza {required-free:.0f} MiB. Libera memoria nelle altre applicazioni o scegli esplicitamente un contesto inferiore. Il contesto e i layer GPU non vengono ridotti automaticamente.')
    ram_free=hardware['ram'].get('free_mb')
    if ram_free is None:raise ValueError('Impossibile rilevare la RAM disponibile per Qwen27B ottimizzato.')
    if ram_free < 16 * 1024:
        raise ValueError(f'RAM insufficiente per Qwen27B ottimizzato: disponibili {ram_free/1024:.2f} GiB, richiesti almeno 16 GiB al caricamento, mancanti {16-ram_free/1024:.2f} GiB. Libera memoria nelle altre applicazioni o usa A richiesta. Contesto e layer GPU restano invariati.')
    if free<required and stage:
        stage(f'Margine VRAM stretto · {free:.0f} MiB liberi · soglia prudenziale {required} · caricamento con contesto {context} invariato')


def child_environment(optimized=None):
    env = os.environ.copy()
    for key in ('QWEN27_MTP_WINDOW', 'QWEN27_MTP_Q4_VEC'):
        env.pop(key, None)
    if optimized:
        env['QWEN27_MTP_WINDOW'] = str(optimized['window'])
        env['GGML_CUDA_GRAPH_OPT'] = '0'
        env.pop('GGML_CUDA_DISABLE_GRAPHS', None)
        env['PATH'] = str(Path(optimized['exe']).parent) + os.pathsep + env.get('PATH', '')
    return env

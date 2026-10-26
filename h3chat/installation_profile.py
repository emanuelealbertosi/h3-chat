"""Optional first-run defaults for the lightweight Windows API installation.

This marker is an installer preference, never a restriction on later local use.
It contains no paths to model weights, credentials or user data.
"""
import json
from pathlib import Path


API_SETTINGS = {
    'profile': 'cpu', 'backend': 'cpu', 'gpu_layers': 0,
    'llm_device': 'cpu', 'image_device': 'cpu', 'rag_device': 'cpu',
    'asr_device': 'cpu', 'vision_device': 'cpu', 'music_backend': 'cpu',
    'chat_model': '', 'create_model': '', 'edit_model': '',
    'diagram_model': '', 'music_model': '', 'video_model': '', 'music_quality': 'model',
    'llm_acceleration': 'standard', 'mtp_enabled': False,
    'memory_policy': 'on_demand', 'ram_cache_gb': 0,
    'transcribe_auto': False, 'voice_auto': False,
}


def write_profile(root, api_only):
    """Record install intent; never open or change an existing user database."""
    target = Path(root) / 'runtime/installation-profile.json'
    target.parent.mkdir(parents=True, exist_ok=True)
    part = target.with_suffix('.writing')
    part.write_text(json.dumps({'version': 1, 'mode': 'api' if api_only else 'standard'}), encoding='utf-8')
    part.replace(target)


def first_run_settings(root, database_existed):
    """A reinstall must not change any saved settings, including provider choices."""
    if database_existed:
        return {}
    from .platform_runtime import is_macos,is_linux
    if is_macos():
        return API_SETTINGS|{'profile':'low','backend':'metal','gpu_layers':20,'execution_mode':'gpu','llm_device':'inherit','vision_enabled':False,'lab_auto':False}
    if is_linux():return API_SETTINGS|{'profile':'low','backend':'cpu','gpu_layers':0,'execution_mode':'gpu','llm_device':'cpu','vision_enabled':False,'lab_auto':False}
    try:
        value = json.loads((Path(root) / 'runtime/installation-profile.json').read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return {}
    return dict(API_SETTINGS) if value == {'version': 1, 'mode': 'api'} else {}

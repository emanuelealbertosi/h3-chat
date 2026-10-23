"""Accept an explicitly authored storyboard without any LLM planning pass."""
import json
import re
from .video_options import validate_plan

MARKER = re.compile(r'^```h3-storyboard[ \t]*\r?\n(.*?)^```[ \t]*$', re.M | re.S)


def read(prompt):
    matches = list(MARKER.finditer(prompt))
    if not matches:
        if re.search(r'^```h3-storyboard\b', prompt, re.M):
            raise ValueError('Il piano video diretto non è chiuso correttamente.')
        return None
    if len(matches) != 1:
        raise ValueError('Inserisci un solo piano video diretto.')
    try:
        value = json.loads(matches[0][1])
    except (ValueError, TypeError) as exc:
        raise ValueError('Il piano video diretto contiene JSON non valido.') from exc
    if not isinstance(value, dict) or set(value) != {'style', 'shots'}:
        raise ValueError('Il piano video diretto richiede style e shots.')
    return value


def request_text(prompt):
    """Only the human header defines total duration/count, not JSON strings."""
    return MARKER.sub('', prompt).strip()


def attachment_plan(refs, soundtrack, duration):
    images = [r for r in refs if r['mime'].startswith('image/')]
    audios = [r for r in refs if r['mime'].startswith('audio/')]
    plan = {'prompt': 'Pre-authored reference music video; preserve the original soundtrack.',
            'images': [{'index': i, 'role': 'reference', 'seconds': 0}
                       for i in range(1, len(images) + 1)],
            'audios': [{'index': i, 'role': 'lipsync' if r['id'] == soundtrack['id'] else 'reference', 'start': 0}
                       for i, r in enumerate(audios, 1)]}
    return validate_plan(plan, refs, min(15, duration))

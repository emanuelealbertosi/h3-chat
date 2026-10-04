"""Higgs speech controls adapted from H3-Audio (MIT; licenses/H3-Audio-MIT.txt)."""
import re
import unicodedata
TAGS = {
    'emotion': 'affection amusement anger arousal awe bitterness confusion contemplation contentment determination disgust elation enthusiasm fear helplessness longing pride relief sadness shame surprise'.split(),
    'prosody': 'speed_very_slow speed_slow speed_fast speed_very_fast pitch_low pitch_high expressive_high expressive_low pause long_pause'.split(),
    'style': 'singing shouting whispering'.split(),
    'sfx': 'cough laughter crying screaming burping humming sigh sniff sneeze'.split(),
}
TAG_RE = re.compile(r'<\|([a-z_]+):([a-z_]+)\|>')
def normalize(text):
    return ''.join(c for c in unicodedata.normalize('NFKD', text.lower()) if not unicodedata.combining(c))


RULES = [
    (r'\b(sensuale|sensual|intim[oa]|intimate|seducente)\b', ['emotion:affection', 'prosody:speed_slow']),
    (r'\b(sussurra\w*|sussurro|whisper\w*)\b', ['style:whispering']),
    (r'\b(giovanile|giovane|youthful|brillante|vivace)\b', ['prosody:expressive_high']),
    (r'\b(senior|anziana|anziano|matura|maturo)\b', ['prosody:speed_slow']),
    (r'\b(profond[oa]|grave|deep|bassa|basso)\b', ['prosody:pitch_low']),
    (r'\b(acut[oa]|alta|alto|high.pitched)\b', ['prosody:pitch_high']),
    (r'\b(lent[oa]|lentamente|slow\w*|calm[oa])\b', ['prosody:speed_slow']),
    (r'\b(veloce|rapido|rapida|fast|energic[oa])\b', ['prosody:speed_fast']),
    (r'\b(entusias\w*|allegro|allegra|gioios[oa])\b', ['emotion:enthusiasm']),
    (r'\b(triste|malinconic[oa]|sad)\b', ['emotion:sadness']),
    (r'\b(arrabbiat[oa]|rabbia|angry)\b', ['emotion:anger']),
    (r'\b(affettuos[oa]|dolce|gentile|cald[oa]|caloroso|calorosa|warm)\b', ['emotion:affection']),
    (r'\b(decis[oa]|autorevole|determinato|determinata)\b', ['emotion:determination']),
    (r'\b(neutr[oa]|neutral|sobri[oa]|piatt[oa])\b', ['prosody:expressive_low']),
    (r'\b(espressiv[oa]|espressivita|expressive|teatrale)\b', ['prosody:expressive_high']),
]


def valid_tags(text):
    for match in TAG_RE.finditer(text):
        if match[2] not in TAGS.get(match[1], []):
            raise ValueError(f'Tag non supportato: {match[0]}')
    leftovers = TAG_RE.sub('', text)
    if '<|' in leftovers or '|>' in leftovers:
        raise ValueError('Tag incompleto o non valido nel testo.')


def direction(prompt='', traits=None, base=None):
    """Transparent deterministic compiler; never puts free instructions in speech."""
    selected = list(base or [])
    matched = []
    text = normalize(prompt)
    hits = sorted((m.start(), m, values) for pattern, values in RULES for m in re.finditer(pattern, text))
    for _, match, values in hits:
        prefix = text[max(0, match.start() - 50):match.start()]
        if re.search(r'(?:\bnon|\bsenza|\bno|\bnot)\s+(?:(?:troppo|essere|molto|parlare|con|tono|una?|voce)\s+)*$', prefix):
            selected = [tag for tag in selected if tag not in values]
            continue
        selected.extend(values)
        matched.append(match[0])
    for trait, intensity in (traits or {}).items():
        if float(intensity) >= 35:
            for pattern, values in RULES:
                if re.search(pattern, normalize(trait)):
                    selected.extend(values)
    explicit = TAG_RE.findall(prompt)
    selected.extend(':'.join(pair) for pair in explicit if pair[1] in TAGS.get(pair[0], []))
    # Last choice wins for mutually exclusive controls.
    grouped = {}
    for tag in selected:
        cat, val = tag.split(':', 1)
        if val not in TAGS.get(cat, []) or val in {'pause', 'long_pause'} or cat == 'sfx':
            continue
        key = f'prosody:{val.split("_")[0]}' if cat == 'prosody' else cat
        grouped[key] = tag
    applied = list(grouped.values())
    return {'tags': applied, 'prefix': ''.join(f'<|{tag}|>' for tag in applied),
            'matched': sorted(set(matched)), 'mode': 'local',
            'note': 'Le caratteristiche sono indicazioni di recitazione. Età e timbro dipendono dal campione; i livelli selezionano i controlli disponibili, senza fondere identità vocali.'}


def split_text(text, limit=280):
    """Partition every character, preferring sentence boundaries, never cutting tags."""
    valid_tags(text)
    chunks = []
    remaining = text
    while remaining:
        if len(remaining) <= limit:
            chunks.append(remaining)
            break
        boundary = limit
        for match in TAG_RE.finditer(remaining):
            if match.start() < boundary < match.end():
                boundary = match.start() or match.end()
                break
        window = remaining[:boundary]
        endings = list(re.finditer(r'[.!?;:][”"\']?\s+|\n+', window))
        if endings and endings[-1].end() >= limit // 3:
            boundary = endings[-1].end()
        elif ' ' in window:
            pos = window.rfind(' ') + 1
            if pos >= limit // 3:
                boundary = pos
        chunks.append(remaining[:boundary])
        remaining = remaining[boundary:]
    return chunks


def apply_direction(text, prefix):
    if not prefix:
        return text
    # Repeat sentence-level controls without altering any spoken character.
    return prefix + re.sub(r'([.!?][\u201d\"\u0027]?\s+)(?=\S)', lambda m: m[0] + prefix, text)



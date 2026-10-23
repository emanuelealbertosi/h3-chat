"""Bind storyboard image aliases to the selected clip's actual Picture slots."""
import re

LABEL=re.compile(r'<(?:Picture|Image|Immagine)\s+(\d+)>|\b(?:Picture|Image|Immagine)[ \t]+#?[ \t]*(\d+)\b',re.I)


def normalize(text):
    return LABEL.sub(lambda m:f'<Picture {int(m[1] or m[2])}>',text)


def indices(text):
    return {int(m[1] or m[2]) for m in LABEL.finditer(text)}


def remap(text,mapping):
    def replace(match):
        index=int(match[1] or match[2])
        if index not in mapping:raise ValueError('Immagine non selezionata nell’inquadratura.')
        return f'<Picture {mapping[index]}>'
    return LABEL.sub(replace,text)


def style_for_clip(style,mapping):
    # Older saved storyboards contain a global cast/location roster in style.
    # Keep common aesthetics and selected subjects; never carry dangling global
    # image numbers or unrelated single-subject definitions into a local clip.
    sentences=re.split(r'(?<=[.!?])\s+|\n+',style)
    kept=[]
    for sentence in sentences:
        labels=indices(sentence)
        if labels and not labels.intersection(mapping):continue
        def replace(match):
            index=int(match[1] or match[2])
            return f'<Picture {mapping[index]}>' if index in mapping else ''
        text=LABEL.sub(replace,sentence)
        text=re.sub(r'\(\s*\)','',text).strip()
        if text:kept.append(text)
    return ' '.join(kept)

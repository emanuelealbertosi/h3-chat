"""Requested slide counts; automatic length is resolved by the source-aware outline."""
import re

MAX_SLIDES = 50
MAX_DECK_CHARACTERS = 4_600_000
_SLIDES = r'(?:slides?|diapositiv[ae])'


def requested_count(prompt, saved=8):
    # A precise human count always wins over automatic settings. Do not confuse
    # a reference to a single slide being edited with the requested deck length.
    automatic = any(re.search(pattern, prompt, re.I) for pattern in (
            r'\b(?:numero|quantit[aà])\s+(?:di\s+)?' + _SLIDES + r'\s*(?:(?:in|sia|è|e)\s+)?(?:automatic[oa]|autonom[oa])\b',
            r'\bnumero\s+(?:automatico|autonomo)\s+(?:di\s+)?' + _SLIDES + r'\b',
            r'\b(?:scegli|decidi|calcola|determina|stabilisci)\s+(?:tu\s+)?(?:(?:automaticamente|autonomamente)\s+)?(?:il\s+)?(?:numero\s+(?:di\s+)?' + _SLIDES + r'|quant[ei]\s+' + _SLIDES + r')\b',
            r'\b' + _SLIDES + r'\s+(?:necessarie|necessari|che\s+servono)\b',
            r'\b(?:scegli|decidi)\s+tu\s+quant[ei](?:\s+ne)?\s+(?:servono|sono\s+necessari[eo])\b',
    ))
    number = None
    for candidate in re.finditer(r'\b(\d+)\s*' + _SLIDES + r'\b', prompt, re.I):
        prefix=prompt[max(0,candidate.start()-60):candidate.start()]
        bounded=re.search(r'(?:massimo|minimo|max\.?|min\.?|fino\s+a|non\s+pi[uù]\s+di|almeno|(?:da|tra|fra)\s+\d+\s+(?:a|e))\s*$',prefix,re.I)
        if (automatic or saved=='auto') and bounded:continue
        number=candidate;break
    if not number:
        number=re.search(r'\b(?:numero\s+(?:di\s+)?'+_SLIDES+r'|'+_SLIDES+r')\s*[:=]\s*(\d+)\b',prompt,re.I)
    count=int(number[1]) if number else 'auto' if automatic else saved
    if count != 'auto' and (type(count) is not int or not 1 <= count <= MAX_SLIDES):
        raise ValueError(f'Slide: scegli Automatico oppure un numero da 1 a {MAX_SLIDES}.')
    if count=='auto':outline_bounds(prompt,count)
    return count


def outline_bounds(prompt,count):
    if count!='auto':return count,count
    lower,upper=1,MAX_SLIDES
    for match in re.finditer(r'\b(?:massimo|max\.?|fino\s+a|non\s+pi[uù]\s+di)\s+(\d+)\s*'+_SLIDES+r'\b',prompt,re.I):upper=min(upper,int(match[1]))
    for match in re.finditer(r'\b(?:minimo|min\.?|almeno)\s+(\d+)\s*'+_SLIDES+r'\b',prompt,re.I):lower=max(lower,int(match[1]))
    for match in re.finditer(r'\b(?:da|tra|fra)\s+(\d+)\s+(?:a|e)\s+(\d+)\s*'+_SLIDES+r'\b',prompt,re.I):lower=max(lower,int(match[1]));upper=min(upper,int(match[2]))
    if not 1<=lower<=upper<=MAX_SLIDES:raise ValueError('Intervallo automatico delle slide non valido: scegli limiti compatibili da 1 a 50.')
    return lower,upper


def outline_count_instruction(count):
    if count == 'auto':
        return (f'Scegli autonomamente il numero di slide, da 1 a {MAX_SLIDES}, sulla base della richiesta, '
                'dei contenuti e delle fonti disponibili, del pubblico e dell’eventuale durata indicata. '
                'Copri tutti gli argomenti richiesti con una densità leggibile, senza riempitivi o ripetizioni. '
                'Conta nel totale anche copertina, pause, esercizi e conclusioni, quando richiesti. '
                'Il numero effettivo è la lunghezza della scaletta restituita; non mirare automaticamente al massimo.')
    return f'Progetta esattamente {count} slide.'

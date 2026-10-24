"""Optional color direction for free HTML slides; independent of infographics."""
import re

TEXT_TONES = ('auto','light','dark')

def requested_tone(prompt):
    matches=list(re.finditer(r'\b(?:test[oi]|scritte|font|caratteri|lettere|text)\s+(?:(?:di\s+colore|colore|sempre|tutt[oi]|tutte)\s+)*(chiari|chiare|bianc[ohi]+|scuri|scure|ner[oi]+|automatic[oi]|light|dark)\b',prompt,re.I))
    if not matches:return None
    m=matches[-1]
    if re.search(r'\bnon\s+(?:usare|voglio|utilizzare)\s*$',prompt[max(0,m.start()-35):m.start()],re.I):return None
    word=m[1].lower();return 'auto' if word.startswith('automatic') else 'light' if word.startswith(('chiar','bianc','light')) else 'dark'

BACKGROUNDS = ('auto', 'light', 'dark', 'custom')
PALETTES = {
    'auto': '',
    'natural': 'colori naturali e misurati, neutri con accenti ispirati alla natura',
    'pastel': 'colori pastello coordinati',
    'vivid': 'colori vivaci e saturi, coordinati, con accenti contrastanti',
    'neon': 'accenti neon luminosi; evita grandi superfici fluorescenti e testi poco leggibili',
    'monochrome': 'palette monocromatica: una famiglia cromatica con variazioni di luminosità',
}


def options(value):
    result = {}
    for key, allowed in (('background', BACKGROUNDS), ('palette', tuple(PALETTES)), ('text_tone',TEXT_TONES)):
        if key in value:
            if not isinstance(value[key], str) or value[key] not in allowed:
                raise ValueError('Sfondo o palette delle slide non validi.')
            result[key] = value[key]
    if 'background_color' in value:
        color = value['background_color']
        if not isinstance(color, str) or not re.fullmatch(r'#[0-9a-fA-F]{6}', color):
            raise ValueError('Colore di sfondo delle slide non valido.')
        result['background_color'] = color.lower()
    if result.get('background') == 'custom':
        result.setdefault('background_color', '#f7f3e8')
    return result


def brief(value):
    opts = options(value)
    background = opts.get('background', 'auto')
    palette = opts.get('palette', 'auto')
    tone=opts.get('text_tone','auto')
    if background == palette == tone == 'auto':
        return ''
    instructions = []
    if background == 'light':
        instructions.append('Sfondo principale chiaro.'+(' Testi scuri e accenti leggibili.' if tone=='auto' else ''))
    elif background == 'dark':
        instructions.append('Sfondo principale scuro.'+(' Testi chiari e accenti leggibili.' if tone=='auto' else ''))
    elif background == 'custom':
        instructions.append('Sfondo principale del colore '+opts['background_color']+'.')
    if tone!='auto':
        instructions.append('COLORE DEI FONT: testi '+('chiari, bianchi o quasi bianchi' if tone=='light' else 'scuri, neri o quasi neri')+'. Applica a titoli, corpo, didascalie ed etichette SVG. Questa scelta è indipendente dalla palette. Progetta superfici locali contrastanti dietro i testi se lo sfondo principale ha luminosità simile; mai scritte bianche su chiaro o nere su scuro. Non aggiungere testo alle illustrazioni AI.')
    if palette != 'auto':
        instructions.append('Palette: '+PALETTES[palette]+'.')
    return '\nPREFERENZE COLORE DELLA PRESENTAZIONE:\n'+'\n'.join(instructions)+'''\nDeclina lo stile selezionato entro queste preferenze. Scegli font, composizioni
e colori secondari liberamente, senza imporre un template. Riporta le scelte
in visual_direction e applicale negli sfondi HTML/CSS di ogni pagina e nei
prompt delle illustrazioni. Lo sfondo scelto è la superficie principale della
slide, non soltanto una cornice dietro un pannello di colore diverso.
Mantieni contrasto leggibile: almeno 4.5:1 per il testo normale; mai testo
pastello su fondo chiaro o testo scuro su fondo scuro. Neon non obbliga uno
sfondo scuro se è stato scelto chiaro. Preferenze esplicite nel prompt corrente
su colori o sfondo prevalgono su questi selettori. Non recuperare palette
dalle impostazioni delle infografiche o da presentazioni precedenti.'''

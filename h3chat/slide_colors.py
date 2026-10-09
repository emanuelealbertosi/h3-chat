"""Optional color direction for free HTML slides; independent of infographics."""
import re

BACKGROUNDS = ('auto', 'light', 'dark', 'custom')
PALETTES = {
    'auto': '',
    'natural': 'colori naturali e misurati, neutri con accenti ispirati alla natura',
    'pastel': 'colori pastello coordinati; usa testi abbastanza scuri da restare leggibili',
    'vivid': 'colori vivaci e saturi, coordinati, con accenti contrastanti',
    'neon': 'accenti neon luminosi; evita grandi superfici fluorescenti e testi poco leggibili',
    'monochrome': 'palette monocromatica: una famiglia cromatica con variazioni di luminosità',
}


def options(value):
    result = {}
    for key, allowed in (('background', BACKGROUNDS), ('palette', tuple(PALETTES))):
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
    if background == palette == 'auto':
        return ''
    instructions = []
    if background == 'light':
        instructions.append('Sfondo principale chiaro, con testi scuri e accenti leggibili.')
    elif background == 'dark':
        instructions.append('Sfondo principale scuro, con testi chiari e accenti leggibili.')
    elif background == 'custom':
        instructions.append('Sfondo principale del colore '+opts['background_color']+'.')
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

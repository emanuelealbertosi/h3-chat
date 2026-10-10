"""Optional typography controls; automatic presets preserve existing scenes."""
import re

EFFECTS=('fade','slide','zoom','pan','blur','wipe','strobe','typewriter','appear','bump','drop','wave','flip')
CHOICES={
    'text_motion':('auto','fade','slide','bump','typewriter','drop','wave','flip'),
    'text_direction':('auto','left','right','up','down'),
    'text_speed':('auto','slow','normal','fast'),
    'text_look':('auto','plain','neon','outline'),
    'text_color':('auto','custom','cycle'),
    'text_scope':('headings','all'),
}
DEFAULTS={key:values[0] for key,values in CHOICES.items()}|{'text_primary':'#ffffff','text_accent':'#00e5ff'}

def validate(options):
    for key in ('text_primary','text_accent'):
        if not isinstance(options[key],str) or not re.fullmatch(r'#[0-9a-fA-F]{6}',options[key]):
            raise ValueError('Colore testi non valido: scegli un colore esadecimale #RRGGBB.')

def brief(options):
    return ('\nRegia dei testi: usa titoli e parole chiave leggibili, marcando le frasi importanti con data-text="key". '
        'Gli effetti bump (rimbalzo), drop (lettere in caduta con prospettiva), wave (lettere in onda), '
        'flip (rotazione) e typewriter (carattere per carattere) sono interpretati dal motore, senza JavaScript. '
        'Usali su brevi testi, non su intere colonne. data-direction="left|right|up|down" indica da dove entra uno scorrimento. '
        'Le opzioni text_* esplicite vengono applicate dal motore ai titoli/parole chiave oppure a tutti i testi secondo text_scope; '
        'non simulare gli effetti con duplicati, spazi fra lettere o testi nascosti. '
        'Con text_motion=auto scegli tu effetti diversi in base al prompt. Conserva tempi di ingresso/uscita coerenti con la voce. '
        'Con text_look=auto e text_color=auto scegli colori leggibili sullo sfondo. '
        'Le lettere devono tornare tutte nella posizione finale e restare leggibili prima dello stacco.')

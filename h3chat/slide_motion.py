"""Optional presentation motion, shared by initial generation and revisions."""
import re

VALUES=('auto','static','animated')

def options(prompt,body):
    value=body.get('motion','auto')
    if not isinstance(value,str) or value not in VALUES:raise ValueError('Slide: scegli Automatico, Statiche oppure Animate.')
    if re.search(r'\b(?:slide|diapositive|presentazione)\s+static[hae]+\b|\bsenza\s+animazioni\b',prompt,re.I):value='static'
    elif re.search(r'\b(?:slide|diapositive|presentazione)\s+animat[ae]\b|\b(?:con|aggiungi|crea)\s+(?:le\s+)?(?:animazioni|transizioni)\b',prompt,re.I):value='animated'
    return value

def brief(value):
    if value=='static':
        return '\nMOVIMENTO: slide statiche. Non inserire animazioni CSS, SVG/SMIL, transizioni o contenuti inizialmente nascosti. Tutti i contenuti devono essere visibili subito.'
    if value=='animated':
        return '\nMOVIMENTO: slide animate. Implementa davvero CSS @keyframes per ingressi progressivi e transizioni brevi coerenti con il contenuto; SVG animato quando chiarisce un diagramma. Non limitarti a descriverle nelle note. Mantieni testi leggibili, durata breve, niente lampeggiamenti; rispetta prefers-reduced-motion e rendi sempre visibili i contenuti nelle esportazioni statiche. Nessun JavaScript.'
    return ''

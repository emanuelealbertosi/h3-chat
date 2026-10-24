"""Indicative speaking time; independent from rendering and provider timeouts."""
import re

MAX_MINUTES=20

def requested(prompt,body):
    value=body.get('duration_minutes',0)
    unit=r'(?:minuti?|minutes?|min)'
    match=re.search(r'\b(?:durata(?:\s+(?:totale|complessiva|indicativa))?|presentazione|lezione)\s*(?:(?:di|da|per|circa)\s*)?(\d+(?:[.,]\d+)?)\s*'+unit+r'\b',prompt,re.I)
    candidates=list(re.finditer(r'\b(\d+(?:[.,]\d+)?)\s*'+unit+r'\b',prompt,re.I))
    if not match and len(candidates)==1:match=candidates[0]
    if match:value=float(match[1].replace(',','.'))
    if type(value) not in (int,float) or not 0<=value<=MAX_MINUTES:
        raise ValueError('Durata indicativa delle slide: da 1 a 20 minuti, oppure 0 per Automatico.')
    if match and value==0:raise ValueError('La durata richiesta deve essere maggiore di zero.')
    return value

def brief(minutes,count=None):
    if not minutes:return ''
    budget=(f' Con {count} slide il riferimento medio è {minutes*60/count:g} secondi per pagina; distribuisci diversamente secondo complessità e attività.' if type(count) is int and count else '')
    return (f'\nDURATA INDICATIVA DELLA PRESENTAZIONE: {minutes:g} minuti complessivi ({minutes*60:g} secondi), incluse pause e attività.'+budget+
            ' Dimensiona contenuti, numero automatico di slide e note del relatore per questo tempo. Indica nelle note il tempo suggerito per ciascuna pagina; la somma deve avvicinarsi al totale. È una stima di esposizione, non un limite di generazione né un timer di riproduzione.')

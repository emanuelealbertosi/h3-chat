"""User-selected panel geometry; the LLM authors the HTML inside each panel."""
from html.parser import HTMLParser
from itertools import permutations
import re
LAYOUTS={'full':(1,'schermo intero'),'columns2':(2,'due colonne affiancate'),'rows2':(2,'due riquadri sopra/sotto'),
         'columns3':(3,'tre colonne affiancate'),'rows3':(3,'tre riquadri sovrapposti'),'pip':(2,'principale con riquadro in basso a destra')}
DEFAULTS={'layout':'full','panel_appearance':'all','panel_order':'auto','panel_interval':.8}

def validate(opts):
    if opts.get('layout') not in LAYOUTS or opts.get('panel_appearance') not in ('all','sequence'):raise ValueError('Composizione dello schermo non valida.')
    count=LAYOUTS[opts['layout']][0]
    if opts.get('panel_order') not in ('auto',*(''.join(p) for p in permutations('123'[:count]))):raise ValueError('Ordine dei riquadri non valido per questa composizione.')
    value=opts.get('panel_interval')
    if type(value) not in (int,float) or not .2<=value<=30:raise ValueError('Intervallo fra riquadri: da 0,2 a 30 secondi.')

def prompt_timing(prompt,opts):
    if LAYOUTS.get(opts.get('layout'),(1,''))[0]==1:return
    match=re.search(r'\b(?:video|riquadr[oi]|pannell[oi])\b.{0,60}?\b(?:ogni|intervallo(?:\s+di)?|delay(?:\s+di)?|ritardo(?:\s+di)?)\s+(\d+(?:[.,]\d+)?)\s*(?:second[oi]\b|s\b)',prompt,re.I)
    if not match:match=re.search(r'\b(?:intervallo|delay|ritardo)\s+(?:di\s+)?(\d+(?:[.,]\d+)?)\s*(?:second[oi]\b|s\b).{0,40}\b(?:video|riquadr[oi]|pannell[oi])\b',prompt,re.I)
    if match:
        opts['panel_interval']=float(match[1].replace(',','.'));opts['panel_appearance']='sequence'
        if re.search(r'\bvideo\b',match[0],re.I):opts['video_start']='panel'
        unit=re.match(r'\s*(?:second[oi]\b|s\b)',prompt[match.end(1):],re.I)
        return match.start(1),match.end(1)+unit.end()

def brief(opts,duration=None):
    count,label=LAYOUTS[opts['layout']]
    if count==1:return ''
    order='123'[:count] if opts['panel_order']=='auto' else opts['panel_order']
    text=f'\nCOMPOSIZIONE OBBLIGATORIA: {label}. Scrivi {count} sezioni principali sorelle, con data-panel="1"'+(' e data-panel="2".' if count==2 else ', data-panel="2" e data-panel="3".')
    text+=' Numeri da sinistra a destra nelle colonne, dall’alto in basso nelle righe; per il riquadro 1 è il principale e 2 la sovraimpressione. Il motore fissa solo i rettangoli; TU progetti contenuti, font, colori, immagini, grafici ed effetti dentro ciascuno. Nessun altro contenuto fuori dalle sezioni. Non duplicare gli stessi contenuti.'
    text+=' Ogni riquadro usa coordinate locali: position:relative, width/height:100%, min-width/min-height:0. Dimensiona testi e immagini per la sua frazione del viewport; non usare larghezze pari all’intera pagina nei riquadri.'
    if opts['panel_appearance']=='sequence':text+=f' Ingressi in ordine {order}, intervallo indicativo {opts["panel_interval"]} secondi. Ogni riquadro resta visibile dopo l’ingresso. Scegli data-motion per il suo ingresso fra fade, slide, zoom, blur e wipe; il motore rispetta l’ordine e adatta gli intervalli alle scene brevi.'
    else:text+=' I riquadri sono visibili insieme; puoi animare liberamente i loro contenuti.'
    return text

def valid_panels(html,opts):
    count=LAYOUTS[opts['layout']][0]
    if count==1:return True
    class Panels(HTMLParser):
        def __init__(self):super().__init__();self.panels=[];self.stack=[];self.parents=[]
        def handle_starttag(self,tag,attrs):
            from .pdf_export import VOID
            value=dict(attrs).get('data-panel')
            if value is not None:self.panels.append(value);self.parents.append(tuple(self.stack))
            if tag not in VOID:self.stack.append((tag,len(self.panels)))
        def handle_endtag(self,tag):
            for i in range(len(self.stack)-1,-1,-1):
                if self.stack[i][0]==tag:self.stack=self.stack[:i];break
    parser=Panels();parser.feed(html)
    return sorted(parser.panels)==list('123'[:count]) and len(set(parser.parents))==1

def ensure_panels(engine,request,settings,cancel,html,opts,on_text):
    if valid_panels(html,opts):return html
    from .slide_html import validate as validate_html
    raw,finish=engine.completion(request+[{'role':'assistant','content':html},{'role':'user','content':'Correggi solo la struttura dei riquadri, conservando contenuti e stile. '+brief(opts)+' Restituisci tutto l’HTML completo.'}],settings,cancel,on_text=on_text)
    if finish=='length':raise ValueError('Composizione dei riquadri incompleta: aumenta Max token.')
    html=validate_html(raw)
    if not valid_panels(html,opts):raise ValueError('Il modello non ha creato tutti i riquadri richiesti. Rigenera questa scena o cambia modello.')
    return html

"""Ask the authoring LLM to repair scenes that contain no playable animation."""
from html.parser import HTMLParser
import math
from .slide_html import BRIEF,validate

HTML_BRIEF=BRIEF.replace('HTML statico completo.','HTML/CSS completo: le animazioni vengono interpretate dal motore tramite gli attributi data-motion, senza JavaScript.')
BRIEF_MOTION='Assegna agli elementi visibili data-motion="fade|slide|zoom|pan|blur|wipe|strobe|typewriter|appear", data-start e data-duration in secondi; data-out è opzionale. Distribuisci gli ingressi lungo la scena, con una regia coerente con la narrazione. Non limitarti a una pagina statica. Nessun JavaScript, CSS animation o transition.'

def playable(html,duration):
    class Animation(HTMLParser):
        found=False
        def handle_starttag(self,tag,attrs):
            if tag in ('script','style','meta','link'):return
            values=dict(attrs);effect=values.get('data-motion')
            if effect not in ('fade','slide','zoom','pan','blur','wipe','strobe','typewriter','appear'):return
            try:start=float(values.get('data-start',0));span=float(values.get('data-duration',.65))
            except (TypeError,ValueError):return
            if not math.isfinite(start) or not math.isfinite(span) or not 0<=start<duration or span<=0:return
            if effect!='appear' or start>0:self.found=True
    parser=Animation();parser.feed(html);return parser.found

def ensure(engine,request,settings,cancel,html,duration,on_text):
    if playable(html,duration):return html
    repair=request+[{'role':'assistant','content':html},{'role':'user','content':'La scena restituita è statica: mancano animazioni utilizzabili dal motore. Conserva composizione, contenuti, immagini e riquadri; aggiungi una vera regia degli elementi visibili per '+str(duration)+' secondi. '+BRIEF_MOTION+' Restituisci l’HTML completo.'}]
    raw,finish=engine.completion(repair,settings,cancel,on_text=on_text)
    if finish=='length':raise ValueError('Animazione incompleta: aumenta Max token.')
    html=validate(raw)
    if not playable(html,duration):raise ValueError('Il modello ha restituito ancora una pagina statica senza animazioni. Rigenera la scena o cambia modello.')
    return html

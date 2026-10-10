"""Ask the authoring LLM to repair scenes that contain no playable animation."""
from html.parser import HTMLParser
import math
from .slide_html import BRIEF,validate,InvalidPage
from .downloads import Cancelled
from .infographic_text import EFFECTS
from .remote_llm import EmptyCompletion

HTML_BRIEF=BRIEF.replace('HTML statico completo.','HTML/CSS completo: le animazioni vengono interpretate dal motore tramite gli attributi data-motion, senza JavaScript.')
BRIEF_MOTION='Assegna agli elementi visibili data-motion="fade|slide|zoom|pan|blur|wipe|strobe|typewriter|appear|bump|drop|wave|flip", data-start e data-duration in secondi; data-out è opzionale. Distribuisci gli ingressi lungo la scena, con una regia coerente con la narrazione. Non limitarti a una pagina statica. Nessun JavaScript, CSS animation o transition.'

def playable(html,duration):
    class Animation(HTMLParser):
        found=False
        def handle_starttag(self,tag,attrs):
            if tag in ('script','style','meta','link'):return
            values=dict(attrs);effect=values.get('data-motion')
            if effect not in EFFECTS:return
            try:start=float(values.get('data-start',0));span=float(values.get('data-duration',.65))
            except (TypeError,ValueError):return
            if not math.isfinite(start) or not math.isfinite(span) or not 0<=start<duration or span<=0:return
            if effect!='appear' or start>0:self.found=True
    parser=Animation();parser.feed(html);return parser.found

def ensure(engine,request,settings,cancel,html,duration,on_text,stage=None):
    if cancel.is_set():raise Cancelled()
    if playable(html,duration):return html
    original=html
    repair=request+[{'role':'assistant','content':html},{'role':'user','content':'La scena restituita è statica: mancano animazioni utilizzabili dal motore. Conserva composizione, contenuti, immagini e riquadri; aggiungi una vera regia degli elementi visibili per '+str(duration)+' secondi. '+BRIEF_MOTION+' Restituisci l’HTML completo.'}]
    try:
        raw,finish=engine.completion(repair,settings,cancel,on_text=on_text)
        if cancel.is_set():raise Cancelled()
        html=original if finish=='length' else validate(raw)
    except (InvalidPage,EmptyCompletion):html=original
    if not playable(html,duration):
        from .infographic_choreography import repair as repair_choreography
        return repair_choreography(engine,request,settings,cancel,original,duration,on_text,stage)
    return html

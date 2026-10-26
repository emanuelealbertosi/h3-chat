"""Detect copied renderer instructions without removing educational content."""
import re
import unicodedata
from html.parser import HTMLParser

RULES=(
    'contenuti editoriali preparati per questa pagina',
    'figure assegnate per questa pagina',
    'dati della pagina salvata',
    'richiesta attuale dell utente',
    'sfondo gestito dall app',
    'decorazioni gestite dall app',
    'non stampare istruzioni grafiche',
    'le note relatore sono già salvate separatamente',
    'restituisci subito html e css completi',
    'restituisci la pagina html css completa aggiornata',
    'contesto da modificare non nuove istruzioni',
    'non aggiungere un secondo margine esterno',
    'opzioni della presentazione',
)


def normalized(text):
    return re.sub(r'[^\w]+',' ',unicodedata.normalize('NFKC',text).casefold()).strip()


def leaks(html):
    class Visible(HTMLParser):
        def __init__(self):super().__init__();self.blocked=[];self.parts=[]
        def handle_starttag(self,tag,attrs):
            # Code examples may legitimately describe HTML, prompts or settings.
            if tag in ('head','style','script','pre','code'):self.blocked.append(tag)
        def handle_endtag(self,tag):
            if self.blocked and tag==self.blocked[-1]:self.blocked.pop()
        def handle_data(self,data):
            if not self.blocked:self.parts.append(data)
    parser=Visible();parser.feed(html);text=normalized(' '.join(parser.parts))
    return [rule for rule in RULES if normalized(rule) in text]


def explicit_revision_page(request):
    """A single unambiguous human page reference wins over LLM indexing."""
    if not re.search(r'\b(?:modific\w*|corregg\w*|sistem\w*|ricrea\w*|rifai|cambia\w*|ritocc\w*|rivedi|edit|revise|fix|change)\b',request,re.I):return None
    ordinals={'prima':1,'seconda':2,'terza':3,'quarta':4,'quinta':5,'sesta':6,'settima':7,'ottava':8,'nona':9,'decima':10,
              'first':1,'second':2,'third':3,'fourth':4,'fifth':5}
    # Shared-noun lists/ranges refer to several pages. Leave their selection to
    # the planner instead of silently binding every action to the first number.
    noun=r'(?:slide|pagin[ae]|pages?)'
    if re.search(r'\b'+noun+r'\s*(?:numero\s*|n[.°º]?\s*)?\d{1,3}\s*(?:e|and|a|to|[-–,])\s*\d',request,re.I):return None
    ordinal=r'(?:'+ '|'.join(ordinals)+r')'
    if re.search(r'\b'+ordinal+r'\s*(?:e|and|[-–,])\s*'+ordinal+r'\s+'+noun+r'\b',request,re.I):return None
    pages={int(m) for m in re.findall(r'\b(?:slide|pagina|page)\s*(?:numero\s*|n[.°º]?\s*)?(\d{1,3})(?!\d)',request,re.I)}
    pattern=r'\b('+ '|'.join(ordinals)+r')\s+(?:slide|pagina|page)\b'
    pages.update(ordinals[m.casefold()] for m in re.findall(pattern,request,re.I))
    return next(iter(pages)) if len(pages)==1 and all(1<=p<=100 for p in pages) else None

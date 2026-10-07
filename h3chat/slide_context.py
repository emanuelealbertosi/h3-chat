"""Keep slide requests and sources without repeatedly prefilling old HTML decks."""
import json
from html.parser import HTMLParser


class SlideText(HTMLParser):
    def __init__(self):super().__init__();self.skip=0;self.parts=[]
    def handle_starttag(self,tag,attrs):
        if tag in ('style','script'):self.skip+=1
    def handle_endtag(self,tag):
        if tag in ('style','script') and self.skip:self.skip-=1
    def handle_data(self,data):
        if not self.skip and data.strip():self.parts.append(data.strip())


def animation_history(history):
    """Keep slide facts for Manim without sending every previous HTML layout."""
    result=[];remaining=16000
    for message in reversed(history):
        item=message.copy();text=item.get('content','');artifact=item.get('meta',{}).get('artifact') or {}
        content=artifact.get('content','')
        snapshot=item.get('seq')==-1 and text.startswith('Canvas attuale da modificare se richiesto:\n')
        if snapshot:content=text.split('\n',1)[1]
        if content.startswith('```h3-slides\n'):
            try:
                deck=json.loads(content[13:-4]);facts=['Presentazione: '+str(deck.get('title',''))]
                for page in deck.get('pages',[])[:30]:
                    parser=SlideText();parser.feed(page.get('html',''))
                    nodes=[str(n.get('text','')) for n in page.get('nodes',[]) if n.get('text')]
                    facts.append(str(page.get('title',''))+'\n'+' '.join(parser.parts+nodes)+'\n'+str(page.get('notes','')))
                limit=min(6000,max(200,remaining));summary='\n'.join(facts)[:limit];remaining=max(0,remaining-len(summary))
                base='' if snapshot else text.split('\nArtefatto nel canvas:\n',1)[0].split('\nContenuti della presentazione precedente (non una nuova fonte; HTML e CSS omessi):\n',1)[0]
                item['content']=base+'\nContenuti della presentazione precedente (non una nuova fonte; HTML e CSS omessi):\n'+summary
            except (ValueError,TypeError,AttributeError):pass
        result.append(item)
    return list(reversed(result))


def artifact_summary(content):
    if content.startswith('```h3-slides\n'):
        try:
            deck=json.loads(content[13:-4])
            return json.dumps({'title':deck.get('title'), 'engine':deck.get('engine'),
                'design':deck.get('design'), 'detail':deck.get('detail'),
                'visual_direction':deck.get('visual_direction','')[:800],
                'pages':[{'title':p.get('title'), 'purpose':p.get('purpose','')[:250]} for p in deck.get('pages',[])[:30]]},ensure_ascii=False)
        except (ValueError,TypeError,AttributeError):pass
    return content[:1200]


def compact_history(history):
    result=[]
    for message in history:
        item=message.copy();text=item.get('content','')
        artifact=item.get('meta',{}).get('artifact')
        if artifact:
            text=text.split('\nArtefatto nel canvas:\n',1)[0]
            text=text.split('\nRiepilogo dell’artefatto precedente (non una fonte):\n',1)[0]
            text+='\nRiepilogo dell’artefatto precedente (non una fonte):\n'+artifact_summary(artifact.get('content',''))
        if item.get('seq')==-1 and text.startswith('Canvas attuale da modificare se richiesto:\n'):
            content=text.split('\n',1)[1]
            if not content.startswith('```h3-slides\n'):result.append(item);continue
            summary=artifact_summary(content)
            # For a requested edit, keep a bounded sample of the current page's
            # original CSS. Do not repeat every page of every previous version.
            try:
                deck=json.loads(content[13:-4]);page=deck['pages'][min(len(deck['pages'])-1,max(0,deck.get('active',0)))]
                if page.get('html'):summary+='\nHTML della pagina attuale:\n'+page['html'][:6000]
            except (ValueError,TypeError,KeyError,IndexError):pass
            text='Canvas attuale da modificare se richiesto:\n'+summary
        item['content']=text;result.append(item)
    # Fresh retrieved excerpts are attached to the final user turn afterwards.
    # Never cut that turn, its source identifiers, or the current canvas sample.
    allowance=12000
    for item in reversed(result[:-1]):
        if item.get('seq')==-1:continue
        limit=min(allowance,2400 if item.get('role')=='user' else 1800)
        text=item['content'];item['content']=text[:limit];allowance-=len(item['content'])
    return [item for item in result if item['content'] or item.get('media')]

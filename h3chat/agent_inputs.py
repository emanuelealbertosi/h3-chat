"""Typed artifact links shared by Agent tools, always scoped to the current chat."""
import json
from html.parser import HTMLParser

class Visible(HTMLParser):
    def __init__(self):super().__init__();self.parts=[];self.blocked=0
    def handle_starttag(self,tag,attrs):
        if tag in ('style','script'):self.blocked+=1
    def handle_endtag(self,tag):
        if tag in ('style','script'):self.blocked=max(0,self.blocked-1)
    def handle_data(self,value):
        if not self.blocked and value.strip():self.parts.append(value.strip())

def text_of(value):
    from .slides import PREFIX
    content=value['content']
    if not content.startswith(PREFIX):return content[:12000]
    deck=json.loads(content[len(PREFIX):-4]);parts=[]
    for i,page in enumerate(deck['pages'],1):
        parser=Visible();parser.feed(page.get('html',''))
        body=' '.join(parser.parts) or ' '.join(n.get('text','') for n in page.get('nodes',[]))
        parts.append(f"Pagina {i}: {page['title']}\n{body[:2500]}\nNote: {page.get('notes','')[:1500]}")
    return '\n\n'.join(parts)[:16000]

def attach(ctx,args,name=''):
    from .agent_tools import artifact
    records=[];media=list(ctx.payload['media']);seen={m['id'] for m in media};documents=[]
    for ident in args.get('source_artifact_ids',[]):
        value=artifact(ctx.app,ctx.job['chat_id'],ident)
        extracted=[d for d in ctx.state.get('documents',[]) if d['id'] in {m['id'] for m in value['media']}]
        text=text_of(value)
        if not text.strip():text='\n\n'.join(b['text'] for d in extracted for b in d['blocks'])[:16000]
        record=info(value)|{'text':text};records.append(record)
        kinds=set(record['media_types'])
        video_tool=name in ('create_video','edit_video','inspect_video_timeline','assemble_video')
        if not record['text'].strip() and kinds and kinds<= {'audio','video'} and not video_tool and not (name=='create_manim' and kinds=={'audio'}):
            raise ValueError('La sorgente contiene solo '+', '.join(sorted(kinds))+': prima trascrivi l’audio con transcribe_audio. Agent non analizza o modifica video.')
        if not record['text'].strip() and kinds=={'image'} and name in ('create_voice','create_music'):
            raise ValueError('La sorgente è solo un’immagine senza descrizione: usa prima inspect_image con Vision, poi riutilizza la descrizione. Non è stata inventata una descrizione.')
        if not record['text'].strip() and kinds and kinds<= {'application','text'}:
            raise ValueError('Leggi prima il documento con read_attachment e artifact_id, poi riutilizza la fonte estratta.')
        if name=='create_infographic' and sum(m['mime'].startswith('image/') for m in value['media'])>32:
            raise ValueError('Un’infografica può ricevere al massimo 32 immagini: scegli un artefatto con una selezione più piccola.')
        if records[-1]['text']:
            documents.append({'id':ident,'name':'Artefatto · '+value['title'],'citation':'D'+str(len(ctx.state.get('documents',[]))+len(documents)+1),
                              'locations':['artefatto salvato'],'partial':True,'blocks':[{'text':records[-1]['text'],'location':'artefatto salvato'}]})
        for item in value['media']:
            if item['id'] not in seen:
                seen.add(item['id']);media.append(item)
        if len(media)>128:raise ValueError('Troppi file sorgente per un singolo passaggio Agent (massimo 128).')
    ctx.active_source_documents=documents;ctx.active_tool_media=media;ctx.source_artifacts=records
    ctx.tool_payload=ctx.payload|{'media':media}

def selected(ctx,args,mime=None):
    """An explicit position always indexes the full media list, not a filtered list."""
    from .agent_tools import artifact
    choices=artifact(ctx.app,ctx.job['chat_id'],args['artifact_id'])['media'] if args.get('artifact_id') else ctx.payload['media']
    number=args.get('number',1)
    if number>len(choices):raise ValueError('File non presente negli allegati o nell’artefatto scelto.')
    item=choices[number-1]
    if mime and not item['mime'].startswith(mime+'/'):raise ValueError('Seleziona un file '+mime+' usando il suo numero nell’elenco media.')
    return item

def info(value):
    from .slides import PREFIX
    kinds={m.get('mime','').split('/')[0] for m in value.get('media',[])}
    kind='slides' if value['content'].startswith(PREFIX) else 'text' if value['content'] else 'media'
    if kind=='slides' and json.loads(value['content'][len(PREFIX):-4]).get('infographic'):kind='infographic'
    return {'id':value.get('id'),'title':value['title'],'kind':kind,'media_types':sorted(kinds)}

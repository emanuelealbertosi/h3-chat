"""Select traceable excerpts inside a shared context budget."""
import math
import re

def tokens(text):return set(re.findall(r'\w{3,}',text.lower()))

def retrieval_query(prompt,history):
    """Resolve explicit follow-ups from user requests, never from generated artifacts."""
    followup=r'\b(?:ricrea|rigenera|rifai|riprova|ripeti|continua|ricreala|rigenerala|rifalla|recreate|regenerate|retry|redo|continue)\b'
    topic=r'\b(?:su|sul|sulla|sulle|sui|sugli|riguardo|about)\b'
    if not re.search(followup,prompt,re.I) or re.search(topic,prompt,re.I):return prompt
    previous=[]
    for message in reversed(history[:-1]):
        if message.get('role')!='user':continue
        text=message.get('content','')
        # Tool excerpts are not conversation topics or trusted instructions.
        text=re.split(r'<(?:fonti_progetto|contenuti_allegati_e_web)>',text)[0].strip()
        if not text:continue
        if re.search(r'\b(?:pagina|page)\s+\d+',prompt,re.I):
            text=re.sub(r'\b(?:pagina|page)\s+\d+','',text,flags=re.I)
        previous.append(text[:1500])
        if not re.search(followup,text,re.I) or re.search(topic,text,re.I) or len(previous)==3:break
    return prompt+(' '.join(['\nArgomento delle richieste precedenti:',*reversed(previous)]) if previous else '')

def retrieval_budget(settings,history):
    # Older code/canvas artifacts must not erase sources for the current request.
    # Reserve a bounded share of the current turn's allowance for fresh excerpts.
    return max(budget(settings,history)//2,budget(settings,history[-1:])//4)

def excerpts(blocks,query,budget):
    if not blocks:return [],False
    terms=tokens(query);pages={int(x) for x in re.findall(r'\b(?:pagina|page)\s+(\d+)\b',query,re.I)}
    paginated=any(b.get('page') is not None for b in blocks)
    candidates=[(i,b) for i,b in enumerate(blocks) if not pages or not paginated or b.get('page') in pages]
    if not candidates:return [],True
    if sum(len(b['text'])+80 for _,b in candidates)<=budget:return [b for _,b in candidates],len(candidates)<len(blocks)
    # Relevant passages first; for summaries spread across the whole document.
    ranked=sorted(candidates,key=lambda x:(-len(terms&tokens(x[1]['text'])),-int(x[1].get('page') in pages),x[0]))
    if not any(terms&tokens(b['text']) for _,b in candidates):
        slots=max(1,budget//1800);ranked=[candidates[round(i*(len(candidates)-1)/max(1,slots-1))] for i in range(min(slots,len(candidates)))]
    chosen=[];used=0
    for i,b in ranked:
        remaining=budget-used-80
        if remaining<150:break
        text=b['text']
        if len(text)>remaining:
            clipped=text[:remaining];boundaries=list(re.finditer(r'\s',clipped));text=clipped[:boundaries[-1].start()] if boundaries else ''
        if not text:continue
        chosen.append((i,b|{'text':text}));used+=len(text)+80
    return [b for _,b in sorted(chosen)],True

def budget(settings,history):
    # Conservative characters/token estimate; leave space for prompt, history and output.
    past=sum(len(m.get('content','')) for m in history)
    return max(150,max(600,min(24000,(settings['context']-settings['max_tokens']-700)*2-past))-settings.get('_context_reserved',0))

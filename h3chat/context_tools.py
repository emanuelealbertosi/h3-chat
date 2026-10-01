"""Select traceable excerpts inside a shared context budget."""
import math
import re

def tokens(text):return set(re.findall(r'\w{3,}',text.lower()))

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

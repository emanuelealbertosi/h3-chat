"""Keep generation count distinct from visual cuts inside a MiniMax clip."""
import math
import re
from .video_timing import _mask, RANGE, NUM_RANGE, seconds

WORDS={'uno':1,'una':1,'un':1,'due':2,'tre':3,'quattro':4,'cinque':5,'sei':6,
       'sette':7,'otto':8,'nove':9,'dieci':10,'undici':11,'dodici':12,
       'tredici':13,'quattordici':14,'quindici':15,'sedici':16,'diciassette':17,
       'diciotto':18,'diciannove':19,'venti':20,'one':1,'two':2,'three':3,'four':4,
       'five':5,'six':6,'seven':7,'eight':8,'nine':9,'ten':10,'eleven':11,'twelve':12}
NUMBER=r'(?:\d+|'+ '|'.join(WORDS)+r')'
UNITS=r'(?:clips?|scene|scenes|scena|segmenti|segments)'
HEADERS=re.compile(r'^[ \t]*(?:#{1,6}[ \t]*|\[)?(?:clip|segmento|segment)[ \t]+(\d+)\b[^\n]*',re.I|re.M)

def number(value):return int(value) if value.isdigit() else WORDS[value.lower()]

def requested(prompt):
    text=_mask(prompt)
    # A rejected count is not a second instruction. Shot / inquadratura counts
    # describe internal cuts, not additional GPU calls.
    text=re.sub(rf'\b(?:non|no|not|anziché|invece di|rather than)[ \t]+(?:(?:fare|generare|creare|make|generate)[ \t]+)?{NUMBER}[ \t]+{UNITS}\b','',text,flags=re.I)
    # Never interpret the trailing seconds in "00:15\nCLIP 2" as "15 clip".
    def named_counts(units,prefix):
        values={number(m[1]) for m in re.finditer(rf'(?<![\w:.,])({NUMBER})[ \t]+(?:{units})\b',text,re.I)}
        values.update(number(m[1]) for m in re.finditer(rf'\b(?:{prefix})[ \t]*[:=][ \t]*({NUMBER})\b',text,re.I))
        return values
    # Explicit generation clips win over a count of narrative scenes.
    counts=named_counts('clips?',r'(?:numero (?:di )?clip|(?:generation )?clips?)')
    if not counts:
        # Casual mentions such as "una scena sul divano" are plot content.
        # Accept scene counts only as explicit partitioning instructions.
        directives=r'(?:crea|genera|voglio|create|generate|make|in|(?:dividi|suddividi|divide|split)(?:[ \t]+in|[ \t]+into)?)'
        counts={number(m[1]) for m in re.finditer(rf'\b{directives}[ \t]+({NUMBER})[ \t]+(?:scene|scenes|scena|segmenti|segments)\b',text,re.I) if number(m[1])>1}
        counts.update(number(m[1]) for m in re.finditer(rf'\bnumero (?:di )?scene[ \t]*[:=][ \t]*({NUMBER})\b',text,re.I))
    if len(counts)>1:raise ValueError('Sono indicati numeri di clip diversi: specifica un solo numero di generazioni.')
    headers=list(HEADERS.finditer(text));indices=[int(m[1]) for m in headers]
    listed=len(indices) if indices and indices==list(range(1,len(indices)+1)) else None
    count=next(iter(counts),listed)
    if counts and listed and count!=listed:
        raise ValueError(f'Richiesti {count} clip, ma sono elencati {listed} blocchi: correggi il numero o l’elenco.')
    return count,headers

def contract(prompt,duration,*,audio_start=0):
    if type(duration) not in (int,float) or not math.isfinite(duration) or not 0<duration<=600:
        raise ValueError('Durata storyboard non valida.')
    frames=math.ceil(duration*24);minimum=math.ceil(frames/360)
    count,headers=requested(prompt);explicit=count is not None
    if count is None:count=minimum
    maximum=min(160,(frames-1)//24+1)
    if not minimum<=count<=maximum:
        raise ValueError(f'Per {duration:g} secondi servono da {minimum} a {maximum} clip (massimo 15 secondi ciascuno); richiesti {count}. Nessuna generazione video è stata avviata.')
    boundaries=[]
    if len(headers)==count and [int(m[1]) for m in headers]==list(range(1,count+1)):
        intervals=[]
        for header in headers:
            matches=[*RANGE.finditer(header[0]),*NUM_RANGE.finditer(header[0])]
            match=min(matches,key=lambda m:m.start()) if matches else None
            if match is None:break
            intervals.append((seconds(match['first']),seconds(match['last'])))
        if len(intervals)==count:
            if count>1 and all(start==0 for start,end in intervals):
                # Explicit clip-local clocks can all start at zero.
                cursor=0;global_intervals=[]
                for start,end in intervals:global_intervals.append((cursor,cursor+end));cursor+=end
                intervals=global_intervals
            elif audio_start and abs(intervals[0][0]-audio_start)<1/24:
                intervals=[(start-audio_start,end-audio_start) for start,end in intervals]
            cursor=0
            for index,(start,end) in enumerate(intervals):
                a,b=round(start*24),round(end*24)
                if a!=cursor or b<=a:raise ValueError('Gli intervalli dei clip devono essere consecutivi, senza buchi o sovrapposizioni.')
                # The last nominal 15-second clip can end at the audio tail.
                if index==count-1 and b>=frames and b-frames<=24:b=frames
                if b-a>360 or (b-a<24 and index!=count-1):raise ValueError('Ogni clip deve durare da 1 a 15 secondi, salvo la coda finale.')
                boundaries.append(b);cursor=b
            if cursor!=frames:raise ValueError('Gli intervalli dei clip devono coprire tutta la durata della traccia selezionata.')
    return {'count':count,'minimum':minimum,'explicit':explicit,'end_frames':boundaries}

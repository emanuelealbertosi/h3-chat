"""Validate the soundtrack before expensive synthesis; select stable scene voices."""
import json
import re
from .downloads import Cancelled


def music_brief(opts):
    if opts['output']!='video' or opts['music'] not in ('generate','jingle'):
        return 'music_style e jingle_lyrics devono essere stringhe vuote: non è richiesta musica generata.'
    return ('music_style deve essere una descrizione NON VUOTA in inglese di genere, strumenti, atmosfera e ritmo, coerente con il prompt. '+
            ('Per un jingle, scrivi anche jingle_lyrics in italiano.' if opts['music']=='jingle' else
             'La base è strumentale: specifica no vocals, no singing; jingle_lyrics deve essere vuoto. Non lasciare vuoto music_style solo perché non è un jingle.'))


def complete_music(engine,base,plan,opts,settings,cancel,stage):
    """One narrow repair keeps all approved scene content and narration intact."""
    if opts['output']!='video' or opts['music'] not in ('generate','jingle'):return plan
    keys=('music_style','jingle_lyrics') if opts['music']=='jingle' else ('music_style',)
    if all(isinstance(plan.get(k),str) and plan[k].strip() for k in keys):return plan
    if cancel.is_set():raise Cancelled()
    stage('Infografica · completamento della descrizione musicale prima della sintesi')
    schema={'type':'object','properties':{'music_style':{'type':'string','minLength':1,'maxLength':1200},
        'jingle_lyrics':{'type':'string','maxLength':6000}},'required':['music_style','jingle_lyrics'],'additionalProperties':False}
    brief=music_brief(opts)+'\nCompleta SOLO i campi musicali. Non cambiare la regia o la narrazione già approvata. Titolo: '+plan['title']+'\nDirezione: '+plan['visual_direction']
    tuning=settings|{'think_level':'off','max_tokens':min(settings['max_tokens'],2400),'temperature':min(settings['temperature'],.3)}
    raw,finish=engine.completion(base+[{'role':'user','content':brief}],tuning,cancel,schema=schema)
    try:
        raw=raw.strip()
        if raw.startswith('```'):raw=re.sub(r'^```(?:json)?\s*|\s*```$','',raw,flags=re.I)
        value=json.loads(raw)
        if finish=='length' or not isinstance(value,dict):raise ValueError()
        for key in keys:
            if not isinstance(value.get(key),str) or not value[key].strip() or len(value[key])>(1200 if key=='music_style' else 6000):raise ValueError()
    except (ValueError,TypeError):
        raise ValueError('Descrizione musicale incompleta: nessuna sintesi vocale o musicale avviata. Specifica genere e strumenti nel prompt oppure scegli Nessuna musica.') from None
    return plan|{k:value[k].strip() for k in keys}


def prompt_voice(prompt):
    """Only voice directions change settings; a character's gender is not a cue."""
    result={}
    names=list(re.finditer(r'\b(?:voce|timbro|narratrice)\s+(limpida|aurora)\b',prompt,re.I))
    if names:result['voice_profile']=names[-1][1].lower()
    mixed=r'\b(?:voci\s+(?:miste|alternate)|voce\s+mista|(?:alterna\w*|mix)\s+(?:le\s+)?voci|(?:voci|voce)\s+(?:maschile\s+e\s+femminile|femminile\s+e\s+maschile))\b'
    if re.search(mixed,prompt,re.I):result['voice_gender']='mixed'
    else:
        matches=list(re.finditer(r'\b(?:voce|narrazione|narratore|narratrice)\s+(?:narrante\s+)?(maschile|femminile|male|female)\b',prompt,re.I))
        if matches:result['voice_gender']='male' if matches[-1][1].lower() in ('maschile','male') else 'female'
    styles={'calda':'warm','seria':'serious','vivace':'lively','radio':'radio','spot':'spot'}
    matches=list(re.finditer(r'\b(?:voce|recitazione|narrazione)\s+(?:(?:maschile|femminile|mista)\s+)?(calda|seria|vivace|radio|spot)\b',prompt,re.I))
    if matches:result['voice_style']=styles[matches[-1][1].lower()]
    return result


def narration_disabled(prompt):
    """An instrumental backing track is not a request to mute the narrator."""
    for hit in re.finditer(r'\b(?:senza voce|senza narrazione|no voice)\b',prompt,re.I):
        if 'narrazione' in hit[0].lower():return True
        prefix=prompt[max(0,hit.start()-120):hit.start()]
        music=r'\b(?:base|musica|sottofondo|colonna sonora|brano|traccia|background music|soundtrack)\b[^.;:!?\n]{0,90}$'
        if not re.search(music,prefix,re.I):return True
    return False


def narration_parts(plan,gender,default_gender):
    first=default_gender if default_gender in ('female','male') else 'female'
    other='male' if first=='female' else 'female'
    return [{'text':s['narration'],'scene_id':i,'sentence_cues':True,
             'voice_fields':{'gender':(first if i%2==0 else other) if gender=='mixed' else first if gender=='auto' else gender}}
            for i,s in enumerate(plan['scenes'])]

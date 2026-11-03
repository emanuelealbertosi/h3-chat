"""Optional character inventory; generated parts share the ordinary image batch."""
import copy,re
from uuid import uuid4
from .motion_rigs import atlas_prompt,template,ACTIONS
from .downloads import safe_join


def extend_schema(schema):
    value=copy.deepcopy(schema)
    short=lambda n:{'type':'string','minLength':1,'maxLength':n}
    character={'type':'object','properties':{'id':short(64),'name':short(100),'appearance':short(1200)},'required':['id','name','appearance'],'additionalProperties':False}
    value['properties']['characters']={'type':'array','minItems':0,'maxItems':2,'items':character};value['required'].append('characters')
    scene=value['properties']['scenes']['items']
    scene['properties']['characters']={'type':'array','maxItems':2,'items':{'type':'object','properties':{'id':short(64),'action':{'type':'string','enum':list(ACTIONS)}},'required':['id','action'],'additionalProperties':False}}
    scene['required'].append('characters');return value


def brief(selected):
    existing=[{'id':s['id'],'name':s['name'],'description':s['description'],'actions':s['rig']['actions']} for s in selected if s.get('rig')]
    import json
    return ('\nPERSONAGGI ARTICOLATI SPERIMENTALI: pianifica al massimo due NUOVI personaggi in characters con id breve, name e appearance (aspetto, vestiti, colori e trattamento illustrativo precisi). appearance descrive SOLO il personaggio, senza gesti, posizione, sfondo, scritte o camera; questi appartengono alla scena. '
      'Non rigenerare quelli già selezionati: characters può essere vuoto quando riusi la raccolta. Per ogni scena scegli in characters quali id compaiono e action idle (posa naturale), wave (saluta) o point (indica con mano aperta). '
      'Usa solo personaggi necessari al prompt, al massimo due per scena; almeno una scena deve usarne uno. Per la prima versione non promettere camminate, prese, lip-sync o cambi di vista articolati. '
      'Ogni nuovo personaggio deriva da un unico foglio di parti coerenti. Gli scenari generati sono SENZA PERSONE: non disegnare doppi dei personaggi nell’immagine di fondo. '
      'Voce narrante fuori campo; personaggi non parlano in camera. Personaggi animabili già selezionati: '+json.dumps(existing,ensure_ascii=False))


def validate_plan(plan,selected):
    definitions=plan.get('characters');known={s['id'] for s in selected if s.get('rig')}
    if not isinstance(definitions,list) or len(definitions)>2:raise ValueError('Regia personaggi incompleta: massimo due nuove identità.')
    for item in definitions:
        if not isinstance(item,dict) or set(item)!={'id','name','appearance'}:raise ValueError('Identità del personaggio non valida.')
        if not isinstance(item['id'],str) or not re.fullmatch('[A-Za-z][A-Za-z0-9_-]{0,63}',item['id']) or item['id'] in known:raise ValueError('Identificativo personaggio non valido o duplicato.')
        if any(not isinstance(item[k],str) or not 1<=len(item[k].strip())<=n for k,n in [('name',100),('appearance',1200)]):raise ValueError('Descrivi nome e aspetto del personaggio.')
        known.add(item['id'])
    used=0
    for row in plan['scenes']:
        actors=row.get('characters')
        if not isinstance(actors,list) or len(actors)>2:raise ValueError('Regia scena: massimo due personaggi articolati.')
        seen=set()
        for actor in actors:
            if not isinstance(actor,dict) or set(actor)!={'id','action'} or not isinstance(actor['id'],str) or actor['id'] not in known or actor['id'] in seen or actor['action'] not in ACTIONS:raise ValueError('Regia scena: personaggio o azione non disponibili.')
            seen.add(actor['id']);used+=1
    if not used:raise ValueError('La regia non usa nessun personaggio articolato: nessuna generazione parti avviata.')
    return plan


def additional_plan(plan):
    return [{'slide':0,'role':'character_parts','character_id':c['id'],'prompt':atlas_prompt(c['appearance'],plan['visual_direction'])+' Output canvas aspect ratio 2:3.',
             'description':c['name'],'aspect':'2:3'} for c in plan['characters']]


def prepare(app,job,plan,selected,media,image_plan,cancel,stage,log):
    result=list(selected);mapping={s['id']:s['id'] for s in selected if s.get('rig')};prepared=[]
    for definition in plan['characters']:
        item=next(p for p in image_plan if p.get('character_id')==definition['id'] and p.get('role')=='character_parts')
        original=next(m for m in media if m['id']==item['asset_id']);folder=app.data/'outputs'/job['id']/'characters';folder.mkdir(parents=True,exist_ok=True)
        target=folder/(definition['id']+'.png');stage('Motion Graphics · trasparenza e parti di '+definition['name'])
        proof=app.engine.tool_call('motion-atlas-worker.py',{'input':str(safe_join(app.data,original['path'])),'output':str(target)},cancel,stage,log,timeout=120)
        asset={'id':uuid4().hex,'name':definition['name']+' · parti trasparenti','mime':'image/png','path':target.relative_to(app.data).as_posix()}
        actor=template(asset,proof['parts'],definition['name'],definition['appearance'],plan['visual_direction'])
        actor['preparation']=proof;result.append(actor);mapping[definition['id']]=actor['id'];prepared.append(asset)
    for row in plan['scenes']:
        row['characters']=[{'id':mapping[c['id']],'action':c['action']} for c in row['characters']]
    return result,prepared

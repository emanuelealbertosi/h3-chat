"""Versioned data-only motion scenes. Legacy HTML is never migrated implicitly."""
import copy
import json
import math
import re

EASINGS=('linear','easeIn','easeOut','easeInOut','step')
KINDS=('group','rect','ellipse','line','path','text','bar','counter','image')
NUMERIC={'x':(-32768,32768),'y':(-32768,32768),'scaleX':(0,8),'scaleY':(0,8),
         'rotation':(-7200,7200),'opacity':(0,1),'strokeWidth':(0,100),
         'barValue':(-1e9,1e9),'pathDraw':(0,1)}
TRANSFORMS={'x':0,'y':0,'scaleX':1,'scaleY':1,'rotation':0,'opacity':1}
FONTS=('Manrope','Cormorant','BebasNeue','Baloo2','Caveat','Bangers')

def error(path,message):raise ValueError('Motion Graphics · '+path+': '+message)

def fields(value,allowed,path):
    if not isinstance(value,dict):error(path,'oggetto JSON richiesto')
    extra=set(value)-set(allowed)
    if 'barValue' in extra:error(path,'barValue non è un campo dell’oggetto: usa value per il valore iniziale e tracks con property:"barValue" per animarlo. Non creare un secondo contatore per aggiungere una traccia.')
    if 'tracks2' in extra:error(path,'tracks2 non è consentito: unisci tutte le tracce nell’unico array tracks dello stesso oggetto.')
    if extra:error(path,'campi non consentiti: '+', '.join(sorted(extra))+'; usa solo '+', '.join(allowed))

def number(value,low,high,path):
    if type(value) not in (int,float) or not low<=value<=high or not math.isfinite(value):error(path,'numero fuori intervallo')
    return value

def color(value,path):
    if not isinstance(value,str) or not (value=='none' or re.fullmatch(r'#[0-9a-fA-F]{6}',value)):error(path,'colore esadecimale richiesto')
    return value

def identifier(value,path):
    if not isinstance(value,str) or not re.fullmatch(r'[A-Za-z][A-Za-z0-9_-]{0,63}',value):error(path,'identificativo non valido')
    return value

def svg_path(value,path):
    if not isinstance(value,str) or not value or len(value)>12000:error(path,'tracciato SVG non valido')
    tokens=re.findall(r'[MmLlHhVvCcSsQqTtAaZz]|[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?',value)
    rest=re.sub(r'[MmLlHhVvCcSsQqTtAaZz]|[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?','',value)
    if not tokens or tokens[0] not in ('M','m') or re.sub(r'[\s,]','',rest):error(path,'tracciato SVG non valido')
    counts={'M':2,'L':2,'H':1,'V':1,'C':6,'S':4,'Q':4,'T':2,'A':7,'Z':0};command=None;values=[]
    def check():
        arity=counts[command]
        if (not arity and values) or (arity and (not values or len(values)%arity)):error(path,'coordinate SVG incomplete')
        if command=='A' and any(values[i] not in (0,1) for start in range(0,len(values),7) for i in (start+3,start+4)):error(path,'flag arco non valido')
    for token in tokens:
        if token.upper() in counts:
            if command is not None:check()
            command=token.upper();values=[]
        else:values.append(number(float(token),-32768,32768,path))
    check()

def safe_data(value):
    stack=[(value,'scene',0,'')];count=0
    while stack:
        item,path,depth,key=stack.pop();count+=1
        if count>50000 or depth>16:error(path,'budget o profondità dei dati superati')
        if item is None:
            if key!='parentId':error(path,'valore nullo non consentito')
        elif type(item) is dict:
            for k,v in item.items():
                if not isinstance(k,str) or k in ('__proto__','constructor','prototype'):error(path,'chiave non consentita')
                stack.append((v,path+'.'+k,depth+1,k))
        elif type(item) is list:
            stack.extend((v,path+'['+str(i)+']',depth+1,'') for i,v in enumerate(item))
        elif type(item) is str:
            if len(item)>20000:error(path,'stringa oltre il budget')
            if any(0xD800<=ord(c)<=0xDFFF for c in item):error(path,'Unicode non valido')
        elif type(item) is int:pass
        elif type(item) is float:
            if not math.isfinite(item):error(path,'numero finito richiesto')
        elif type(item) is not bool:error(path,'sono ammessi solo dati JSON')


def validate(scene):
    safe_data(scene)
    fields(scene,('version','id','width','height','duration','background','objects','camera'), 'scene')
    if scene.get('version')!=2:error('version','versione non supportata')
    result=copy.deepcopy(scene);identifier(result.get('id'),'id')
    for axis in ('width','height'):number(result.get(axis),100,8192,axis)
    duration=number(result.get('duration'),.1,600,'duration');color(result.get('background'),'background')
    rows=result.get('objects')
    if not isinstance(rows,list) or not 1<=len(rows)<=256:error('objects','da 1 a 256 oggetti, senza troncamento')
    seen={};parents={}
    for index,obj in enumerate(rows):
        path='objects['+str(index)+']'
        fields(obj,('id','type','parentId','layer','width','height','anchor','transform','fill','stroke','strokeWidth',
                    'text','fontSize','fontFamily','path','value','maxValue','unit','tracks','visible','parallax','assetId','imageFit'),path)
        ident=identifier(obj.get('id'),path+'.id')
        if ident in seen:error(path+'.id','identificativo duplicato')
        seen[ident]=obj
        if obj.get('type') not in KINDS:error(path+'.type','primitiva non supportata')
        if obj['type']=='image':
            if not isinstance(obj.get('assetId'),str) or not re.fullmatch('[0-9a-f]{32}',obj['assetId']):error(path+'.assetId','immagine autorizzata richiesta')
            if obj.get('imageFit','contain') not in ('contain','cover'):error(path+'.imageFit','contain o cover richiesto')
        parents[ident]=obj.get('parentId')
        if parents[ident] is not None:identifier(parents[ident],path+'.parentId')
        number(obj.get('layer',0),-1000,1000,path+'.layer')
        number(obj.get('parallax',1),0,2,path+'.parallax')
        if obj.get('parentId') and obj.get('parallax',1)!=1:error(path+'.parallax','la parallasse si applica al gruppo principale')
        for axis in ('width','height'):number(obj.get(axis),1,16384,path+'.'+axis)
        anchor=obj.get('anchor',{'x':0,'y':0});fields(anchor,('x','y'),path+'.anchor')
        for axis in ('x','y'):number(anchor.get(axis,0),0,1,path+'.anchor.'+axis)
        obj['anchor']={'x':anchor.get('x',0),'y':anchor.get('y',0)}
        transform=obj.get('transform',{});fields(transform,TRANSFORMS,path+'.transform')
        obj['transform']=TRANSFORMS|transform
        for key,val in obj['transform'].items():number(val,*NUMERIC[key],path+'.transform.'+key)
        for key in ('fill','stroke'):
            obj[key]=color(obj.get(key,'none' if key=='stroke' else '#24C4D8'),path+'.'+key)
        number(obj.get('strokeWidth',0),0,100,path+'.strokeWidth')
        if type(obj.get('visible',True)) is not bool:error(path+'.visible','valore booleano richiesto')
        if obj.get('fontFamily','Manrope') not in FONTS:error(path+'.fontFamily','font locale non riconosciuto')
        number(obj.get('fontSize',32),8,400,path+'.fontSize')
        for key,limit in (('text',1200),('unit',30)):
            if not isinstance(obj.get(key,''),str) or len(obj.get(key,''))>limit:error(path+'.'+key,'testo troppo lungo o non valido')
        if obj['type']=='path' or 'path' in obj:
            svg_path(obj.get('path'),path+'.path')
        for key,default,bounds in (('value',0,(-1e9,1e9)),('maxValue',100,(.000001,1e9))):number(obj.get(key,default),*bounds,path+'.'+key)
        tracks=obj.get('tracks',[])
        if not isinstance(tracks,list) or len(tracks)>14:error(path+'.tracks','tracce non valide')
        properties=set()
        for ti,track in enumerate(tracks):
            tp=path+'.tracks['+str(ti)+']';fields(track,('property','keyframes'),tp);prop=track.get('property')
            if prop not in (*NUMERIC,'visible','fill','stroke','text') or prop in properties:error(tp+'.property','proprietà non supportata o duplicata')
            if prop=='barValue' and obj['type'] not in ('bar','counter'):error(tp+'.property','valore disponibile solo su barra o contatore')
            if prop=='pathDraw' and obj['type']!='path':error(tp+'.property','disegno disponibile solo su tracciato')
            if prop=='text' and obj['type']!='text':error(tp+'.property','testo disponibile solo su testo')
            properties.add(prop);keys=track.get('keyframes');previous=-1
            if not isinstance(keys,list) or not 1<=len(keys)<=128:error(tp,'da 1 a 128 keyframe')
            for ki,key in enumerate(keys):
                kp=tp+'.keyframes['+str(ki)+']';fields(key,('t','value','ease'),kp);stamp=number(key.get('t'),0,duration,kp+'.t')
                if stamp<=previous:error(kp+'.t','tempi strettamente crescenti richiesti')
                previous=stamp
                if key.get('ease','linear') not in EASINGS:error(kp+'.ease','easing non supportato')
                if prop in NUMERIC:number(key.get('value'),*NUMERIC[prop],kp+'.value')
                elif prop=='visible':
                    if type(key.get('value')) is not bool:error(kp+'.value','valore booleano richiesto')
                elif prop in ('fill','stroke'):color(key.get('value'),kp+'.value')
                elif not isinstance(key.get('value'),str) or len(key['value'])>1200:error(kp+'.value','testo non valido')
    for ident,parent in parents.items():
        chain={ident}
        while parent is not None:
            if parent not in seen or seen[parent]['type']!='group':error(ident+'.parentId','gruppo padre inesistente')
            if parent in chain:error(ident+'.parentId','gerarchia ciclica')
            chain.add(parent);parent=parents[parent]
    if len({o['assetId'] for o in rows if o['type']=='image'})>12:error('images','massimo dodici immagini distinte per scena')
    camera=result.get('camera',{});fields(camera,('keyframes',),'camera');keys=camera.get('keyframes',[]);previous=-1
    if not isinstance(keys,list) or len(keys)>128:error('camera','troppi keyframe')
    for i,key in enumerate(keys):
        path='camera.keyframes['+str(i)+']';fields(key,('t','x','y','zoom','ease'),path)
        stamp=number(key.get('t'),0,duration,path+'.t')
        if stamp<=previous:error(path+'.t','tempi strettamente crescenti richiesti')
        previous=stamp
        for axis in ('x','y'):number(key.get(axis),-32768,32768,path+'.'+axis)
        number(key.get('zoom'),.1,8,path+'.zoom')
        if key.get('ease','linear') not in EASINGS:error(path+'.ease','easing non supportato')
    result['camera']={'keyframes':keys}
    if sum(len(t['keyframes']) for o in rows for t in o.get('tracks',[]))+len(keys)>4096:error('keyframes','massimo 4096 keyframe per scena')
    if len(json.dumps(result,ensure_ascii=False,separators=(',',':')).encode('utf8'))>512000:error('scene','budget scena di 512000 byte superato')
    return result

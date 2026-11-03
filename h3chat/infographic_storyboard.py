"""Data-only motion scene authoring after measured narration is available."""
import copy,json,re
from pathlib import Path
from .downloads import Cancelled
from .infographic_scene import validate
from .motion_sprites import expand

EXAMPLE={'version':2,'id':'scene01','width':1280,'height':720,'duration':10,'background':'#F4F8FA','objects':[
 {'id':'rack','type':'group','layer':2,'width':220,'height':320,'transform':{'x':400,'y':260},'tracks':[{'property':'x','keyframes':[{'t':0,'value':-250},{'t':1.2,'value':400,'ease':'easeOut'}]}]},
 {'id':'box','type':'rect','parentId':'rack','width':220,'height':320,'fill':'#165467'},
 {'id':'led','type':'ellipse','parentId':'rack','width':20,'height':20,'transform':{'x':30,'y':30},'fill':'#FFB547'},
 {'id':'title','type':'text','layer':5,'parallax':0,'width':1100,'height':80,'text':'Dati illustrativi','fontSize':54,'fill':'#165467','transform':{'x':65,'y':65},'tracks':[{'property':'opacity','keyframes':[{'t':0,'value':0},{'t':1,'value':1}]}]}],
 'camera':{'keyframes':[{'t':0,'x':640,'y':360,'zoom':1},{'t':10,'x':680,'y':360,'zoom':1.08,'ease':'easeInOut'}]}}

BRIEF='''MOTION GRAPHICS 2D: produci SOLO JSON, nessun HTML, CSS, JavaScript, URL o callback.
Componi illustrazioni originali multilivello, gruppi articolati e movimenti di camera.
Il prompt, gli allegati e le fonti selezionate hanno priorità. Non inventare dati: numeri dimostrativi vanno etichettati come illustrativi.
Ogni oggetto ha id univoco, type (group,rect,ellipse,line,path,text,bar,counter), width,height e layer.
parentId deve indicare l'id di un oggetto con type:group presente in objects, MAI un text, counter, rect o un id inventato. Un oggetto radice senza padre usa parentId:null, mai la stringa vuota. Per un numero animato dentro un contenitore crea un group e un solo figlio counter; il contenitore non è un secondo counter. Le coordinate dei figli sono locali. transform: x,y,scaleX,scaleY,rotation,opacity.
L'origine locale dei figli è l'angolo superiore sinistro del gruppo, anche quando il gruppo usa anchor centrale. Un figlio centrato va a x=width/2,y=height/2 del gruppo con anchor0.5, non a x=0,y=0 con anchor0.5. Non applicare due volte lo spostamento dell'anchor. Mantieni i testi visibili interamente dentro il viewport anche con la camera.
I gruppi principali possono avere parallax0..2:0 sfondo fisso/HUD,1 movimento normale, valori intermedi per profondità. Nei figli parallax deve valere1.
anchor x,y da0a1. Colori solo #RRGGBB oppure none. Testo tramite text, fontFamily Manrope,Cormorant,BebasNeue,Baloo2,Caveat,Bangers, fontSize8..400.
Tracce: property x,y,scaleX,scaleY,rotation,opacity,fill,stroke,strokeWidth,visible,text,barValue,pathDraw.
keyframes ordinati con t in secondi entro duration, value, ease linear/easeIn/easeOut/easeInOut/step.
Una traccia mantiene il suo primo valore anche prima del primo keyframe e l'ultimo dopo la fine. Una proprietà senza traccia usa il valore base. Per entrate ritardate metti opacity0 nel primo keyframe e opacity1 alla fine dell'entrata: niente duplicati o lampi prima dell'inizio.
bar/counter: value,maxValue,unit. path: tracciato SVG statico. Nessun testo dentro un path.
counter.text è un prefisso oppure contiene il segnaposto {value}, sostituito dal numero; unit è il suffisso. Anima barValue con keyframe per barre/contatori richiesti animati: non lasciare contatori sempre a0. I titoli possono essere HUD con parallax0; riserva comunque coordinate locali corrette e spazio ai testi.
camera.keyframes: t,x,y,zoom,ease. Camera centrata sul viewport, zoom1 iniziale, movimenti morbidi senza tagliare testi.
Distribuisci le azioni lungo tutta la voce: entrate, pose, piccoli movimenti periodici con keyframe ripetuti, cambi di attenzione e uscite.
Non disegnare una slide statica: oggetti e livelli devono muoversi indipendentemente, mantenendo leggibili le informazioni.
Massimo96 oggetti prima dell'espansione sprite,256 dopo;4096 keyframe totali. Nessun troncamento silenzioso.
Scrivi JSON compatto, senza indentazione o spazi superflui. Non ripetere centinaia di keyframe simili: usa pochi momenti chiave con easing. Una scena non deve esaurire il budget per descrivere ogni dettaglio decorativo.
Un gruppo può usare spriteId SOLO dal catalogo selezionato: verrà inserita la grafica originale esatta senza rigenerarla.
Quando non vi sono sprite selezionati crea nuove primitive. Non ricostruire personaggi canonici dai soli nomi se sono disponibili riferimenti più specifici.
'''

def schema(width,height,duration,sprites,images):
    def number(low=-32768,high=32768):return {'type':'number','minimum':low,'maximum':high}
    def obj(properties):return {'type':'object','properties':properties,'required':list(properties),'additionalProperties':False}
    text=lambda maximum:{'type':'string','maxLength':maximum}
    ease={'type':'string','enum':['linear','easeIn','easeOut','easeInOut','step']}
    key=obj({'t':number(0,duration),'value':{'anyOf':[number(-1e9,1e9),text(1200),{'type':'boolean'}]},'ease':ease})
    track=obj({'property':{'type':'string','enum':['x','y','scaleX','scaleY','rotation','opacity','fill','stroke','strokeWidth','visible','text','barValue','pathDraw']},'keyframes':{'type':'array','minItems':1,'maxItems':128,'items':key}})
    common={'id':text(64),'parentId':{'type':['string','null'],'minLength':1,'maxLength':64,'pattern':'^[A-Za-z][A-Za-z0-9_-]{0,63}$'},'layer':number(-1000,1000),'parallax':number(0,2),'width':number(1,16384),'height':number(1,16384),'anchor':obj({'x':number(0,1),'y':number(0,1)}),'transform':obj({'x':number(),'y':number(),'scaleX':number(0,8),'scaleY':number(0,8),'rotation':number(-7200,7200),'opacity':number(0,1)}),'fill':text(7),'stroke':text(7),'strokeWidth':number(0,100),'visible':{'type':'boolean'},'tracks':{'type':'array','maxItems':14,'items':track}}
    fonts={'type':'string','enum':['Manrope','Cormorant','BebasNeue','Baloo2','Caveat','Bangers']};variants=[]
    for kind in ('group','rect','ellipse','line','path','text','bar','counter',*(['image'] if images else [])):
        props=common|{'type':{'type':'string','enum':[kind]}}
        if kind in ('text','counter'):props|={'text':text(1200),'fontSize':number(8,400),'fontFamily':fonts}
        if kind=='path':props['path']=text(12000)
        if kind in ('bar','counter'):props|={'value':number(-1e9,1e9),'maxValue':number(.000001,1e9),'unit':text(30)}
        if kind=='image':props|={'assetId':{'type':'string','enum':[i['id'] for i in images]},'imageFit':{'type':'string','enum':['contain','cover']}}
        variants.append(obj(props))
        if kind=='group':
            static=[s['id'] for s in sprites if not s.get('rig')];rigged=[s['id'] for s in sprites if s.get('rig')]
            if static:variants.append(obj(props|{'spriteId':{'type':'string','enum':static}}))
            if rigged:variants.append(obj(props|{'spriteId':{'type':'string','enum':rigged},'gesture':{'type':'string','enum':['idle','wave','point']},'actionStart':number(0,duration),'actionEnd':number(0,duration)}))
    return obj({'version':{'type':'integer','enum':[2]},'id':text(64),'width':{'type':'number','enum':[width]},'height':{'type':'number','enum':[height]},'duration':{'type':'number','enum':[duration]},'background':text(7),'objects':{'type':'array','minItems':1,'maxItems':96,'items':{'anyOf':variants}},'camera':obj({'keyframes':{'type':'array','maxItems':128,'items':obj({'t':number(0,duration),'x':number(),'y':number(),'zoom':number(.1,8),'ease':ease})}})})

def canonical_roots(scene):
    """Canonicalize only the unambiguous no-parent sentinel from author output.

    Never invent missing groups, remove links or change valid parent IDs.
    Saved-project validation remains strict and uses the canonical null value.
    """
    result=copy.deepcopy(scene)
    if isinstance(result,dict) and isinstance(result.get('objects'),list):
        for obj in result['objects']:
            if isinstance(obj,dict) and obj.get('parentId')=='':obj['parentId']=None
    return result


def paint_errors(scene):
    """Catch accidentally unpainted lettering, while retaining outlined text.

    Apply only to generated scenes, not an owner's deliberate editing choices.
    A later paint keyframe is allowed for an intentional reveal.
    """
    errors=[]
    for obj in scene.get('objects',[]):
        if obj.get('type') not in ('text','counter'):continue
        tracks={t['property']:t['keyframes'] for t in obj.get('tracks',[])}
        fills=[obj.get('fill','none'),*[k['value'] for k in tracks.get('fill',[])]]
        strokes=[obj.get('stroke','none'),*[k['value'] for k in tracks.get('stroke',[])]]
        widths=[obj.get('strokeWidth',0),*[k['value'] for k in tracks.get('strokeWidth',[])]]
        if not any(c!='none' for c in fills) and not (any(c!='none' for c in strokes) and any(w>0 for w in widths)):
            errors.append(obj['id']+': testo sempre invisibile, fill:none e nessun contorno visibile. Assegna un colore esadecimale leggibile al testo; non usare none come colore delle scritte.')
    return errors


def hierarchy_errors(scene):
    """Report related graph defects together so one repair can address them all."""
    if not isinstance(scene,dict) or not isinstance(scene.get('objects'),list):return []
    rows=[o for o in scene['objects'] if isinstance(o,dict)]
    by_id={o['id']:o for o in rows if isinstance(o.get('id'),str)};errors=[]
    for obj in rows:
        parent=obj.get('parentId');ident=obj.get('id','?')
        if parent is None:continue
        if not isinstance(parent,str) or parent not in by_id:
            errors.append(str(ident)+'.parentId: gruppo '+str(parent)+' inesistente')
        elif by_id[parent].get('type')!='group':
            errors.append(str(ident)+'.parentId: '+parent+' esiste ma è di tipo '+str(by_id[parent].get('type'))+', non group. Se è un contenitore trasformalo in group conservandone posizione e animazioni; il counter deve essere solo il figlio numerico')
        if obj.get('parallax',1)!=1:
            errors.append(str(ident)+'.parallax: per un figlio deve essere 1; la parallasse si configura solo sul gruppo principale')
        chain={ident};cursor=parent
        while isinstance(cursor,str) and cursor in by_id:
            if cursor in chain:
                errors.append(str(ident)+'.parentId: gerarchia ciclica');break
            chain.add(cursor);cursor=by_id[cursor].get('parentId')
    return errors[:24]


def generate(engine,base,row,width,height,duration,settings,cancel,stage,sprites=(),timing=None,images=(),verify=None,diagnostics=None,trace=None):
    catalog=[{k:s[k] for k in ('id','name','description','style','tags','palette')}|{'width':s['scene']['width'],'height':s['scene']['height'],**({'actions':s['rig']['actions']} if s.get('rig') else {})} for s in sprites]
    brief=BRIEF+'\nScena richiesta: '+json.dumps(row,ensure_ascii=False)+'\nDimensioni obbligatorie: '+str(width)+'x'+str(height)+', durata reale '+str(duration)+'s.\nTempi: '+json.dumps(timing or {})+'\nSprite selezionati: '+json.dumps(catalog,ensure_ascii=False)+'\nEsempio di struttura, NON di contenuto: '+json.dumps(EXAMPLE)
    brief+='\nImmagini autorizzate: '+json.dumps(images,ensure_ascii=False)+'. Per inserirle usa type:image, assetId esatto dal catalogo, width,height, imageFit contain o cover. Non deformare i soggetti, non sostituire gli allegati richiesti. Non inventare contenuti delle immagini non analizzate.'
    if any(s.get('rig') for s in sprites):brief+='\nPERSONAGGI ARTICOLATI: gli sprite con actions sono personaggi assemblati da parti coerenti. Inseriscili come type:group con spriteId, gesture idle|wave|point, actionStart e actionEnd entro la scena. Non inserire il loro foglio parti come immagine intera e non ridisegnarli con primitive. Il motore articola braccia, avambracci, testa e busto. width,height sono lo spazio finale: mantieni proporzioni circa600:800 e spazio per il braccio sollevato. In Scena.characters sono indicati i personaggi e i gesti richiesti: tutti devono comparire, con gesture corrispondente.'
    required_images={i['asset_id'] for i in row.get('illustrations',[]) if i.get('asset_id')}
    if required_images:brief+='\nILLUSTRAZIONI ASSEGNATE: inserisci effettivamente le immagini elencate in illustrations di questa scena, con type:image e assetId esatto. Sono state generate apposta: non ignorarle ridisegnando primitive al loro posto. Componile con testi, contatori, tracciati e livelli distinti, preservando le proporzioni. Non appiattire tutto in un poster statico. Segui visual_direction e continuity per raccordare questa inquadratura alle altre.'
    error='';previous='';shape=schema(width,height,duration,sprites,images)
    allowance=settings.get('max_tokens',16000)
    budget=min(allowance,max(16000,min(40000,round(duration*900))))
    for attempt in range(2):
        if cancel.is_set():raise Cancelled()
        stage('Motion Graphics · '+('correzione dati della scena' if attempt else 'oggetti, livelli e camera'))
        request=base+[{'role':'user','content':brief}]
        if previous:request+=[{'role':'assistant','content':previous},{'role':'user','content':'Ripara SOLO i dati non validi, conservando grafica, testi e regia. Non aggiungere campi non previsti. Errore preciso: '+error+'\nRestituisci l’intero JSON corretto.'}]
        elif error:request+=[{'role':'user','content':error+'\nRigenera la scena completa in JSON compatto, senza indentazione, con meno dettagli decorativi e pochi keyframe significativi. Mantieni contenuti, immagini autorizzate, durata e movimenti richiesti. Non continuare un frammento JSON troncato.'}]
        checked=[0]
        def progress(value):
            if len(value)>512000:raise ValueError('Motion Graphics: risposta oltre il budget della scena.')
            if len(value)-checked[0]>=512:
                checked[0]=len(value);tail=value[-1600:]
                if len(tail)==1600 and not tail.strip():raise ValueError('Motion Graphics: ripetizione senza avanzamento.')
                stage('Motion Graphics · dati della scena · '+str(len(value))+' caratteri')
        raw,finish=engine.completion(request,settings|{'think_level':'off','max_tokens':budget},cancel,on_text=progress,schema=shape)
        if diagnostics:
            folder=Path(diagnostics);folder.mkdir(parents=True,exist_ok=True);(folder/f'attempt-{attempt+1}.json.txt').write_text(raw,encoding='utf8')
            (folder/f'attempt-{attempt+1}.budget.json').write_text(json.dumps({'max_tokens':budget,'finish':finish,'characters':len(raw)}),encoding='utf8')
        try:
            if finish=='length':raise ValueError('Scena incompleta: aumenta Max token o riduci la complessità.')
            raw=re.sub(r'^```(?:json)?\s*|\s*```$','',raw.strip(),flags=re.I);scene=canonical_roots(json.loads(raw))
            problems=hierarchy_errors(scene)
            if problems:raise ValueError('Gerarchia della scena: '+'; '.join(problems))
            if scene.get('width')!=width or scene.get('height')!=height or abs(scene.get('duration',-1)-duration)>.001:raise ValueError('Dimensioni o durata diverse da quelle richieste.')
            used=[o.get('spriteId') for o in scene.get('objects',[]) if isinstance(o,dict) and o.get('spriteId')]
            for requested in row.get('characters',[]):
                if not any(o.get('spriteId')==requested['id'] and o.get('gesture')==requested['action'] for o in scene.get('objects',[])):raise ValueError('Personaggio o gesto richiesto ignorato: '+requested['id']+' · '+requested['action'])
            scene=expand(scene,sprites)
            authorized_images={m['id'] for m in images}|{m['id'] for s in sprites for m in s.get('media',[])}
            if any(o['type']=='image' and o['assetId'] not in authorized_images for o in scene['objects']):raise ValueError('Immagine non presente nel catalogo autorizzato.')
            missing=required_images-{o['assetId'] for o in scene['objects'] if o['type']=='image'}
            if missing:raise ValueError('Illustrazioni assegnate ignorate: inserisci type:image con assetId '+', '.join(sorted(missing)))
            unpainted=paint_errors(scene)
            if unpainted:raise ValueError('Leggibilità della scena: '+'; '.join(unpainted))
            if verify:verify(scene)
            if trace is not None:trace['sprites']=[{k:s[k] for k in ('id','name','sha256')}|{'instances':used.count(s['id'])} for s in sprites if s['id'] in used]
            return validate(scene)
        except (ValueError,TypeError,AttributeError) as exc:
            error=str(exc)[:6000];previous=raw
            if finish=='length':
                # Repeating the same truncated prefix under the same cap cannot
                # finish the graph. Retry once with more of the user's allowance.
                previous='';budget=min(allowance,max(budget+4000,budget*2))
            if diagnostics:(Path(diagnostics)/f'error-{attempt+1}.txt').write_text(error,encoding='utf8')
            if attempt:raise ValueError('Motion Graphics: scena non valida dopo una correzione. '+error) from None

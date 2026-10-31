"""Data-only motion scene authoring after measured narration is available."""
import json,re
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
parentId deve essere un gruppo esistente; le coordinate dei figli sono locali. transform: x,y,scaleX,scaleY,rotation,opacity.
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
    common={'id':text(64),'parentId':{'type':['string','null']},'layer':number(-1000,1000),'parallax':number(0,2),'width':number(1,16384),'height':number(1,16384),'anchor':obj({'x':number(0,1),'y':number(0,1)}),'transform':obj({'x':number(),'y':number(),'scaleX':number(0,8),'scaleY':number(0,8),'rotation':number(-7200,7200),'opacity':number(0,1)}),'fill':text(7),'stroke':text(7),'strokeWidth':number(0,100),'visible':{'type':'boolean'},'tracks':{'type':'array','maxItems':14,'items':track}}
    fonts={'type':'string','enum':['Manrope','Cormorant','BebasNeue','Baloo2','Caveat','Bangers']};variants=[]
    for kind in ('group','rect','ellipse','line','path','text','bar','counter',*(['image'] if images else [])):
        props=common|{'type':{'type':'string','enum':[kind]}}
        if kind in ('text','counter'):props|={'text':text(1200),'fontSize':number(8,400),'fontFamily':fonts}
        if kind=='path':props['path']=text(12000)
        if kind in ('bar','counter'):props|={'value':number(-1e9,1e9),'maxValue':number(.000001,1e9),'unit':text(30)}
        if kind=='image':props|={'assetId':{'type':'string','enum':[i['id'] for i in images]},'imageFit':{'type':'string','enum':['contain','cover']}}
        variants.append(obj(props))
        if kind=='group' and sprites:variants.append(obj(props|{'spriteId':{'type':'string','enum':[s['id'] for s in sprites]}}))
    return obj({'version':{'type':'integer','enum':[2]},'id':text(64),'width':{'type':'number','enum':[width]},'height':{'type':'number','enum':[height]},'duration':{'type':'number','enum':[duration]},'background':text(7),'objects':{'type':'array','minItems':1,'maxItems':96,'items':{'anyOf':variants}},'camera':obj({'keyframes':{'type':'array','maxItems':128,'items':obj({'t':number(0,duration),'x':number(),'y':number(),'zoom':number(.1,8),'ease':ease})}})})

def generate(engine,base,row,width,height,duration,settings,cancel,stage,sprites=(),timing=None,images=(),verify=None,diagnostics=None,trace=None):
    catalog=[{k:s[k] for k in ('id','name','description','style','tags','palette')}|{'width':s['scene']['width'],'height':s['scene']['height']} for s in sprites]
    brief=BRIEF+'\nScena richiesta: '+json.dumps(row,ensure_ascii=False)+'\nDimensioni obbligatorie: '+str(width)+'x'+str(height)+', durata reale '+str(duration)+'s.\nTempi: '+json.dumps(timing or {})+'\nSprite selezionati: '+json.dumps(catalog,ensure_ascii=False)+'\nEsempio di struttura, NON di contenuto: '+json.dumps(EXAMPLE)
    brief+='\nImmagini autorizzate: '+json.dumps(images,ensure_ascii=False)+'. Per inserirle usa type:image, assetId esatto dal catalogo, width,height, imageFit contain o cover. Non deformare i soggetti, non sostituire gli allegati richiesti. Non inventare contenuti delle immagini non analizzate.'
    error='';previous='';shape=schema(width,height,duration,sprites,images)
    for attempt in range(2):
        if cancel.is_set():raise Cancelled()
        stage('Motion Graphics · '+('correzione dati della scena' if attempt else 'oggetti, livelli e camera'))
        request=base+[{'role':'user','content':brief}]
        if previous:request+=[{'role':'assistant','content':previous},{'role':'user','content':'Ripara SOLO i dati non validi, conservando grafica, testi e regia. Non aggiungere campi non previsti. Errore preciso: '+error+'\nRestituisci l’intero JSON corretto.'}]
        checked=[0]
        def progress(value):
            if len(value)>512000:raise ValueError('Motion Graphics: risposta oltre il budget della scena.')
            if len(value)-checked[0]>=512:
                checked[0]=len(value);tail=value[-1600:]
                if len(tail)==1600 and not tail.strip():raise ValueError('Motion Graphics: ripetizione senza avanzamento.')
                stage('Motion Graphics · dati della scena · '+str(len(value))+' caratteri')
        budget=min(settings.get('max_tokens',12000),max(12000,min(40000,round(duration*600))))
        raw,finish=engine.completion(request,settings|{'think_level':'off','max_tokens':budget},cancel,on_text=progress,schema=shape)
        if diagnostics:
            folder=Path(diagnostics);folder.mkdir(parents=True,exist_ok=True);(folder/f'attempt-{attempt+1}.json.txt').write_text(raw,encoding='utf8')
        try:
            if finish=='length':raise ValueError('Scena incompleta: aumenta Max token o riduci la complessità.')
            raw=re.sub(r'^```(?:json)?\s*|\s*```$','',raw.strip(),flags=re.I);scene=json.loads(raw)
            if scene.get('width')!=width or scene.get('height')!=height or abs(scene.get('duration',-1)-duration)>.001:raise ValueError('Dimensioni o durata diverse da quelle richieste.')
            used=[o.get('spriteId') for o in scene.get('objects',[]) if isinstance(o,dict) and o.get('spriteId')];scene=expand(scene,sprites)
            if any(o['type']=='image' and o['assetId'] not in {m['id'] for m in images} for o in scene['objects']):raise ValueError('Immagine non presente nel catalogo autorizzato.')
            if verify:verify(scene)
            if trace is not None:trace['sprites']=[{k:s[k] for k in ('id','name','sha256')}|{'instances':used.count(s['id'])} for s in sprites if s['id'] in used]
            return validate(scene)
        except (ValueError,TypeError,AttributeError) as exc:
            error=str(exc)[:1800];previous=raw
            if diagnostics:(Path(diagnostics)/f'error-{attempt+1}.txt').write_text(error,encoding='utf8')
            if attempt:raise ValueError('Motion Graphics: scena non valida dopo una correzione. '+error) from None

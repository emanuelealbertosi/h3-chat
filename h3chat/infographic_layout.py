"""Portrait composition guidance and one measured LLM repair, never a template."""
import copy
import logging
from .downloads import Cancelled
from .slides import FORMATS
from .slide_html import validate

def brief(aspect):
    width,height=FORMATS[aspect]
    text=f'\nFORMATO VINCOLANTE: {aspect}, viewport {width} × {height:.2f} px, identico per TUTTE le scene. body e contenitore principale occupano tutta questa superficie, box-sizing:border-box. '
    if aspect=='9:16':
        text+='È una pagina VERTICALE, non una slide orizzontale inserita in un video verticale. Progetta la distribuzione dei contenuti su tutta l’altezza utile: diagrammi, immagini, titoli e blocchi proporzionati, leggibili su uno smartphone. Evita gruppi piccoli compressi nella metà superiore con una grande area vuota prima del footer. Non basta uno sfondo alto o un footer ancorato in basso. Puoi disporre fasi/card in verticale, ingrandire figure e tipografia o redistribuire la composizione; scegli TU la soluzione senza cambiare contenuti. Mantieni i margini e spazio negativo equilibrato, senza stirare immagini, deformare grafici o aggiungere fatti per riempire.'
    return text+' Rispetta eventuali richieste esplicite dell’utente di grandi spazi vuoti o composizione volutamente minimalista.'

def ensure(app,job,deck,index,media,request,settings,cancel,html,on_text,stage,log):
    motion=deck.get('infographic',{});opts=motion.get('options',{})
    if deck['format']!='9:16' or opts.get('layout','full')!='full' or opts.get('output','video')!='video':return html,None
    duration=motion['durations'][index]
    unavailable='Verifica dell’impaginazione verticale non disponibile: controlla la scena in Anteprima prima di esportarla.'
    def measure(value):
        probe=copy.deepcopy(deck);probe['pages']=[probe['pages'][index]|{'html':value,'status':'ready'}];probe['active']=0;probe['infographic']['durations']=[duration]
        try:
            result=app.engine.tool_call('infographic-worker.py',{'mode':'layout','data':str(app.data),'deck':probe,'media':media,'output':str(app.data/'outputs'/job['id']/'layout-check'/'unused.mp4')},cancel,stage,log,timeout=90)
            return result['pages'][0]
        except Cancelled:raise
        except Exception as exc:
            logging.getLogger(__name__).warning('Verifica layout verticale non disponibile: %s',exc)
            return None
    stage(f'Infografica · verifica composizione verticale · scena {index+1}')
    report=measure(html)
    if report is None:return html,unavailable
    if not report['issue']:return html,None
    stage(f'Infografica · adattamento AI al formato verticale · scena {index+1}')
    detail=f"Nel rendering reale il vuoto verticale più grande misura {report.get('largest_gap',0)} px ({round(report.get('gap_ratio',0)*100)}% dell’altezza)."
    if report.get('wrong_size'):detail+=f" Il body misura {report.get('body_width')} × {report.get('body_height')} px, invece di {report['width']} × {report['height']}."
    repair=request+[{'role':'assistant','content':html},{'role':'user','content':'Correggi l’impaginazione verticale della scena. '+detail+brief(deck['format'])+' Conserva dati, fonti, immagini autorizzate, narrazione, tempi ed effetti animati. Nessun nuovo testo per riempire, nessun JavaScript. Restituisci tutto l’HTML completo corretto.'}]
    raw,finish=app.engine.completion(repair,settings,cancel,on_text=on_text)
    if cancel.is_set():raise Cancelled()
    if finish=='length':raise ValueError('Impaginazione verticale incompleta: aumenta Max token.')
    html=validate(raw);report=measure(html)
    if report is None:return html,unavailable
    warning='La scena lascia ancora molto spazio vuoto o usa dimensioni diverse dal formato verticale: puoi chiedere un’altra impaginazione con Ricrea questa scena.' if report['issue'] else None
    return html,warning

"""Three presentation styles; continuous 2.5D uses the legacy compatible HTML scene."""
from html.parser import HTMLParser


def brief(opts):
    mode=opts.get('visual_mode','normal')
    if mode=='normal':return ''
    text=('\nSTILE DECORATIVO ILLUSTRATO: ambienti e illustrazioni curati, coerenti e ricchi di dettagli utili. '
          'Componi la pagina con HTML/CSS/SVG ricchi e tipografia espressiva ma leggibile. Evita grandi schede opache che nascondono le immagini. '
          'Il disegno può essere statico: anima in modo motivato titoli, dettagli e informazioni. Mantieni video, audio, griglie e pannelli richiesti dall’utente. ')
    if mode!='sequence':return text
    return text+('\nPIANO SEQUENZA 2.5D SIMULATO: camera continua contenuta sui piani visivi e dissolvenze morbide A PIENO QUADRO. '
      'Nessuna fascia di raccordo, fumo, nebbia, vignettatura grigia, blur a tutto schermo o pilastro gigante davanti alle immagini. '
      'Non applicare zoom o pan a tutto il contenitore: camera, accelerazioni e raccordi sono gestiti dal motore. '
      'Se l’ambiente è costruito da grafica usa TRE PIANI INDIPENDENTI: lontano data-depth="0.35" (cielo, parete lontana, panorama), '
      'medio data-depth="1" (edificio, arredi o illustrazione principale), vicino data-depth="1.65" (foglie, pilastri, strumenti o cornice ambientale). '
      'Usa wrapper HTML distinti con questi attributi e dimensioni esplicite, ciascuno con una propria grafica. Metti data-motion sui figli, NON sul wrapper data-depth. '
      'Niente wrapper di profondità annidati. Non copiare la stessa immagine intera in tutti e tre i livelli: usa elementi SVG/CSS o immagini pertinenti diverse. '
      'Se un’immagine è lo SFONDO, usala ampia come <img data-asset-id="ID" data-image-fit="cover"> nel wrapper data-depth="0.35" data-layer-role="background-image". '
      'NON ridisegnare cielo, pareti, edifici o scenari opachi in HTML/SVG davanti alla foto: lo sfondo è già l’immagine. '
      'Un eventuale fondale vettoriale ha data-layer-role="background-vector", è il livello più basso e resta SOTTO tutte le immagini. '
      'Con uno sfondo immagine bastano quel piano e i contenuti HUD a data-depth="0": non inventare altre scenografie per riempire tre piani. '
      'Eventuali dettagli vicini sono piccoli, con fondo trasparente, e lasciano libera l’immagine principale. '
      'I titoli stanno su un piano data-depth="0", fermi rispetto al viewport; falli entrare dopo l’arrivo della camera e uscire prima del raccordo. '
      'Con più pannelli conserva data-panel, la griglia e i video autorizzati: i piani stanno DENTRO ogni pannello. '
      'Con video di fondo lascia trasparenti pagina e piani decorativi; non coprire il filmato con una parete opaca. '
      'Palette, orizzonte, luce e direzione devono raccordarsi fra ambienti. Nessun colore di copertura o camera-occluder. Nessun personaggio a marionetta o persona che scivola fingendo una camminata. '
      'Questa è composizione 2.5D: non promettere ricostruzioni 3D o rotazioni che mostrino superfici non disponibili. ')


class Depths(HTMLParser):
    def __init__(self):super().__init__();self.values=set();self.invalid=False;self.stack=[];self.image_background=False;self.hud=False
    def handle_starttag(self,tag,attrs):
        from .pdf_export import VOID
        value=dict(attrs).get('data-depth')
        if dict(attrs).get('data-layer-role')=='background-image':self.image_background=True
        if value is not None:
            try:self.hud|=float(value)==0
            except ValueError:pass
        if value is not None and any(flag for _,flag in self.stack):self.invalid=True
        if tag not in VOID:self.stack.append((tag,value is not None))
        if value is None:return
        try:
            depth=float(value)
            if not 0<=depth<=2:raise ValueError()
            if depth>0:self.values.add(round(depth,2))
        except (ValueError,TypeError):self.invalid=True
    def handle_endtag(self,tag):
        for i in range(len(self.stack)-1,-1,-1):
            if self.stack[i][0]==tag:self.stack=self.stack[:i];break


def validate_layers(html):
    parser=Depths();parser.feed(html)
    ranges=(any(0<v<.75 for v in parser.values),any(.75<=v<=1.25 for v in parser.values),any(1.25<v<=2 for v in parser.values))
    if parser.invalid or not (all(ranges) or (parser.image_background and ranges[0] and parser.hud)):
        raise ValueError('Piano sequenza: usa piani non annidati. Con uno sfondo immagine bastano data-depth="0.35" data-layer-role="background-image" e contenuti HUD a data-depth="0". Per una scena soltanto vettoriale servono tre piani distinti .35, 1 e 1.65.')


def ensure(engine,request,settings,cancel,html,opts,writing,stage,planned=()):
    if opts.get('visual_mode')!='sequence':return html
    def check(value):
        from .slide_html import used_images
        missing=[p for p in planned if p['id'] not in used_images(value)]
        if missing:raise ValueError('Inserisci davvero le immagini già assegnate a questa scena: '+str(missing)+'. Usa <img data-asset-id="ID">; non sostituirle con un ambiente SVG/HTML. Se sono sfondi, data-layer-role="background-image", sotto i contenuti e sopra qualsiasi fondale vettoriale.')
        validate_layers(value)
    try:check(html);return html
    except ValueError as exc:error=str(exc)
    from .slide_html import generate
    stage('Piano sequenza · correzione dei piani di profondità')
    fixed=generate(engine,request+[{'role':'assistant','content':html},{'role':'user','content':error+' Conserva contenuti, stile, media e pannelli. '+brief(opts)+' Restituisci tutto HTML e CSS corretto.'}],settings,cancel,writing,stage,'Piano sequenza · profondità')
    check(fixed);return fixed

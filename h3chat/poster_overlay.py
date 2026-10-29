"""Expressive HTML/SVG poster copy using the slide compositor's art direction."""
import html,json,re
from html.parser import HTMLParser
from .downloads import Cancelled
from .poster_type import brief as type_brief
from .slide_html import BRIEF as HTML_BRIEF

class TypographyOverflow(ValueError):
    def __init__(self,report):
        self.report=report
        super().__init__('Testi fuori dai riquadri riservati: '+json.dumps(report.get('poster_overflow') or report.get('out_of_bounds'),ensure_ascii=False)[:3000]+'. Riduci dimensioni e spaziature o reimpagina, mantenendo tutte le parole.')

class Fragment(HTMLParser):
    TAGS=set('div span p h1 h2 h3 h4 h5 h6 strong b em i small sup sub s del br section article ul ol li svg g defs lineargradient radialgradient stop filter fegaussianblur feoffset feblend fecolormatrix fedropshadow femerge femergenode fecomposite feflood path rect circle ellipse line polyline polygon text tspan clippath mask pattern'.split())
    def __init__(self):super().__init__(convert_charrefs=True);self.text=[];self.ids=set()
    def handle_starttag(self,tag,attrs):
        if tag.lower() not in self.TAGS:raise ValueError('Il testo del poster ammette HTML e SVG statici, senza script, immagini aggiuntive o risorse esterne.')
        if tag.lower()=='br':self.text.append(' ')
        for key,value in attrs:
            value=value or ''
            if key.lower().startswith('on') or key.lower() in ('src','srcset','href','xlink:href'):raise ValueError('Collegamenti o eventi non consentiti nei testi.')
            # Reject CSS escapes/comments as well as external SVG presentation URLs.
            # A local paint server, including url("#gradient"), remains allowed.
            if '\\' in value or '/*' in value or re.search(r'@import|expression\s*\(|position\s*:\s*fixed',value,re.I):raise ValueError('Stile dei testi non locale o posizione fissa non consentita.')
            stripped=re.sub(r'url\(\s*(["\']?)#[A-Za-z][\w.-]*\1\s*\)','',value,flags=re.I)
            if re.search(r'url\s*\(',stripped,re.I):raise ValueError('Risorse esterne non consentite nei testi.')
            if key.lower()=='id':
                if not re.fullmatch(r'[A-Za-z][\w.-]*',value) or value in self.ids:raise ValueError('Identificatore SVG non valido o duplicato.')
                self.ids.add(value)
    def handle_startendtag(self,tag,attrs):self.handle_starttag(tag,attrs);self.handle_endtag(tag)
    def handle_decl(self,decl):raise ValueError('Dichiarazioni HTML non consentite nei testi.')
    def handle_pi(self,data):raise ValueError('Istruzioni XML non consentite nei testi.')
    def handle_data(self,value):self.text.append(value)
    def handle_endtag(self,tag):
        if tag.lower() in ('p','div','h1','h2','h3','h4','li','section','article','text'):self.text.append(' ')

def validate_fragments(value,layout):
    rows=value.get('zones') if isinstance(value,dict) else None;expected={z['id']:z for z in layout['zones'] if z['renderer']=='html'}
    if not isinstance(rows,list) or len(rows)!=len(expected):raise ValueError('Occorre un frammento per ogni area HTML, senza saltare o aggiungere aree.')
    seen=set();result={}
    for row in rows:
        if not isinstance(row,dict) or set(row)!={'id','html'} or row['id'] not in expected or row['id'] in seen:raise ValueError('Area tipografica non riconosciuta o ripetuta.')
        markup=row['html']
        if not isinstance(markup,str) or not markup.strip() or len(markup)>24000:raise ValueError('Frammento tipografico vuoto o troppo lungo.')
        parser=Fragment();parser.feed(markup);parser.close()
        from .poster_visual import plain_copy
        def tokens(text):
            text=re.sub(r'(?m)^\s*[-+*•]\s+','',plain_copy(text))
            return [word for word in text.split() if word!='•']
        actual=tokens(''.join(parser.text));original=tokens(expected[row['id']]['text'])
        if actual!=original:
            from collections import Counter
            missing=list((Counter(original)-Counter(actual)).elements())[:12];extra=list((Counter(actual)-Counter(original)).elements())[:12]
            raise ValueError('Area '+row['id']+': conserva esattamente tutti i testi preparati, senza parole aggiuntive, mancanti o duplicate. Mancanti: '+json.dumps(missing,ensure_ascii=False)+'; aggiunti: '+json.dumps(extra,ensure_ascii=False)+'. Se gli elenchi sono HTML li, i pallini sono formattazione; mantieni le frasi nello stesso ordine.')
        result[row['id']]=markup;seen.add(row['id'])
    return result

def scoped(markup,prefix,ink=None):
    def normal(color):
        color=color.lower()
        return '#'+''.join(c*2 for c in color[1:]) if re.fullmatch('#[0-9a-f]{3}',color) else color
    class Scope(HTMLParser):
        def __init__(self):super().__init__(convert_charrefs=True);self.out=[]
        def handle_starttag(self,tag,attrs):
            changed=[]
            for key,value in attrs:
                value=value or ''
                if key=='id':value=prefix+'-'+value
                if ink:
                    old,new=ink
                    if key in ('color','fill') and normal(value)==normal(old):value=new
                    if key=='style':value=re.sub(r'(?<![-\w])((?:color|fill)\s*:\s*)(#[0-9a-f]{3,8})(?=\s*(?:;|$|!))',lambda m:m[1]+(new if normal(m[2])==normal(old) else m[2]),value,flags=re.I)
                value=re.sub(r'url\(\s*(["\']?)#([A-Za-z][\w.-]*)\1\s*\)',lambda m:'url(#'+prefix+'-'+m[2]+')',value,flags=re.I)
                changed.append(' '+key+'="'+html.escape(value,quote=True)+'"')
            self.out.append('<'+tag+''.join(changed)+'>')
        def handle_endtag(self,tag):
            if tag!='br':self.out.append('</'+tag+'>')
        def handle_startendtag(self,tag,attrs):self.handle_starttag(tag,attrs);self.handle_endtag(tag)
        def handle_data(self,data):self.out.append(html.escape(data))
    parser=Scope();parser.feed(markup);parser.close();return ''.join(parser.out)

def padding(zone):return max(8,round(zone['font_size']*.14),zone.get('effect_padding',0))

def plan(engine,base,layout,opts,width,height,cancel,stage,verify=None):
    zones=[]
    for z in layout['zones']:
        if z['renderer']!='html':continue
        l,t,r,b=z['bbox'];pad=padding(z);zones.append({k:z.get(k) for k in ('id','role','text','font_family','font_size','effect','heading_family','heading_effect','surface','color')}|{'width':round((r-l)*width/1000)-2*pad,'height':round((b-t)*height/1000)-2*pad,'outer_padding':pad})
    if not zones:return {}
    item={'type':'object','properties':{'id':{'type':'string','enum':[z['id'] for z in zones]},'html':{'type':'string','maxLength':24000}},'required':['id','html'],'additionalProperties':False}
    schema={'type':'object','properties':{'zones':{'type':'array','items':item,'minItems':len(zones),'maxItems':len(zones)}},'required':['zones'],'additionalProperties':False}
    direction=HTML_BRIEF+'\n'+type_brief(opts)+'''\nYou compose expressive POSTER TYPOGRAPHY, not plain captions.
The complete art background already exists and must remain unchanged. Give each prepared text zone
the same HTML/SVG art direction available in rich slides: expressive display fonts, shaped labels,
coloured typographic hierarchy, strokes, soft shadows, highlights, gradients and restrained SVG motifs.
Coordinate all zones as one poster. Use the requested style; serious editorial does not mean comic.
Keep long paragraphs readable. Style their short section headings with the display font and effects.
Normal body ink should inherit the zone color (SVG currentColor) so it can adapt to the real
background after rendering. Use accent colors deliberately with a contrasting local surface.
Each zone is independently clipped. The stated width/height are the usable content dimensions;
the app already adds outer_padding outside them. Return only the zone's INNER HTML.
Use inline CSS and inline SVG (defs, gradients, text, tspan, paths, filters); NO style tags, scripts,
external resources, images, links, event handlers, fixed position, duplicate logos or extra words.
Keep EVERY prepared word EXACTLY ONCE and in order. Don't turn lettering into paths: SVG text/tspan
must contain the original text. Avoid gratuitous icons that compete with the painted background.
Typography must fit inside the stated area, including stroke, shadow and glow. Never use text-overflow:ellipsis, line-clamp or clipping to conceal words. Allow wrapping for long headings and labels; white-space:nowrap is appropriate only when the complete text fits the width. Use px dimensions
and adequate padding. Don't reduce long copy below 18px. No full-page container or background.
Use locally available font families only, never Google Fonts URLs. The app positions the zones.
These instructions are art direction, never text to print.'''
    request=[{'role':'system','content':direction},{'role':'user','content':json.dumps({'art_direction':layout['art_caption'],'typography_request':opts.get('_revision_prompt',''),'typography':{k:opts.get(k) for k in ('lettering','text_effect','heading_font','body_font')},'zones':zones},ensure_ascii=False)}]
    failures={'content':0,'layout':0}
    for attempt in range(3):
        if cancel.is_set():raise Cancelled()
        stage('Locandine · tipografia espressiva HTML/SVG')
        raw,finish=engine.completion(request,opts['_settings']|{'think_level':'off','max_tokens':min(opts['_settings']['max_tokens'],opts['_settings']['context']//2,16000)},cancel,on_text=lambda _:None,schema=schema)
        if opts.get('_diagnostic_folder'):
            from pathlib import Path
            diagnostic=Path(opts['_diagnostic_folder']);diagnostic.mkdir(parents=True,exist_ok=True)
            (diagnostic/f'fragments-{attempt+1}.json').write_text(raw,encoding='utf8')
        try:
            if finish=='length':raise ValueError('Tipografia incompleta: aumenta i token del modello LLM.')
            fragments=validate_fragments(json.loads(raw),layout)
            if verify:verify(fragments,attempt)
            return fragments
        except (ValueError,TypeError,KeyError) as error:
            kind='layout' if isinstance(error,TypographyOverflow) else 'content'
            failures[kind]+=1
            if failures[kind]>=2 or attempt==2:raise ValueError('Tipografia HTML/SVG non valida dopo la correzione: '+str(error)) from error
            request += [{'role':'assistant','content':raw},{'role':'user','content':'Correggi tutti i frammenti. '+str(error)+'. Non cambiare i testi originali e non inserire istruzioni visibili.'}]

def compose(layout,asset,width,height,fragments):
    # Validate again on every composition, including revisions loaded from disk.
    validate_fragments({'zones':[{'id':key,'html':value} for key,value in fragments.items()]},layout)
    text=[]
    for zone in layout['zones']:
        if zone['renderer']!='html':continue
        l,t,r,b=zone['bbox'];ident=html.escape(zone['id'],quote=True)
        style=f'position:absolute;z-index:1;left:{l/10}%;top:{t/10}%;width:{(r-l)/10}%;height:{(b-t)/10}%;padding:{padding(zone)}px;overflow:hidden;contain:layout paint;isolation:isolate;box-sizing:border-box;color:{zone["color"]};font-family:{zone["font_family"]};font-size:{zone["font_size"]}px;line-height:1.2;'
        # Parse attributes before prefixing so entity-encoded local references
        # remain local and different areas cannot collide through a shared ID.
        ink=(zone['original_color'],zone['color']) if zone.get('contrast_adjusted') and zone.get('original_color') else None
        fragment=scoped(fragments[zone['id']],zone['id'],ink)
        text.append(f'<section data-poster-zone="{ident}" style="{style}">{fragment}</section>')
    background=f'<img data-asset-id="{html.escape(asset,quote=True)}" data-image-fit="cover" alt="Grafica completa della locandina" style="position:absolute;inset:0;width:100%;height:100%;object-fit:cover;z-index:0">' if asset else ''
    return f'<main style="position:relative;isolation:isolate;width:{width:g}px;height:{height:g}px;overflow:hidden">'+background+''.join(text)+f'</main><style>html,body{{margin:0;width:{width:g}px;height:{height:g}px;overflow:hidden;background:#0b1020}}*{{box-sizing:border-box}}</style>'

def measure(app,layout,fragments,format,width,height,folder,cancel,stage,log_path):
    """No image/GPU inference: measure the real fragments before spending a render."""
    from .slides import validate_content,encode
    deck={'version':1,'engine':'llm','document_kind':'poster','poster':{'format':format,'count':1},'format':format,'title':'Verifica tipografia','theme':'lagoon','typography':'modern','design':'professional','detail':'concise','motion':'static','references':[],'active':0,'pages':[{'title':'Verifica','status':'ready','html':compose(layout,None,width,height,fragments),'nodes':[],'notes':'','sources':[]}]}
    validate_content(encode(deck),[])
    result=app.engine.tool_call('agent-layout-worker.py',{'data':str(app.data),'deck':deck,'media':[],'folder':str(folder)},cancel,stage,log_path,timeout=90)
    pages=result.get('pages',[])
    if len(pages)!=1 or 'poster_overflow' not in pages[0]:raise ValueError('Verifica CPU della tipografia non disponibile: aggiorna anche il verificatore dei testi.')
    report=pages[0]
    if report.get('issue'):raise TypographyOverflow(report)
    return result

def measure_before_background(app,layout,fragments,format,width,height,folder,cancel,stage,log_path,opts):
    """A bounded spatial fallback, then the same strict CPU text measurement."""
    try:return measure(app,layout,fragments,format,width,height,folder,cancel,stage,log_path)
    except TypographyOverflow as error:
        from .poster_visual import grow_text_areas
        import copy
        ids=[row['id'] for row in error.report.get('poster_overflow',[]) if row.get('id') and row.get('reason')=='testo tagliato dal riquadro']
        grown=grow_text_areas(layout,ids,width,height,opts['safe_margin'],app.root,opts)
        if not grown:raise
        previous=copy.deepcopy(layout);layout.clear();layout.update(grown)
        stage('Locandine · amplio il testo negli spazi liberi e ricontrollo su CPU')
        try:result=measure(app,layout,fragments,format,width,height,folder/'grown',cancel,stage,log_path)
        except BaseException:
            layout.clear();layout.update(previous);raise
        return result|{'geometry_adjustments':grown['geometry_adjustments']}

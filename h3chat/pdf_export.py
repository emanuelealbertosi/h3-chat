"""Print sanitized canvas markup with the bundled Windows browser engine.

No JavaScript, network, local file URLs or form controls from document content.
Text and SVG stay vector-based in the PDF; chart canvases arrive as PNG data URIs.
"""
import base64
import html
import os
import re
import subprocess
import time
from html.parser import HTMLParser
from pathlib import Path
from .store import uid
from .engine import CREATE_NO_WINDOW

ALLOWED=set(('article div span p h1 h2 h3 h4 h5 h6 strong b em i s del sup sub br hr blockquote ul ol li pre code table thead tbody tr th td figure figcaption img '
             'svg g path rect circle ellipse line polyline polygon text tspan defs marker clipPath mask pattern linearGradient radialGradient stop use title desc '
             'math semantics mrow mi mn mo msup msub mfrac mroot msqrt mtable mtr mtd annotation').lower().split())
VOID={'br','hr','img'}


class Sanitizer(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True);self.output=[];self.skipped=0
    def handle_starttag(self,tag,attrs):
        if tag in ('script','style','iframe','object'):
            self.skipped+=1;return
        if self.skipped or tag not in ALLOWED:return
        clean=[]
        for key,value in attrs:
            value=value or ''
            if key.lower().startswith('on') or key in ('srcset','formaction'):continue
            if key in ('src','href','xlink:href') and not (value.startswith('#') or (tag=='img' and re.match(r'^data:image/(png|jpeg);base64,',value))):continue
            if key=='style' and any(x in value.lower() for x in ('url(','expression','@import')):continue
            if key=='class':value=' '.join(x for x in value.split() if x not in ('no-export','canvas-preview'))
            clean.append(f' {key}="{html.escape(value,quote=True)}"')
        self.output.append('<'+tag+''.join(clean)+'>')
    def handle_endtag(self,tag):
        if tag in ('script','style','iframe','object'):
            self.skipped=max(0,self.skipped-1);return
        if not self.skipped and tag in ALLOWED and tag not in VOID:self.output.append('</'+tag+'>')
    def handle_data(self,data):
        if not self.skipped:self.output.append(html.escape(data))


def embedded_css(root):
    sheets=[]
    for relative in ('style.css','vendor/katex.min.css','vendor/highlight.css'):
        file=root/'static'/relative
        def replace(match):
            name=match.group(1).strip('"\'')
            path=root/name.lstrip('/') if name.startswith('/static/') else file.parent/name
            if not path.resolve().is_relative_to((root/'static').resolve()) or not path.is_file():return 'url()'
            mime='font/woff2' if path.suffix=='.woff2' else 'font/ttf' if path.suffix=='.ttf' else 'font/woff'
            return 'url(data:'+mime+';base64,'+base64.b64encode(path.read_bytes()).decode()+')'
        sheets.append(re.sub(r'url\(([^)]+)\)',replace,file.read_text(encoding='utf-8')))
    return '\n'.join(sheets)


def export_pdf(root,data,body):
    source=body.get('html','');title=body.get('title','Documento H3')
    if not isinstance(source,str) or len(source)>16*1024*1024 or not isinstance(title,str) or len(title)>150:raise ValueError('Documento non valido o troppo grande.')
    parser=Sanitizer();parser.feed(source)
    candidates=[Path(os.environ.get('PROGRAMFILES(X86)','C:/Program Files (x86)'))/'Microsoft/Edge/Application/msedge.exe',
                Path(os.environ.get('PROGRAMFILES','C:/Program Files'))/'Microsoft/Edge/Application/msedge.exe']
    edge=next((p for p in candidates if p.exists()),None)
    if not edge:raise ValueError('Per il PDF serve Microsoft Edge, normalmente incluso in Windows.')
    key=uid();folder=data/'exports'/key;folder.mkdir(parents=True)
    css=embedded_css(root)+'''
      @page {size:A4;margin:18mm 17mm;} body{background:white;margin:0;color:#202f30;}
      .rich{font-size:11pt;line-height:1.65;max-width:none;overflow:visible;}
      .rich h1{font-size:29pt}.rich h2{font-size:18pt}.rich h3{font-size:14pt}
      h1,h2,h3,h4{break-after:avoid} p{orphans:3;widows:3}
      pre{white-space:pre-wrap!important;overflow:visible!important} pre code{white-space:pre-wrap;overflow-wrap:anywhere}
      table{width:100%;table-layout:fixed} th,td{overflow-wrap:anywhere} thead{display:table-header-group} tr{break-inside:avoid}
      figure,.math-block{break-inside:avoid;max-width:100%} .chart-box{height:auto} img{max-width:100%;height:auto;max-height:220mm}
      .no-export{display:none!important} .rich .math-block{overflow:visible}.visual-label{font-size:9pt}
    '''
    document='<!doctype html><meta charset="utf-8"><meta http-equiv="Content-Security-Policy" content="default-src \'none\'; style-src \'unsafe-inline\'; img-src data:; font-src data:; script-src \'none\'"><title>'+html.escape(title)+'</title><style>'+css+'</style><article class="rich">'+''.join(parser.output)+'</article>'
    source_file=folder/'document.html';source_file.write_text(document,encoding='utf-8')
    target=folder/'document.pdf'
    args=[str(edge),'--headless','--disable-gpu','--no-first-run','--no-pdf-header-footer','--print-to-pdf='+str(target),
          '--user-data-dir='+str(folder/'browser-profile'),'--virtual-time-budget=2500',source_file.as_uri()]
    result=subprocess.run(args,capture_output=True,timeout=90,creationflags=CREATE_NO_WINDOW)
    # Windows Edge may return from its launcher while the browser child is still printing.
    deadline=time.monotonic()+60
    while time.monotonic()<deadline:
        if target.is_file():
            try:
                raw=target.read_bytes()
                if raw.startswith(b'%PDF-') and b'%%EOF' in raw[-100:]:break
            except OSError:pass
        time.sleep(.2)
    if not target.is_file() or target.read_bytes()[:5]!=b'%PDF-' or b'%%EOF' not in target.read_bytes()[-100:]:raise RuntimeError('Esportazione PDF non riuscita. '+result.stderr.decode('utf-8','replace')[-800:])
    return {'url':'/exports/'+key+'/document.pdf','name':title+'.pdf'}

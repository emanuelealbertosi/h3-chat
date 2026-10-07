"""Isolated HTML frames and embedded authorized assets for offline rendering."""
import base64
import html
import re
from html.parser import HTMLParser
from pathlib import Path
from .downloads import safe_join
from .pdf_export import ALLOWED,VOID
from .slides import FORMATS
from .slide_html import source

class Clean(HTMLParser):
    def __init__(self,data,media):
        super().__init__();self.data=Path(data);self.assets={m['id']:m for m in media if m.get('mime') in ('image/png','image/jpeg')};self.out=[];self.skipped=0;self.style=False
    def handle_starttag(self,tag,attrs):
        if tag in ('script','iframe','object','embed','form','video','audio'):self.skipped+=1;return
        if self.skipped:return
        if tag=='style':self.style=True;self.out.append('<style>');return
        if tag not in ALLOWED:return
        clean=[]
        for key,value in attrs:
            value=value or ''
            if key.startswith('on') or key.startswith('data-h3-') or key in ('src','srcset','action','formaction','autofocus'):continue
            if key in ('href','xlink:href') and not value.startswith('#'):continue
            if key=='style' and re.search(r'expression|@import',value,re.I):continue
            clean.append(' '+key+'="'+html.escape(value,quote=True)+'"')
        if tag=='img':
            asset=self.assets.get(dict(attrs).get('data-asset-id'))
            if not asset:return
            file=safe_join(self.data,asset['path'])
            if file.stat().st_size>16*1024**2:raise ValueError('Immagine infografica oltre 16 MB.')
            clean.append(' src="data:'+asset['mime']+';base64,'+base64.b64encode(file.read_bytes()).decode()+'"')
        self.out.append('<'+tag+''.join(clean)+'>')
    def handle_endtag(self,tag):
        if tag in ('script','iframe','object','embed','form','video','audio'):self.skipped=max(0,self.skipped-1);return
        if self.skipped:return
        if tag=='style':self.style=False;self.out.append('</style>');return
        if tag in ALLOWED and tag not in VOID:self.out.append('</'+tag+'>')
    def handle_data(self,data):
        if self.skipped:return
        # CSP independently denies network and script, including escaped CSS URLs.
        if self.style:self.out.append(re.sub(r'@import[^;]*;','',data,flags=re.I).replace('</','< /'))
        else:self.out.append(html.escape(data))

def document(root,data,deck,media):
    width,height=FORMATS[deck['format']];frames=[];root=Path(root)
    opts=deck.get('infographic',{}).get('options',{});radius={'square':0,'soft':48,'round':110}.get(opts.get('corners','square'),0);background='#f5f4ef' if opts.get('frame')=='light' else '#101820'
    fonts=''
    for name in ('Manrope','Cormorant'):
        file=root/'static'/(name+'.ttf')
        if file.is_file():fonts+='@font-face{font-family:'+name+';src:url(data:font/ttf;base64,'+base64.b64encode(file.read_bytes()).decode()+')}'
    math_css=''
    if any('$' in page.get('html','') for page in deck['pages']):
        file=root/'static/vendor/katex.min.css'
        if file.is_file():
            def math_font(match):
                name=match[1].strip('"\'')
                if not re.fullmatch(r'fonts/KaTeX_[\w-]+\.woff2',name):return 'url(data:font/woff;base64,)'
                font=root/'static/vendor'/name
                return 'url(data:font/woff2;base64,'+base64.b64encode(font.read_bytes()).decode()+')' if font.is_file() else 'url(data:font/woff;base64,)'
            math_css=re.sub(r'url\(([^)]+)\)',math_font,file.read_text(encoding='utf-8'))
    csp="default-src 'none'; style-src 'unsafe-inline'; img-src data:; font-src data:; script-src 'none'; connect-src 'none'; form-action 'none'"
    video=deck.get('infographic',{}).get('video');backdrop=''
    if video:
        from .infographic_video import asset,validate
        validate(video);asset(data,media,video['asset_id'],'video/mp4')
        poster=asset(data,media,video['poster_id'],'image/jpeg')
        if poster.stat().st_size>16*1024**2:raise ValueError('Anteprima video troppo grande.')
        backdrop='<style>body{position:relative!important;isolation:isolate;background:transparent!important;height:'+str(height)+'px}html{background:#101820}img[data-h3-video]{position:absolute!important;inset:0!important;z-index:-1!important;width:100%!important;height:100%!important;max-width:none!important;max-height:none!important;object-fit:'+video['fit']+'!important;pointer-events:none!important}</style><img data-h3-video data-h3-trusted src="data:image/jpeg;base64,'+base64.b64encode(poster.read_bytes()).decode()+'">'
    for i,page in enumerate(deck['pages']):
        cleaner=Clean(data,media);cleaner.feed(source(page.get('html','')))
        inner='<!doctype html><html lang="it"><head><meta charset="utf-8"><meta http-equiv="Content-Security-Policy" content="'+html.escape(csp,quote=True)+'"><style>html,body{margin:0;width:'+str(width)+'px;height:'+str(height)+'px;overflow:hidden}*,*:before,*:after{box-sizing:border-box;animation:none!important;transition:none!important}'+fonts+math_css+'</style></head><body>'+''.join(cleaner.out)+backdrop+'</body></html>'
        frames.append('<iframe sandbox="allow-same-origin" data-h3-scene="'+str(i)+'" style="position:absolute;inset:0;width:100%;height:100%;border:0" srcdoc="'+html.escape(inner,quote=True)+'"></iframe>')
    return '<!doctype html><html style="background:'+background+'"><head><meta charset="utf-8"><meta http-equiv="Content-Security-Policy" content="default-src \'none\'; frame-src \'self\'; style-src \'unsafe-inline\'; img-src data:; font-src data:; script-src \'none\'; connect-src \'none\'"></head><body style="margin:0;width:'+str(width)+'px;height:'+str(height)+'px;overflow:hidden;clip-path:inset(0 round '+str(radius)+'px);background:'+background+'">'+''.join(frames)+'</body></html>'

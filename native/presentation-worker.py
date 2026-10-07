"""Bounded slide import: PDF/image rendering and portable PPTX layout extraction."""
import base64
import html
import io
import json
import os
import posixpath
import sys
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]
RUNTIME=ROOT/'runtime/tools/documents';sys.path[:0]=[str(ROOT),str(RUNTIME)]
dll=os.add_dll_directory(str(RUNTIME)) if os.name=='nt' and RUNTIME.is_dir() else None
wire=sys.stdout;sys.stdout=sys.stderr
def emit(event,**kw):wire.write(json.dumps({'event':event,**kw},ensure_ascii=False)+'\n');wire.flush()
NS={'a':'http://schemas.openxmlformats.org/drawingml/2006/main','p':'http://schemas.openxmlformats.org/presentationml/2006/main','r':'http://schemas.openxmlformats.org/officeDocument/2006/relationships'}
REL='{http://schemas.openxmlformats.org/package/2006/relationships}'

def package(path):
    z=zipfile.ZipFile(path)
    names=z.namelist()
    if len(names)>10000 or sum(i.file_size for i in z.infolist())>100*1024**2 or any('vbaproject' in n.lower() for n in names):
        z.close();raise ValueError('PPTX troppo grande o con macro. Usa un PPTX senza macro o un PDF.')
    if 'ppt/presentation.xml' not in names:z.close();raise ValueError('Presentazione PPTX non valida.')
    return z

def pptx_pdf(path,folder):
    from PIL import Image
    from h3chat.pdf_export import export_pdf
    warnings=set();sections=[]
    with package(path) as z:
        def xml(name):
            raw=z.read(name)
            if b'<!DOCTYPE' in raw.upper() or b'<!ENTITY' in raw.upper():raise ValueError('XML PPTX non supportato.')
            return ET.fromstring(raw)
        def rels(name):
            directory,filename=posixpath.split(name);r=directory+'/_rels/'+filename+'.rels'
            if r not in z.namelist():return {}
            return {e.get('Id'):posixpath.normpath(posixpath.join(directory,e.get('Target',''))) for e in xml(r) if e.get('TargetMode')!='External'}
        presentation=xml('ppt/presentation.xml');size=presentation.find('p:sldSz',NS)
        width=int(size.get('cx'));height=int(size.get('cy'));pixel_height=1280*height/width
        if not width>0 or not height>0 or not .25<=width/height<=4:raise ValueError('Formato PPTX non supportato.')
        theme={};theme_font='Calibri'
        if 'ppt/theme/theme1.xml' in z.namelist():
            t=xml('ppt/theme/theme1.xml')
            for node in t.findall('a:themeElements/a:clrScheme/*',NS):
                child=next(iter(node),None)
                if child is not None:theme[node.tag.split('}')[-1]]=child.get('val') if child.tag.endswith('srgbClr') else child.get('lastClr','000000')
            font=t.find('a:themeElements/a:fontScheme/a:minorFont/a:latin',NS)
            if font is not None:theme_font=font.get('typeface',theme_font)
        def color(node,default='000000'):
            if node is None:return '#'+default
            v=node.find('a:srgbClr',NS)
            if v is not None:return '#'+v.get('val',default)
            v=node.find('a:schemeClr',NS)
            if v is not None:return '#'+theme.get({'tx1':'dk1','bg1':'lt1','tx2':'dk2','bg2':'lt2'}.get(v.get('val'),v.get('val')),default)
            return '#'+default
        slides=presentation.findall('p:sldIdLst/p:sldId',NS)
        if not 1<=len(slides)<=30:raise ValueError('Presentazione Manim: massimo 30 slide; dividi il file.')
        links=rels('ppt/presentation.xml')
        for index,s in enumerate(slides):
            name=links.get(s.get('{'+NS['r']+'}id'));slide=xml(name);links_slide=rels(name)
            bg=color(slide.find('p:cSld/p:bg/p:bgPr/a:solidFill',NS),'FFFFFF');parts=[]
            def draw(tree,transform=(1,1,0,0)):
                sx,sy,dx,dy=transform
                for shape in tree:
                    kind=shape.tag.split('}')[-1]
                    if kind not in ('sp','pic','grpSp','graphicFrame','cxnSp'):continue
                    xf=shape.find('p:spPr/a:xfrm',NS)
                    if xf is None:xf=shape.find('p:xfrm',NS)
                    if kind=='grpSp':xf=shape.find('p:grpSpPr/a:xfrm',NS)
                    if xf is None:
                        warnings.add('Alcuni segnaposto ereditati dal tema non hanno coordinate esplicite: per la massima fedeltà esporta il PPTX in PDF.');continue
                    off=xf.find('a:off',NS);ext=xf.find('a:ext',NS)
                    if off is None or ext is None:continue
                    x=float(off.get('x',0))*sx+dx;y=float(off.get('y',0))*sy+dy
                    w=float(ext.get('cx',0))*sx;h=float(ext.get('cy',0))*sy
                    if kind=='grpSp':
                        co=xf.find('a:chOff',NS);ce=xf.find('a:chExt',NS)
                        if co is not None and ce is not None and float(ce.get('cx',0)) and float(ce.get('cy',0)):
                            nsx=w/float(ce.get('cx'));nsy=h/float(ce.get('cy'));draw(shape,(nsx,nsy,x-float(co.get('x'))*nsx,y-float(co.get('y'))*nsy))
                        continue
                    if w<=0 or h<=0:continue
                    style=f'position:absolute;left:{x/width*100:.5f}%;top:{y/height*100:.5f}%;width:{w/width*100:.5f}%;height:{h/height*100:.5f}%;box-sizing:border-box;overflow:hidden;'
                    angle=float(xf.get('rot',0))/60000
                    if angle:style+=f'transform:rotate({angle}deg);'
                    if kind=='pic':
                        blip=shape.find('.//a:blip',NS);target=links_slide.get(blip.get('{'+NS['r']+'}embed')) if blip is not None else None
                        if not target or target not in z.namelist():warnings.add('Immagine collegata esternamente non importata.');continue
                        try:
                            with Image.open(io.BytesIO(z.read(target))) as picture:
                                if picture.width*picture.height>50_000_000:raise ValueError('Immagine PPTX troppo grande.')
                                data=io.BytesIO();picture.convert('RGB').save(data,format='PNG')
                            crop=shape.find('.//a:srcRect',NS);l=r=t=b=0
                            if crop is not None:l,r,t,b=(float(crop.get(k,0))/100000 for k in ('l','r','t','b'))
                            if l+r>=1 or t+b>=1:raise ValueError('Ritaglio immagine PPTX non valido.')
                            picstyle=f'position:absolute;left:{-l/(1-l-r)*100}%;top:{-t/(1-t-b)*100}%;width:{100/(1-l-r)}%;height:{100/(1-t-b)}%;max-width:none;object-fit:fill;'
                            parts.append('<div style="'+style+'"><img style="'+picstyle+'" src="data:image/png;base64,'+base64.b64encode(data.getvalue()).decode()+'"></div>')
                        except (OSError,ValueError):warnings.add('Una figura vettoriale o non supportata richiede un’esportazione PDF del PPTX.')
                        continue
                    if kind=='graphicFrame':warnings.add('Grafici, SmartArt e oggetti incorporati complessi: usa il PDF esportato da PowerPoint per conservarne l’aspetto.');continue
                    sp=shape.find('p:spPr',NS);fill=sp.find('a:solidFill',NS) if sp is not None else None
                    if fill is not None:style+='background:'+color(fill)+';'
                    geometry=sp.find('a:prstGeom',NS) if sp is not None else None
                    if geometry is not None and geometry.get('prst')=='ellipse':style+='border-radius:50%;'
                    elif geometry is not None and geometry.get('prst') not in ('rect','roundRect'):warnings.add('Alcune forme decorative sono approssimate; usa PDF per una copia fedele.')
                    line=sp.find('a:ln',NS) if sp is not None else None
                    if line is not None and line.find('a:noFill',NS) is None:style+=f'border:{max(.5,float(line.get("w",12700))/width*1280)}px solid '+color(line.find('a:solidFill',NS))+';'
                    text=[]
                    for paragraph in shape.findall('p:txBody/a:p',NS):
                        prop=paragraph.find('a:pPr',NS);align={'ctr':'center','r':'right','just':'justify'}.get(prop.get('algn') if prop is not None else '', 'left')
                        runs=[]
                        for run in paragraph:
                            if run.tag.endswith('}br'):runs.append('<br>');continue
                            if run.tag.split('}')[-1] not in ('r','fld'):continue
                            content=run.find('a:t',NS)
                            if content is None:continue
                            rp=run.find('a:rPr',NS)
                            if rp is None and prop is not None:rp=prop.find('a:defRPr',NS)
                            attrs=rp.attrib if rp is not None else {};font=rp.find('a:latin',NS) if rp is not None else None
                            face=font.get('typeface',theme_font) if font is not None else theme_font
                            if face.startswith('+'):face=theme_font
                            css=f'font-size:{float(attrs.get("sz",1800))/100*12700/width*1280}px;font-family:{html.escape(face,quote=True)};color:'+color(rp.find('a:solidFill',NS) if rp is not None else None)+';'
                            if attrs.get('b')=='1':css+='font-weight:bold;'
                            if attrs.get('i')=='1':css+='font-style:italic;'
                            runs.append('<span style="'+css+'">'+html.escape(content.text or '')+'</span>')
                        text.append('<p style="margin:0;line-height:1.15;text-align:'+align+'">'+''.join(runs)+'</p>')
                    body=shape.find('p:txBody/a:bodyPr',NS);inset=float(body.get('lIns',91440)) if body is not None else 91440
                    parts.append('<div style="'+style+f'padding:{inset/width*1280}px;">'+''.join(text)+'</div>')
            tree=slide.find('p:cSld/p:spTree',NS)
            if tree is not None:draw(tree)
            sections.append(f'<section style="position:relative;width:1280px;height:{pixel_height}px;background:{bg};break-after:page;overflow:hidden">'+''.join(parts)+'</section>')
    # Reuse the app's sanitized, network-disabled browser PDF renderer.
    result=export_pdf(ROOT,folder,{'title':'PPTX import','html':''.join(sections),'page_dimensions':[1280,pixel_height]})
    pdf=folder/'exports'/result['url'].split('/')[2]/'document.pdf'
    return pdf,sorted(warnings)

def extract(request):
    import pypdfium2 as pdfium
    from PIL import Image
    folder=Path(request['output']).resolve();folder.mkdir(parents=True,exist_ok=True)
    pages=[];warnings=[]
    def add(image,text,regions,original):
        if len(pages)>=30:raise ValueError('Presentazione Manim: massimo 30 slide; dividi il file. Nessuna pagina è stata scartata.')
        number=len(pages)+1;name=f'slide-{number:03}.png';path=folder/name;image.save(path)
        assets=[{'name':name,'path':str(path),'original':original}];selected=[]
        w,h=image.size
        for region in regions[:8]:
            box=region['box'];left,top,right,bottom=[max(0,min(1,float(n))) for n in box]
            if right-left<.01 or bottom-top<.01:continue
            part=f'slide-{number:03}-part-{len(selected)+1:02}.png';target=folder/part
            image.crop((round(left*w),round(top*h),round(right*w),round(bottom*h))).save(target)
            selected.append({'asset':'assets/'+part,'kind':region['kind'],'text':region.get('text','')[:1500],
                             'left':left,'top':top,'width':right-left,'height':bottom-top})
            assets.append({'name':part,'path':str(target),'original':original+' · dettaglio'})
        pages.append({'number':number,'original':original,'text':text[:14000],'aspect':w/h,'regions':selected,'assets':assets})
    for item in request['inputs']:
        path=Path(item['path']);emit('stage',message='Manim · lettura presentazione '+item['name'])
        if not path.is_file() or path.stat().st_size>64*1024**2:raise ValueError('Presentazione non disponibile o oltre 64 MB.')
        if path.suffix.lower()=='.pptx':path,notes=pptx_pdf(path,folder);warnings.extend(notes)
        if path.suffix.lower()=='.pdf':
            with pdfium.PdfDocument(str(path)) as doc:
                if len(pages)+len(doc)>30:raise ValueError('Presentazione Manim: massimo 30 slide; dividi il file.')
                for index in range(len(doc)):
                    page=doc[index];w,h=page.get_size();regions=[];text=''
                    try:
                        tp=page.get_textpage()
                        try:
                            text=tp.get_text_range()
                            for r in range(min(tp.count_rects(),32)):
                                x1,y1,x2,y2=tp.get_rect(r)
                                regions.append({'kind':'text','text':tp.get_text_bounded(x1,y1,x2,y2),'box':[x1/w,1-y2/h,x2/w,1-y1/h]})
                        finally:tp.close()
                        pictures=[]
                        for obj in page.get_objects(filter=[3]):
                            x1,y1,x2,y2=obj.get_bounds();pictures.append({'kind':'image','box':[x1/w,1-y2/h,x2/w,1-y1/h]})
                        regions=pictures[:4]+regions[:max(0,8-len(pictures[:4]))]
                        bitmap=page.render(scale=min(2,1600/max(w,h)))
                        try:add(bitmap.to_pil().convert('RGB'),text,regions,item['name']+' · pagina '+str(index+1))
                        finally:bitmap.close()
                    finally:page.close()
        else:
            with Image.open(path) as image:
                if image.width*image.height>50_000_000:raise ValueError('Immagine slide troppo grande.')
                from PIL import ImageOps
                image=ImageOps.exif_transpose(image).convert('RGB');image.thumbnail((1600,1600))
                add(image,'',[],item['name'])
    return {'version':1,'pages':pages,'warnings':sorted(set(warnings))}

if __name__=='__main__':
    emit('hello')
    try:emit('result',result=extract(json.loads(sys.stdin.readline())))
    except Exception as error:
        import traceback
        traceback.print_exc();emit('error',message=str(error))

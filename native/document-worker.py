"""Read documents in an isolated, time-limited process. Never execute macros."""
import json
import os
import re
from pathlib import Path
import sys
import zipfile
ROOT=Path(__file__).resolve().parents[1]
RUNTIME=ROOT/'runtime/tools/documents'
sys.path[:0]=[str(ROOT),str(RUNTIME)]
from h3chat.document_limits import limits,RAG_PDF_PAGES
dll=os.add_dll_directory(str(RUNTIME)) if os.name=='nt' and RUNTIME.is_dir() else None
wire=sys.stdout;sys.stdout=sys.stderr
def emit(event,**kw):wire.write(json.dumps({'event':event,**kw},ensure_ascii=False)+'\n');wire.flush()

def chunks(text):
    current=''
    for word in re.findall(r'\S+\s*',text):
        if current and len(current)+len(word)>1800:yield current;current=''
        current+=word
    if current:yield current

def read(path,profile='chat'):
    path=Path(path);blocks=[];blank=[];warnings=[]
    max_pages,max_chars,_=limits(profile)
    if path.suffix.lower()=='.pdf':
        from pypdf import PdfReader
        # A file object keeps large images/streams on disk until actually needed.
        with path.open('rb') as stream:
            doc=PdfReader(stream)
            if doc.is_encrypted:raise ValueError('Il PDF è protetto: allega una copia senza password.')
            total=len(doc.pages)
            if total>max_pages:raise ValueError(f'PDF: massimo {max_pages} pagine per '+('il RAG.' if profile=='rag' else 'allegato chat. Usa un progetto RAG per un libro completo.'))
            count=0
            for i,page in enumerate(doc.pages):
                emit('stage',message=f'Lettura PDF · pagina {i+1}/{total}')
                contents=page.get_contents()
                if contents and len(contents.get_data())>16*1024**2:raise ValueError('Una pagina PDF è troppo complessa: esportala con una risoluzione inferiore.')
                text=page.extract_text() or ''
                count+=len(text)
                if count>max_chars:raise ValueError(f'Documento troppo lungo: massimo {max_chars:,} caratteri estratti.'.replace(',','.'))
                if not text.strip():blank.append(i+1)
                for chunk in chunks(text):blocks.append({'location':f'pagina {i+1}','page':i+1,'text':chunk})
        if blank:warnings.append(f'{len(blank)} pagine senza testo estraibile: possono richiedere Vision.')
    else:
        validate_docx(path,profile)
        from docx import Document
        from docx.table import Table
        doc=Document(path);total=0;count=0
        for i,item in enumerate(doc.iter_inner_content(),1):
            text='\n'.join(' | '.join(c.text for c in row.cells) for row in item.rows) if isinstance(item,Table) else item.text
            count+=len(text)
            if count>max_chars:raise ValueError('Documento Word troppo lungo.')
            for chunk in chunks(text):blocks.append({'location':f'blocco {i}','page':None,'text':chunk})
        warnings.append('Word: testo e tabelle estratti; immagini, intestazioni e layout non vengono analizzati.')
    return {'blocks':blocks,'pages':total,'blank_pages':blank,'warnings':warnings}

def validate_docx(path,profile='chat'):
    _,_,max_archive=limits(profile)
    with zipfile.ZipFile(path) as z:
        items=z.infolist();names={x.filename for x in items}
        if not {'[Content_Types].xml','word/document.xml'}<=names:raise ValueError('Il file non è un documento Word .docx.')
        if len(items)>10000 or sum(x.file_size for x in items)>max_archive:raise ValueError('Documento Word decompresso troppo grande.')
        if any(x.flag_bits&1 or (x.file_size>1024*1024 and x.file_size/max(1,x.compress_size)>200) for x in items):raise ValueError('Archivio Word compresso o cifrato non consentito.')
        if any('vbaproject' in x.lower() for x in names):raise ValueError('Usa un .docx senza macro.')

def render(path,pages,output):
    import pypdfium2 as pdfium
    doc=pdfium.PdfDocument(path);result=[]
    try:
        for number in pages[:4]:
            if not 1<=number<=len(doc):raise ValueError('Pagina PDF inesistente.')
            page=doc[number-1]
            try:
                w,h=page.get_size();scale=min(1.7,1600/max(w,h));bitmap=page.render(scale=scale)
                try:
                    target=Path(output)/f'page-{number}.png';target.parent.mkdir(parents=True,exist_ok=True);bitmap.to_pil().save(target);result.append({'page':number,'path':str(target)})
                finally:bitmap.close()
            finally:page.close()
    finally:doc.close()
    return result

def assets(path, pages, output, limit=16):
    """Bounded embedded figures; scan pages remain eligible as whole-page images."""
    from PIL import Image
    import io
    Image.MAX_IMAGE_PIXELS=20000000
    folder=Path(output);folder.mkdir(parents=True,exist_ok=True)
    result=[];seen=set()
    def save(raw,location):
        import hashlib
        if len(result)>=limit or len(raw)>20*1024**2:return
        key=hashlib.sha256(raw).hexdigest()
        if key in seen:return
        seen.add(key)
        try:
            with Image.open(io.BytesIO(raw)) as image:
                if image.width<100 or image.height<100:return
                image.thumbnail((1600,1600))
                target=folder/f'figure-{len(result)+1}.png';image.convert('RGB').save(target)
            result.append({'path':str(target),'location':location})
        except (OSError,ValueError):return
    if Path(path).suffix.lower()=='.docx':
        validate_docx(path,'rag')
        with zipfile.ZipFile(path) as z:
            for item in z.infolist():
                if item.filename.startswith('word/media/') and item.file_size<=20*1024**2:
                    save(z.read(item),Path(item.filename).name)
                if len(result)>=limit:break
    else:
        from pypdf import PdfReader
        with Path(path).open('rb') as stream:
            doc=PdfReader(stream)
            if doc.is_encrypted or len(doc.pages)>RAG_PDF_PAGES:raise ValueError('PDF protetto o troppo lungo.')
            numbers=list(dict.fromkeys(pages)) if pages else list(range(1,len(doc.pages)+1))
            for number in numbers:
                if not 1<=number<=len(doc.pages):continue
                page=doc.pages[number-1]
                contents=page.get_contents()
                if contents and len(contents.get_data())>16*1024**2:continue
                for image in page.images:
                    save(image.data,f'pagina {number} · {image.name}')
                    if len(result)>=limit:break
                if len(result)>=limit:break
    return result

def visuals(path,output):
    """Index every illustrated PDF page and raster image in Word, on disk."""
    from PIL import Image
    import io,hashlib
    Image.MAX_IMAGE_PIXELS=20_000_000
    path=Path(path);folder=Path(output);folder.mkdir(parents=True,exist_ok=True)
    result=[];warnings=[];seen=set()
    def save(raw,location,page=None):
        key=hashlib.sha256(raw).hexdigest()
        if key in seen:return
        if len(raw)>32*1024**2:raise ValueError('Una figura è troppo grande per il RAG: massimo 32 MB.')
        with Image.open(io.BytesIO(raw)) as image:
            if image.width*image.height>20_000_000:raise ValueError('Una figura supera 20 milioni di pixel.')
            image.thumbnail((1600,1600));target=folder/f'image-{len(result)+1}.png';image.convert('RGB').save(target)
        seen.add(key);result.append({'path':target.name,'location':location,'page':page})
        if len(result)>RAG_PDF_PAGES:raise ValueError('Massimo 3.000 immagini per documento RAG.')
    if path.suffix.lower()=='.pdf':
        import pypdfium2 as pdfium
        doc=pdfium.PdfDocument(path)
        try:
            if len(doc)>RAG_PDF_PAGES:raise ValueError('PDF: massimo 3.000 pagine per il RAG.')
            for i in range(len(doc)):
                emit('stage',message=f'RAG · analisi figure · pagina {i+1}/{len(doc)}')
                page=doc[i]
                try:
                    # Image, vector path and shading objects include photos,
                    # plots and diagrams. Text objects alone do not create a vector.
                    if not any(obj.type in (2,3,5) for obj in page.get_objects()):continue
                    w,h=page.get_size();scale=min(1600/max(w,h),(602112/(w*h))**.5)
                    bitmap=page.render(scale=scale)
                    try:
                        target=folder/f'page-{i+1}.png';bitmap.to_pil().convert('RGB').save(target)
                        result.append({'path':target.name,'location':f'pagina {i+1} · contenuto visivo','page':i+1})
                    finally:bitmap.close()
                finally:page.close()
        finally:doc.close()
    elif path.suffix.lower()=='.docx':
        validate_docx(path,'rag')
        from docx import Document
        doc=Document(path)
        for number,item in enumerate(doc.iter_inner_content(),1):
            for blip in item._element.xpath('.//a:blip'):
                rel=blip.get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}embed')
                if rel and rel in doc.part.related_parts:
                    part=doc.part.related_parts[rel]
                    if not part.content_type.startswith('image/'):continue
                    try:save(part.blob,f'blocco {number} · immagine')
                    except OSError:warnings.append(f'Figura del blocco {number} non decodificabile; non indicizzata.')
    else:
        if path.stat().st_size>32*1024**2:raise ValueError('Immagine RAG troppo grande: massimo 32 MB.')
        save(path.read_bytes(),'immagine')
    return {'visuals':result,'warnings':warnings}

emit('hello',engine='documents')
for line in sys.stdin:
    try:
        request=json.loads(line)
        result=(read(request['path'],request.get('profile','chat')) if request['op']=='read' else visuals(request['path'],request['folder']) if request['op']=='visuals' else assets(request['path'],request.get('pages',[]),request['output'],request.get('limit',16)) if request['op']=='assets' else render(request['path'],request['pages'],request['output']))
        if request['op'] in ('read','visuals'):
            target=Path(request['output']);target.parent.mkdir(parents=True,exist_ok=True);part=target.with_suffix('.writing');part.write_text(json.dumps(result,ensure_ascii=False),encoding='utf-8');part.replace(target);result={'path':str(target)}
        emit('result',result=result)
    except Exception as e:emit('error',message=str(e))
